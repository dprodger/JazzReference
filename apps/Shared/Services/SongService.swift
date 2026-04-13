import SwiftUI
import Combine

// MARK: - Song Service

@MainActor
class SongService: ObservableObject {
    @Published var songs: [Song] = []
    @Published var isLoading = false
    @Published var errorMessage: String?

    // MARK: - Song List

    func fetchSongs(searchQuery: String = "") async {
        let startTime = Date()
        isLoading = true
        errorMessage = nil

        var path = "/songs"
        if !searchQuery.isEmpty {
            let normalizedQuery = APIClient.normalizeSearchText(searchQuery)
            path += "?search=\(normalizedQuery.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? "")"
        }

        let url = URL.api(path: path)

        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            let decodedSongs = try JSONDecoder().decode([Song].self, from: data)

            guard !Task.isCancelled else { return }

            self.songs = decodedSongs
            self.isLoading = false
            APIClient.logRequest("GET /songs\(searchQuery.isEmpty ? "" : "?search=...")", startTime: startTime)
        } catch is CancellationError {
            return
        } catch let error as NSError where error.code == NSURLErrorCancelled {
            return
        } catch {
            guard !Task.isCancelled else { return }
            self.errorMessage = "Failed to fetch songs: \(error.localizedDescription)"
            self.isLoading = false
        }
    }

    // MARK: - Song Search

    func searchSongs(query: String) async throws -> [Song] {
        let encodedQuery = query.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? query
        let url = URL.api(path: "/songs?search=\(encodedQuery)&limit=20")

        let (data, response) = try await URLSession.shared.data(from: url)

        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw URLError(.badServerResponse)
        }

        return try JSONDecoder().decode([Song].self, from: data)
    }

    // MARK: - Song Detail

    func fetchSongDetail(id: String, sortBy: RecordingSortOrder) async -> Song? {
        let url = URL.api(path: "/songs/\(id)?sort=\(sortBy.rawValue)")

        do {
            let (data, response) = try await URLSession.shared.data(from: url)

            if let httpResponse = response as? HTTPURLResponse {
                guard (200...299).contains(httpResponse.statusCode) else {
                    print("HTTP error: \(httpResponse.statusCode)")
                    return nil
                }
            }

            return try JSONDecoder().decode(Song.self, from: data)
        } catch {
            print("Error fetching song detail with sort: \(error)")
            if let decodingError = error as? DecodingError {
                print("Decoding error details: \(decodingError)")
            }
            return nil
        }
    }

    func fetchSongDetail(id: String) async -> Song? {
        return await fetchSongDetail(id: id, sortBy: .year)
    }

    // MARK: - Two-Phase Song Loading

    func fetchSongSummary(id: String) async -> Song? {
        let startTime = Date()
        let url = URL.api(path: "/songs/\(id)/summary")

        do {
            let (data, response) = try await URLSession.shared.data(from: url)

            if let httpResponse = response as? HTTPURLResponse {
                guard (200...299).contains(httpResponse.statusCode) else {
                    print("HTTP error fetching song summary: \(httpResponse.statusCode)")
                    return nil
                }
            }

            let song = try JSONDecoder().decode(Song.self, from: data)
            APIClient.logRequest("GET /songs/\(id)/summary", startTime: startTime)

            if APIClient.diagnosticsEnabled {
                print("   \u{21B3} Summary: \(song.featuredRecordings?.count ?? 0) featured recordings, \(song.recordingCount ?? 0) total")
            }
            return song
        } catch {
            print("Error fetching song summary: \(error)")
            if let decodingError = error as? DecodingError {
                print("Decoding error details: \(decodingError)")
            }
            return nil
        }
    }

    func fetchSongRecordings(id: String, sortBy: RecordingSortOrder = .year) async -> [Recording]? {
        let startTime = Date()
        let url = URL.api(path: "/songs/\(id)/recordings?sort=\(sortBy.rawValue)")

        do {
            let (data, response) = try await URLSession.shared.data(from: url)

            if let httpResponse = response as? HTTPURLResponse {
                guard (200...299).contains(httpResponse.statusCode) else {
                    print("HTTP error fetching song recordings: \(httpResponse.statusCode)")
                    return nil
                }
            }

            let recordingsResponse = try JSONDecoder().decode(SongRecordingsResponse.self, from: data)
            APIClient.logRequest("GET /songs/\(id)/recordings", startTime: startTime)

            if APIClient.diagnosticsEnabled {
                print("   \u{21B3} Loaded \(recordingsResponse.recordingCount) recordings")
            }
            return recordingsResponse.recordings
        } catch {
            print("Error fetching song recordings: \(error)")
            if let decodingError = error as? DecodingError {
                print("Decoding error details: \(decodingError)")
            }
            return nil
        }
    }

    // MARK: - Transcriptions

    func fetchSongTranscriptions(songId: String) async -> [SoloTranscription] {
        #if DEBUG
        if APIClient.isPreviewMode {
            return [.preview1, .preview2]
        }
        #endif

        let url = URL.api(path: "/songs/\(songId)/transcriptions")

        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            return try JSONDecoder().decode([SoloTranscription].self, from: data)
        } catch {
            print("Error fetching song transcriptions: \(error)")
            return []
        }
    }

    #if DEBUG
    func fetchSongTranscriptionsSync(songId: String) -> [SoloTranscription] {
        if APIClient.isPreviewMode {
            return [.preview1, .preview2]
        }
        return []
    }
    #endif

    // MARK: - Songs in Repertoire

    func fetchSongsInRepertoire(repertoireId: String, searchQuery: String = "", authToken: String? = nil) async {
        let startTime = Date()
        isLoading = true
        errorMessage = nil

        var path: String
        if repertoireId == "all" {
            path = "/songs/index"
        } else {
            path = "/repertoires/\(repertoireId)/songs"
        }

        if !searchQuery.isEmpty {
            let normalizedQuery = APIClient.normalizeSearchText(searchQuery)
            path += "?search=\(normalizedQuery.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? "")"
        }

        let url = URL.api(path: path)

        var request = URLRequest(url: url)
        if let token = authToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        do {
            let (data, response) = try await URLSession.shared.data(for: request)

            if let httpResponse = response as? HTTPURLResponse {
                if httpResponse.statusCode == 401 {
                    self.errorMessage = "Authentication required. Please log in again."
                    self.isLoading = false
                    return
                } else if httpResponse.statusCode != 200 {
                    self.errorMessage = "Failed to load songs (HTTP \(httpResponse.statusCode))"
                    self.isLoading = false
                    return
                }
            }

            let decodedSongs = try JSONDecoder().decode([Song].self, from: data)

            guard !Task.isCancelled else { return }

            self.songs = decodedSongs
            self.isLoading = false

            let endpoint = repertoireId == "all" ?
                "GET /songs/index" :
                "GET /repertoires/\(repertoireId)/songs"
            APIClient.logRequest(endpoint + (searchQuery.isEmpty ? "" : "?search=..."), startTime: startTime)

            if APIClient.diagnosticsEnabled {
                print("   \u{21B3} Returned \(decodedSongs.count) songs")
            }
        } catch is CancellationError {
            return
        } catch let error as NSError where error.code == NSURLErrorCancelled {
            return
        } catch {
            guard !Task.isCancelled else { return }
            self.errorMessage = "Failed to fetch songs: \(error.localizedDescription)"
            self.isLoading = false
            print("Error fetching repertoire songs: \(error)")
        }
    }

    // MARK: - Repertoire Management

    func fetchRepertoires() async -> [Repertoire] {
        let startTime = Date()
        let url = URL.api(path: "/repertoires")

        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            let repertoires = try JSONDecoder().decode([Repertoire].self, from: data)
            APIClient.logRequest("GET /repertoires", startTime: startTime)

            if APIClient.diagnosticsEnabled {
                print("   \u{21B3} Returned \(repertoires.count) repertoires")
            }
            return repertoires
        } catch {
            print("Error fetching repertoires: \(error)")
            return []
        }
    }

    func addSongToRepertoire(songId: String, repertoireId: String) async -> Result<String, Error> {
        let startTime = Date()
        let url = URL.api(path: "/repertoires/\(repertoireId)/songs")

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body = ["song_id": songId]

        do {
            request.httpBody = try JSONSerialization.data(withJSONObject: body)

            let (data, response) = try await URLSession.shared.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                return .failure(NSError(domain: "SongService", code: -1, userInfo: [NSLocalizedDescriptionKey: "Invalid response"]))
            }

            APIClient.logRequest("POST /repertoires/\(repertoireId)/songs", startTime: startTime)

            if httpResponse.statusCode == 201 {
                if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   let message = json["message"] as? String {
                    print("   \u{21B3} \(message)")
                    return .success(message)
                }
                return .success("Song added to repertoire")
            } else if httpResponse.statusCode == 409 {
                if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   let error = json["error"] as? String {
                    print("   \u{21B3} \(error)")
                    return .failure(NSError(domain: "SongService", code: 409, userInfo: [NSLocalizedDescriptionKey: error]))
                }
                return .failure(NSError(domain: "SongService", code: 409, userInfo: [NSLocalizedDescriptionKey: "Song already in repertoire"]))
            } else {
                if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   let error = json["error"] as? String {
                    return .failure(NSError(domain: "SongService", code: httpResponse.statusCode, userInfo: [NSLocalizedDescriptionKey: error]))
                }
                return .failure(NSError(domain: "SongService", code: httpResponse.statusCode, userInfo: [NSLocalizedDescriptionKey: "Failed to add song"]))
            }
        } catch {
            print("Error adding song to repertoire: \(error)")
            return .failure(error)
        }
    }

    // MARK: - Preview Support

    #if DEBUG
    func fetchSongDetailSync(id: String) -> Song? {
        if APIClient.isPreviewMode {
            switch id {
            case "preview-song-1":
                return Song.preview
            case "preview-song-2":
                return Song.previewNoRecordings
            default:
                return Song.preview
            }
        }
        return nil
    }
    #endif
}

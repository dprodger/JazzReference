// MARK: - Queue Status Models
struct CurrentSong: Codable {
    let songId: String
    let songName: String
    
    enum CodingKeys: String, CodingKey {
        case songId = "song_id"
        case songName = "song_name"
    }
}

struct ResearchProgress: Codable {
    let phase: String
    let current: Int
    let total: Int
    
    /// Human-readable description of the current phase
    var phaseDescription: String {
        switch phase {
        case "musicbrainz_recording_import":
            return "Importing MusicBrainz recordings"
        case "spotify_track_match":
            return "Matching Spotify tracks"
        default:
            return phase.replacingOccurrences(of: "_", with: " ").capitalized
        }
    }
    
    /// Short label for the phase
    var phaseLabel: String {
        switch phase {
        case "musicbrainz_recording_import":
            return "MusicBrainz"
        case "spotify_track_match":
            return "Spotify"
        default:
            return phase
        }
    }
    
    /// Progress as a fraction (0.0 to 1.0)
    var progressFraction: Double {
        guard total > 0 else { return 0 }
        return Double(current) / Double(total)
    }
}

struct QueueStatus: Codable {
    let queueSize: Int
    let workerActive: Bool
    let currentSong: CurrentSong?
    let progress: ResearchProgress?
    
    enum CodingKeys: String, CodingKey {
        case queueSize = "queue_size"
        case workerActive = "worker_active"
        case currentSong = "current_song"
        case progress
    }
}

// MARK: - Network Manager
import SwiftUI
import Combine

class NetworkManager: ObservableObject {
    static let baseURL = "https://www.linernotesjazz.com/api"
    @Published var songs: [Song] = []
    @Published var performers: [Performer] = []
    @Published var isLoading = false
    @Published var errorMessage: String?
    @Published var recordings: [Recording] = []
    
    // MARK: - Diagnostics
    private static var requestCounter = 0
    private static let diagnosticsEnabled = true // Toggle this to enable/disable logging
    
    private static func logRequest(_ endpoint: String, startTime: Date) {
        guard diagnosticsEnabled else { return }
        requestCounter += 1
        let duration = Date().timeIntervalSince(startTime)
        print("🌐 API Call #\(requestCounter): \(endpoint) (took \(String(format: "%.2f", duration))s)")
    }
    
    static func resetRequestCounter() {
        requestCounter = 0
        if diagnosticsEnabled {
            print("📊 Request counter reset")
        }
    }
    
    static func printRequestSummary() {
        guard diagnosticsEnabled else { return }
        print("📊 Total API calls in this session: \(requestCounter)")
    }
    
    // MARK: - Network Methods
    
    func fetchSongs(searchQuery: String = "") async {
        let startTime = Date()
        await MainActor.run {
            isLoading = true
            errorMessage = nil
        }
        
        var urlString = "\(NetworkManager.baseURL)/songs"
        if !searchQuery.isEmpty {
            urlString += "?search=\(searchQuery.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? "")"
        }
        
        guard let url = URL(string: urlString) else {
            await MainActor.run {
                errorMessage = "Invalid URL"
                isLoading = false
            }
            return
        }
        
        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            let decodedSongs = try JSONDecoder().decode([Song].self, from: data)
            
            await MainActor.run {
                self.songs = decodedSongs
                self.isLoading = false
            }
            NetworkManager.logRequest("GET /songs\(searchQuery.isEmpty ? "" : "?search=...")", startTime: startTime)
        } catch {
            await MainActor.run {
                self.errorMessage = "Failed to fetch songs: \(error.localizedDescription)"
                self.isLoading = false
            }
        }
    }
    
    func fetchPerformers(searchQuery: String = "") async {
        let startTime = Date()
        await MainActor.run {
            isLoading = true
            errorMessage = nil
        }
        
        var urlString = "\(NetworkManager.baseURL)/performers"
        if !searchQuery.isEmpty {
            urlString += "?search=\(searchQuery.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? "")"
        }
        
        guard let url = URL(string: urlString) else {
            await MainActor.run {
                errorMessage = "Invalid URL"
                isLoading = false
            }
            return
        }
        
        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            let decodedPerformers = try JSONDecoder().decode([Performer].self, from: data)
            
            await MainActor.run {
                self.performers = decodedPerformers
                self.isLoading = false
            }
            NetworkManager.logRequest("GET /performers\(searchQuery.isEmpty ? "" : "?search=...")", startTime: startTime)
        } catch {
            await MainActor.run {
                self.errorMessage = "Failed to fetch performers: \(error.localizedDescription)"
                self.isLoading = false
            }
        }
    }
    
/*
    func fetchSongDetail(id: String) async -> Song? {
        let startTime = Date()
        guard let url = URL(string: "\(NetworkManager.baseURL)/songs/\(id)") else {
            return nil
        }
        
        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            let song = try JSONDecoder().decode(Song.self, from: data)
            NetworkManager.logRequest("GET /songs/\(id)", startTime: startTime)
            
            // Log additional info about what was returned
            if NetworkManager.diagnosticsEnabled {
                print("   ↳ Returned song with \(song.recordings?.count ?? 0) recordings")
            }
            return song
        } catch let error as NSError where error.code == NSURLErrorCancelled {
            // Silently ignore cancellations
            return nil
        } catch {
            print("Error fetching song detail: \(error)")
            return nil
        }
    }
    
*/
    func fetchRecordingDetail(id: String) async -> Recording? {
        let startTime = Date()
        guard let url = URL(string: "\(NetworkManager.baseURL)/recordings/\(id)") else {
            return nil
        }
        
        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            let recording = try JSONDecoder().decode(Recording.self, from: data)
            NetworkManager.logRequest("GET /recordings/\(id)", startTime: startTime)
            
            // Log additional info about what was returned
            if NetworkManager.diagnosticsEnabled {
                print("   ↳ Returned recording with \(recording.performers?.count ?? 0) performers")
            }
            return recording
        } catch let error as NSError where error.code == NSURLErrorCancelled {
            // Silently ignore cancellations
            return nil
        } catch {
            print("Error fetching recording detail: \(error)")
            return nil
        }
    }
    
    func fetchPerformerDetail(id: String) async -> PerformerDetail? {
        let startTime = Date()
        guard let url = URL(string: "\(NetworkManager.baseURL)/performers/\(id)") else {
            return nil
        }
        
        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            let performer = try JSONDecoder().decode(PerformerDetail.self, from: data)
            NetworkManager.logRequest("GET /performers/\(id)", startTime: startTime)
            
            // Log additional info about what was returned
            if NetworkManager.diagnosticsEnabled {
                print("   ↳ Returned performer with \(performer.recordings?.count ?? 0) recordings")
            }
            return performer
        } catch let error as NSError where error.code == NSURLErrorCancelled {
            // Silently ignore cancellations
            return nil
        } catch {
            print("Error fetching performer detail: \(error)")
            return nil
        }
    }
    
    // MARK: - Repertoire API Methods
    
    /// Fetch all available repertoires
    func fetchRepertoires() async -> [Repertoire] {
        let startTime = Date()
        guard let url = URL(string: "\(NetworkManager.baseURL)/repertoires") else {
            print("Error: Invalid repertoires URL")
            return []
        }
        
        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            let repertoires = try JSONDecoder().decode([Repertoire].self, from: data)
            NetworkManager.logRequest("GET /repertoires", startTime: startTime)
            
            if NetworkManager.diagnosticsEnabled {
                print("   ↳ Returned \(repertoires.count) repertoires")
            }
            return repertoires
        } catch {
            print("Error fetching repertoires: \(error)")
            return []
        }
    }
    
    /// Fetch songs in a specific repertoire
    /// - Parameters:
    ///   - repertoireId: The repertoire ID, or "all" for all songs
    ///   - searchQuery: Optional search query
    ///   - authToken: Optional auth token for protected repertoires
    func fetchSongsInRepertoire(repertoireId: String, searchQuery: String = "", authToken: String? = nil) async {
        let startTime = Date()
        await MainActor.run {
            isLoading = true
            errorMessage = nil
        }
        
        // Build URL - "all" uses public /songs endpoint, others use protected /repertoires endpoint
        var urlString: String
        if repertoireId == "all" {
            // Use the public songs endpoint (no auth required)
            urlString = "\(NetworkManager.baseURL)/songs"
        } else {
            // Use the protected repertoire endpoint (requires auth)
            urlString = "\(NetworkManager.baseURL)/repertoires/\(repertoireId)/songs"
        }
        
        // Add search query if present
        if !searchQuery.isEmpty {
            urlString += "?search=\(searchQuery.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? "")"
        }
        
        guard let url = URL(string: urlString) else {
            await MainActor.run {
                errorMessage = "Invalid URL"
                isLoading = false
            }
            return
        }
        
        // Build request with optional authentication
        var request = URLRequest(url: url)
        if let token = authToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        
        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            
            // Check for HTTP errors
            if let httpResponse = response as? HTTPURLResponse {
                if httpResponse.statusCode == 401 {
                    await MainActor.run {
                        self.errorMessage = "Authentication required. Please log in again."
                        self.isLoading = false
                    }
                    return
                } else if httpResponse.statusCode != 200 {
                    await MainActor.run {
                        self.errorMessage = "Failed to load songs (HTTP \(httpResponse.statusCode))"
                        self.isLoading = false
                    }
                    return
                }
            }
            
            let decodedSongs = try JSONDecoder().decode([Song].self, from: data)
            
            await MainActor.run {
                self.songs = decodedSongs
                self.isLoading = false
            }
            
            let endpoint = repertoireId == "all" ?
                "GET /songs" :
                "GET /repertoires/\(repertoireId)/songs"
            NetworkManager.logRequest(endpoint + (searchQuery.isEmpty ? "" : "?search=..."), startTime: startTime)
            
            if NetworkManager.diagnosticsEnabled {
                print("   ↳ Returned \(decodedSongs.count) songs")
            }
        } catch {
            await MainActor.run {
                self.errorMessage = "Failed to fetch songs: \(error.localizedDescription)"
                self.isLoading = false
            }
            print("Error fetching repertoire songs: \(error)")
        }
    }
    
    // MARK: - Add Song to Repertoire
    
    /// Add a song to a repertoire
    /// - Parameters:
    ///   - songId: The song ID to add
    ///   - repertoireId: The repertoire ID to add it to
    /// - Returns: Result with success message or error
    func addSongToRepertoire(songId: String, repertoireId: String) async -> Result<String, Error> {
        let startTime = Date()
        guard let url = URL(string: "\(NetworkManager.baseURL)/repertoires/\(repertoireId)/songs") else {
            print("Error: Invalid add song URL")
            return .failure(NSError(domain: "NetworkManager", code: -1, userInfo: [NSLocalizedDescriptionKey: "Invalid URL"]))
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        // Create request body
        let body = ["song_id": songId   ]
        
        do {
            request.httpBody = try JSONSerialization.data(withJSONObject: body)
            
            let (data, response) = try await URLSession.shared.data(for: request)
            
            guard let httpResponse = response as? HTTPURLResponse else {
                return .failure(NSError(domain: "NetworkManager", code: -1, userInfo: [NSLocalizedDescriptionKey: "Invalid response"]))
            }
            
            NetworkManager.logRequest("POST /repertoires/\(repertoireId)/songs", startTime: startTime)
            
            if httpResponse.statusCode == 201 {
                // Success
                if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   let message = json["message"] as? String {
                    print("   ↳ \(message)")
                    return .success(message)
                }
                return .success("Song added to repertoire")
            } else if httpResponse.statusCode == 409 {
                // Conflict - already in repertoire
                if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   let error = json["error"] as? String {
                    print("   ↳ \(error)")
                    return .failure(NSError(domain: "NetworkManager", code: 409, userInfo: [NSLocalizedDescriptionKey: error]))
                }
                return .failure(NSError(domain: "NetworkManager", code: 409, userInfo: [NSLocalizedDescriptionKey: "Song already in repertoire"]))
            } else {
                // Other error
                if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   let error = json["error"] as? String {
                    return .failure(NSError(domain: "NetworkManager", code: httpResponse.statusCode, userInfo: [NSLocalizedDescriptionKey: error]))
                }
                return .failure(NSError(domain: "NetworkManager", code: httpResponse.statusCode, userInfo: [NSLocalizedDescriptionKey: "Failed to add song"]))
            }
        } catch {
            print("Error adding song to repertoire: \(error)")
            return .failure(error)
        }
    }
        
    func refreshSongData(songId: String) async -> Bool {
        guard let url = URL(string: "\(NetworkManager.baseURL)/songs/\(songId)/refresh") else {
            print("Error: Invalid refresh URL")
            return false
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            
            guard let httpResponse = response as? HTTPURLResponse else {
                print("Error: Invalid response")
                return false
            }
            
            // 202 Accepted is the expected success status
            if httpResponse.statusCode == 202 {
                // Optionally parse the response to get queue info
                if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                    if let queueSize = json["queue_size"] as? Int {
                        print("✓ Song queued for research (queue size: \(queueSize))")
                    }
                }
                return true
            } else {
                print("Error: Unexpected status code \(httpResponse.statusCode)")
                if let responseString = String(data: data, encoding: .utf8) {
                    print("Response: \(responseString)")
                }
                return false
            }
        } catch {
            print("Error refreshing song data: \(error.localizedDescription)")
            return false
        }
    }
    
    /// Fetch the current research queue status
    func fetchQueueStatus() async -> QueueStatus? {
        let startTime = Date()
        guard let url = URL(string: "\(NetworkManager.baseURL)/research/queue") else {
            print("Error: Invalid queue status URL")
            return nil
        }
        
        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            let queueStatus = try JSONDecoder().decode(QueueStatus.self, from: data)
            
            NetworkManager.logRequest("GET /research/queue", startTime: startTime)
            
            if NetworkManager.diagnosticsEnabled {
                if let currentSong = queueStatus.currentSong {
                    print("   ↳ Queue: \(queueStatus.queueSize), Processing: \(currentSong.songName)")
                } else {
                    print("   ↳ Queue: \(queueStatus.queueSize)")
                }
            }
            
            return queueStatus
        } catch {
            print("Error fetching queue status: \(error.localizedDescription)")
            return nil
        }
    }
    
    func fetchAuthorityRecommendations(songId: String) async -> AuthorityRecommendationsResponse? {
        guard let url = URL(string: "\(Self.baseURL)/songs/\(songId)/authority_recommendations") else {
            return nil
        }
        
        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            let response = try JSONDecoder().decode(AuthorityRecommendationsResponse.self, from: data)
            return response
        } catch {
            print("Error fetching authority recommendations: \(error)")
            return nil
        }
    }
    
    func fetchSongDetail(id: String, sortBy: RecordingSortOrder) async -> Song? {
        // Build URL with sort parameter
        guard let url = URL(string: "\(Self.baseURL)/songs/\(id)?sort=\(sortBy.rawValue)") else {
            print("Invalid URL for song detail with sort parameter")
            return nil
        }
        
        do {
            let (data, response) = try await URLSession.shared.data(from: url)
            
            // Check for HTTP errors
            if let httpResponse = response as? HTTPURLResponse {
                guard (200...299).contains(httpResponse.statusCode) else {
                    print("HTTP error: \(httpResponse.statusCode)")
                    return nil
                }
            }
            
            let decoder = JSONDecoder()
            let song = try decoder.decode(Song.self, from: data)
            return song
        } catch {
            print("Error fetching song detail with sort: \(error)")
            if let decodingError = error as? DecodingError {
                print("Decoding error details: \(decodingError)")
            }
            return nil
        }
    }
    
    /// Fetch song detail without sort parameter (uses backend default)
    func fetchSongDetail(id: String) async -> Song? {
        // Default to authority sort
        return await fetchSongDetail(id: id, sortBy: .year)
    }

    // USAGE IN SongDetailView:
    //
    // Task {
    //     isLoading = true
    //     if let updatedSong = await NetworkManager().fetchSongDetail(id: songId, sortBy: sortOrder) {
    //         song = updatedSong
    //     }
    //     isLoading = false
    // }
    //
    // This will hit the backend with: GET /api/songs/{id}?sort=authority
    //                              or: GET /api/songs/{id}?sort=year
    //                              or: GET /api/songs/{id}?sort=canonical
    
    // MARK: - Solo Transcriptions
    
    func fetchSongTranscriptions(songId: String) async -> [SoloTranscription] {
        #if DEBUG
        if Self.isPreviewMode {
            return [.preview1, .preview2]
        }
        #endif
        
        guard let url = URL(string: "\(NetworkManager.baseURL)/songs/\(songId)/transcriptions") else {
            return []
        }
        
        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            let transcriptions = try JSONDecoder().decode([SoloTranscription].self, from: data)
            return transcriptions
        } catch {
            print("Error fetching song transcriptions: \(error)")
            return []
        }
    }
    
    func fetchRecordingTranscriptions(recordingId: String) async -> [SoloTranscription] {
        #if DEBUG
        if Self.isPreviewMode {
            return [.preview1]
        }
        #endif
        
        guard let url = URL(string: "\(NetworkManager.baseURL)/recordings/\(recordingId)/transcriptions") else {
            return []
        }
        
        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            let transcriptions = try JSONDecoder().decode([SoloTranscription].self, from: data)
            return transcriptions
        } catch {
            print("Error fetching recording transcriptions: \(error)")
            return []
        }
    }
    
    func fetchTranscriptionDetail(id: String) async -> SoloTranscription? {
        #if DEBUG
        if Self.isPreviewMode {
            switch id {
            case "preview-transcription-1":
                return .preview1
            case "preview-transcription-2":
                return .preview2
            case "preview-transcription-3":
                return .previewMinimal
            default:
                return .preview1
            }
        }
        #endif
        
        guard let url = URL(string: "\(NetworkManager.baseURL)/transcriptions/\(id)") else {
            return nil
        }
        
        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            let transcription = try JSONDecoder().decode(SoloTranscription.self, from: data)
            return transcription
        } catch {
            print("Error fetching transcription detail: \(error)")
            return nil
        }
    }
    
    // MARK: - Recordings

    /// Total count of recordings in the database (fetched separately for performance)
    @Published var recordingsCount: Int = 0

    /// Fetch total recordings count (lightweight endpoint)
    func fetchRecordingsCount() async {
        guard let url = URL(string: "\(NetworkManager.baseURL)/recordings/count") else {
            return
        }

        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            if let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
               let count = json["count"] as? Int {
                await MainActor.run {
                    self.recordingsCount = count
                }
            }
        } catch {
            // Silently fail - count is just for display
        }
    }

    /// Fetch recordings with search query (search required due to large dataset)
    /// Search matches against artist name, album title, or song title
    /// - Parameter searchQuery: Search string (required - empty string clears results)
    func fetchRecordings(searchQuery: String = "") async {
        let startTime = Date()

        // If no search query, clear results (dataset too large to load all)
        if searchQuery.isEmpty {
            await MainActor.run {
                self.recordings = []
                self.isLoading = false
            }
            return
        }

        await MainActor.run {
            isLoading = true
            errorMessage = nil
        }

        let urlString = "\(NetworkManager.baseURL)/recordings?search=\(searchQuery.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? "")"

        guard let url = URL(string: urlString) else {
            await MainActor.run {
                errorMessage = "Invalid URL"
                isLoading = false
            }
            return
        }

        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            let decodedRecordings = try JSONDecoder().decode([Recording].self, from: data)

            await MainActor.run {
                self.recordings = decodedRecordings
                self.isLoading = false
            }
            NetworkManager.logRequest("GET /recordings?search=...", startTime: startTime)

            if NetworkManager.diagnosticsEnabled {
                print("   ↳ Returned \(decodedRecordings.count) recordings")
            }
        } catch {
            await MainActor.run {
                self.errorMessage = "Failed to fetch recordings: \(error.localizedDescription)"
                self.isLoading = false
            }
        }
    }
    
    // MARK: - Preview Mode (DEBUG only)
    
    #if DEBUG
    func fetchSongTranscriptionsSync(songId: String) -> [SoloTranscription] {
        if Self.isPreviewMode {
            return [.preview1, .preview2]
        }
        return []
    }
    
    func fetchRecordingTranscriptionsSync(recordingId: String) -> [SoloTranscription] {
        if Self.isPreviewMode {
            return [.preview1]
        }
        return []
    }
    
    func fetchTranscriptionDetailSync(id: String) -> SoloTranscription? {
        if Self.isPreviewMode {
            switch id {
            case "preview-transcription-1":
                return .preview1
            case "preview-transcription-2":
                return .preview2
            case "preview-transcription-3":
                return .previewMinimal
            default:
                return .preview1
            }
        }
        return nil
    }
    #endif
}

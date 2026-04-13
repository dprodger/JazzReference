import Foundation

// MARK: - Content Service Response Types

/// Response from adding a manual streaming link
struct ManualStreamingLinkResponse: Codable {
    let success: Bool
    let service: String?
    let trackId: String?
    let trackUrl: String?
    let error: String?

    enum CodingKeys: String, CodingKey {
        case success
        case service
        case trackId = "track_id"
        case trackUrl = "track_url"
        case error
    }
}

// MARK: - Content Service

@MainActor
class ContentService {

    // MARK: - Transcriptions

    func fetchTranscriptionDetail(id: String) async -> SoloTranscription? {
        #if DEBUG
        if APIClient.isPreviewMode {
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

        let url = URL.api(path: "/transcriptions/\(id)")

        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            let transcription = try JSONDecoder().decode(SoloTranscription.self, from: data)
            return transcription
        } catch {
            print("Error fetching transcription detail: \(error)")
            return nil
        }
    }

    #if DEBUG
    func fetchTranscriptionDetailSync(id: String) -> SoloTranscription? {
        if APIClient.isPreviewMode {
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

    /// Create a new transcription
    func createTranscription(songId: String, recordingId: String?, youtubeUrl: String, userId: String? = nil) async throws {
        let url = URL.api(path: "/transcriptions")

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        var body: [String: Any] = [
            "song_id": songId,
            "youtube_url": youtubeUrl
        ]
        if let recordingId = recordingId {
            body["recording_id"] = recordingId
        }
        if let userId = userId {
            body["created_by"] = userId
        }

        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw URLError(.badServerResponse)
        }

        if httpResponse.statusCode >= 400 {
            if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let error = json["error"] as? String {
                throw NSError(domain: "APIError", code: httpResponse.statusCode, userInfo: [NSLocalizedDescriptionKey: error])
            }
            throw URLError(.badServerResponse)
        }
    }

    // MARK: - Videos

    /// Create a new video (backing track)
    func createVideo(songId: String, youtubeUrl: String, videoType: String, title: String, tempo: Int? = nil, keySignature: String? = nil, userId: String? = nil) async throws {
        let url = URL.api(path: "/videos")

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        var body: [String: Any] = [
            "song_id": songId,
            "youtube_url": youtubeUrl,
            "video_type": videoType,
            "title": title
        ]
        if let tempo = tempo {
            body["tempo"] = tempo
        }
        if let keySignature = keySignature {
            body["key_signature"] = keySignature
        }
        if let userId = userId {
            body["created_by"] = userId
        }

        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw URLError(.badServerResponse)
        }

        if httpResponse.statusCode >= 400 {
            if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let error = json["error"] as? String {
                throw NSError(domain: "APIError", code: httpResponse.statusCode, userInfo: [NSLocalizedDescriptionKey: error])
            }
            throw URLError(.badServerResponse)
        }
    }

    /// Fetch videos for a song
    func fetchSongVideos(songId: String, videoType: String? = nil) async throws -> [Video] {
        var path = "/songs/\(songId)/videos"
        if let videoType = videoType {
            path += "?type=\(videoType)"
        }

        let url = URL.api(path: path)

        let (data, response) = try await URLSession.shared.data(from: url)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw URLError(.badServerResponse)
        }

        if httpResponse.statusCode >= 400 {
            throw URLError(.badServerResponse)
        }

        let decoder = JSONDecoder()
        return try decoder.decode([Video].self, from: data)
    }

    // MARK: - Content Reports

    /// Submit a content error report to the API
    static func submitContentReport(
        entityType: String,
        entityId: String,
        entityName: String,
        externalSource: String,
        externalUrl: String,
        explanation: String
    ) async throws -> Bool {
        let url = URL.api(path: "/content-reports")

        let requestBody: [String: Any] = [
            "entity_type": entityType,
            "entity_id": entityId,
            "entity_name": entityName,
            "external_source": externalSource,
            "external_url": externalUrl,
            "explanation": explanation,
            "reporter_platform": "ios",
            "reporter_app_version": Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0"
        ]

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: requestBody)

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            return false
        }

        if (200...299).contains(httpResponse.statusCode) {
            return true
        } else {
            if let errorDict = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let errorMessage = errorDict["error"] as? String {
                print("API Error submitting content report: \(errorMessage)")
            }
            return false
        }
    }

    // MARK: - Authority Recommendations

    func fetchAuthorityRecommendations(songId: String) async -> AuthorityRecommendationsResponse? {
        let url = URL.api(path: "/songs/\(songId)/authority_recommendations")

        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            let response = try JSONDecoder().decode(AuthorityRecommendationsResponse.self, from: data)
            return response
        } catch {
            print("Error fetching authority recommendations: \(error)")
            return nil
        }
    }

    // MARK: - Manual Streaming Links

    /// Add a manual streaming link for a recording on a specific release
    func addManualStreamingLink(
        recordingId: String,
        releaseId: String,
        url: String,
        notes: String? = nil,
        authToken: String
    ) async -> ManualStreamingLinkResponse? {
        let startTime = Date()
        let apiUrl = URL.api(path: "/recordings/\(recordingId)/releases/\(releaseId)/streaming-link")

        var request = URLRequest(url: apiUrl)
        request.httpMethod = "POST"
        request.setValue("Bearer \(authToken)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        var body: [String: Any] = ["url": url]
        if let notes = notes, !notes.isEmpty {
            body["notes"] = notes
        }

        do {
            request.httpBody = try JSONSerialization.data(withJSONObject: body)
            let (data, response) = try await URLSession.shared.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                return nil
            }

            APIClient.logRequest("POST /recordings/\(recordingId)/releases/\(releaseId)/streaming-link", startTime: startTime)

            if (200...299).contains(httpResponse.statusCode) {
                let linkResponse = try JSONDecoder().decode(ManualStreamingLinkResponse.self, from: data)
                if APIClient.diagnosticsEnabled {
                    print("   \u{21B3} Added \(linkResponse.service ?? "unknown") link: \(linkResponse.trackId ?? "?")")
                }
                return linkResponse
            } else {
                if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   let error = json["error"] as? String {
                    return ManualStreamingLinkResponse(success: false, service: nil, trackId: nil, trackUrl: nil, error: error)
                }
                print("Error adding streaming link: HTTP \(httpResponse.statusCode)")
                return ManualStreamingLinkResponse(success: false, service: nil, trackId: nil, trackUrl: nil, error: "HTTP \(httpResponse.statusCode)")
            }
        } catch {
            print("Error adding streaming link: \(error)")
            return ManualStreamingLinkResponse(success: false, service: nil, trackId: nil, trackUrl: nil, error: error.localizedDescription)
        }
    }
}

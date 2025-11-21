// MARK: - Network Manager
import SwiftUI
import Combine

class NetworkManager: ObservableObject {
    static let baseURL = "https://www.linernotesjazz.com/api"
    @Published var songs: [Song] = []
    @Published var performers: [Performer] = []
    @Published var isLoading = false
    @Published var errorMessage: String?
    
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
    
    // MARK: - NEW: Add Song to Repertoire
    
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
    func fetchQueueStatus() async -> (queueSize: Int, workerActive: Bool)? {
        let startTime = Date()
        guard let url = URL(string: "\(NetworkManager.baseURL)/research/queue") else {
            print("Error: Invalid queue status URL")
            return nil
        }
        
        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
            
            NetworkManager.logRequest("GET /research/queue", startTime: startTime)
            
            if let queueSize = json?["queue_size"] as? Int,
               let workerActive = json?["worker_active"] as? Bool {
                return (queueSize, workerActive)
            }
            return nil
        } catch {
            print("Error fetching queue status: \(error.localizedDescription)")
            return nil
        }
    }
}
// MARK: - NetworkManager Extensions for Solo Transcriptions

extension NetworkManager {
    
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
}

// MARK: - Preview Mode Extension for Sync Methods

#if DEBUG
extension NetworkManager {
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
}
#endif

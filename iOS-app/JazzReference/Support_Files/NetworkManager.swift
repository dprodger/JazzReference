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
    static let baseURL = "https://api.approachnote.com"
    @Published var songs: [Song] = []
    @Published var performers: [Performer] = []
    @Published var isLoading = false
    @Published var errorMessage: String?
    @Published var recordings: [Recording] = []

    // MARK: - Performers Pagination State
    @Published var performersIndex: [Performer] = []  // Lightweight index for alphabet nav
    @Published var hasMorePerformers = true
    @Published var isLoadingMorePerformers = false
    private var performersTotalCount = 0
    private var currentPerformersOffset = 0
    private let performersPageSize = 500
    
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

            // Check if cancelled before updating UI (avoids race with newer request)
            guard !Task.isCancelled else { return }

            await MainActor.run {
                self.songs = decodedSongs
                self.isLoading = false
            }
            NetworkManager.logRequest("GET /songs\(searchQuery.isEmpty ? "" : "?search=...")", startTime: startTime)
        } catch is CancellationError {
            // Task was cancelled (user typed again) - silently ignore
            return
        } catch let error as NSError where error.code == NSURLErrorCancelled {
            // URLSession request was cancelled - silently ignore
            return
        } catch {
            // Only show error if this task wasn't cancelled
            guard !Task.isCancelled else { return }
            await MainActor.run {
                self.errorMessage = "Failed to fetch songs: \(error.localizedDescription)"
                self.isLoading = false
            }
        }
    }

    /// Fetch lightweight performer index for display and alphabet navigation
    /// Returns only id, name, sort_name - fast to load all 30k performers
    func fetchPerformersIndex(searchQuery: String = "") async {
        let startTime = Date()
        await MainActor.run {
            isLoading = true
            errorMessage = nil
        }

        var urlString = "\(NetworkManager.baseURL)/performers/index"
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

            guard !Task.isCancelled else { return }

            await MainActor.run {
                self.performersIndex = decodedPerformers
                self.isLoading = false
            }
            NetworkManager.logRequest("GET /performers/index\(searchQuery.isEmpty ? "" : "?search=...")", startTime: startTime)
        } catch is CancellationError {
            return
        } catch let error as NSError where error.code == NSURLErrorCancelled {
            return
        } catch {
            guard !Task.isCancelled else { return }
            await MainActor.run {
                self.errorMessage = "Failed to fetch performers: \(error.localizedDescription)"
                self.isLoading = false
            }
        }
    }

    /// Fetch performers with pagination - initial load or after search change
    func fetchPerformers(searchQuery: String = "") async {
        let startTime = Date()
        await MainActor.run {
            isLoading = true
            errorMessage = nil
            // Reset pagination state for fresh load
            currentPerformersOffset = 0
            hasMorePerformers = true
            performers = []
        }

        var urlString = "\(NetworkManager.baseURL)/performers?limit=\(performersPageSize)&offset=0"
        if !searchQuery.isEmpty {
            urlString += "&search=\(searchQuery.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? "")"
        }

        guard let url = URL(string: urlString) else {
            await MainActor.run {
                errorMessage = "Invalid URL"
                isLoading = false
            }
            return
        }

        do {
            let (data, response) = try await URLSession.shared.data(from: url)
            let decodedPerformers = try JSONDecoder().decode([Performer].self, from: data)

            // Parse pagination headers
            var totalCount = decodedPerformers.count
            var hasMore = false
            if let httpResponse = response as? HTTPURLResponse {
                if let totalCountHeader = httpResponse.value(forHTTPHeaderField: "X-Total-Count"),
                   let count = Int(totalCountHeader) {
                    totalCount = count
                }
                if let hasMoreHeader = httpResponse.value(forHTTPHeaderField: "X-Has-More") {
                    hasMore = hasMoreHeader == "true"
                }
            }

            guard !Task.isCancelled else { return }

            await MainActor.run {
                self.performers = decodedPerformers
                self.performersTotalCount = totalCount
                self.hasMorePerformers = hasMore
                self.currentPerformersOffset = decodedPerformers.count
                self.isLoading = false
            }
            NetworkManager.logRequest("GET /performers?limit=\(performersPageSize)&offset=0\(searchQuery.isEmpty ? "" : "&search=...")", startTime: startTime)
        } catch is CancellationError {
            return
        } catch let error as NSError where error.code == NSURLErrorCancelled {
            return
        } catch {
            guard !Task.isCancelled else { return }
            await MainActor.run {
                self.errorMessage = "Failed to fetch performers: \(error.localizedDescription)"
                self.isLoading = false
            }
        }
    }

    /// Load next page of performers for infinite scroll
    func loadMorePerformers(searchQuery: String = "") async {
        // Don't load if already loading or no more data
        guard !isLoadingMorePerformers && hasMorePerformers else { return }

        let startTime = Date()
        await MainActor.run {
            isLoadingMorePerformers = true
        }

        var urlString = "\(NetworkManager.baseURL)/performers?limit=\(performersPageSize)&offset=\(currentPerformersOffset)"
        if !searchQuery.isEmpty {
            urlString += "&search=\(searchQuery.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? "")"
        }

        guard let url = URL(string: urlString) else {
            await MainActor.run {
                isLoadingMorePerformers = false
            }
            return
        }

        do {
            let (data, response) = try await URLSession.shared.data(from: url)
            let decodedPerformers = try JSONDecoder().decode([Performer].self, from: data)

            // Parse pagination headers
            var hasMore = false
            if let httpResponse = response as? HTTPURLResponse {
                if let hasMoreHeader = httpResponse.value(forHTTPHeaderField: "X-Has-More") {
                    hasMore = hasMoreHeader == "true"
                }
            }

            guard !Task.isCancelled else { return }

            await MainActor.run {
                self.performers.append(contentsOf: decodedPerformers)
                self.hasMorePerformers = hasMore
                self.currentPerformersOffset += decodedPerformers.count
                self.isLoadingMorePerformers = false
            }
            NetworkManager.logRequest("GET /performers?limit=\(performersPageSize)&offset=\(currentPerformersOffset - decodedPerformers.count)\(searchQuery.isEmpty ? "" : "&search=...")", startTime: startTime)
        } catch is CancellationError {
            return
        } catch let error as NSError where error.code == NSURLErrorCancelled {
            return
        } catch {
            guard !Task.isCancelled else { return }
            await MainActor.run {
                self.isLoadingMorePerformers = false
            }
            print("Error loading more performers: \(error)")
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
        return await fetchPerformerDetail(id: id, sortBy: .year)
    }

    func fetchPerformerDetail(id: String, sortBy: PerformerRecordingSortOrder) async -> PerformerDetail? {
        let startTime = Date()
        guard let url = URL(string: "\(NetworkManager.baseURL)/performers/\(id)?sort=\(sortBy.rawValue)") else {
            return nil
        }

        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            let performer = try JSONDecoder().decode(PerformerDetail.self, from: data)
            NetworkManager.logRequest("GET /performers/\(id)?sort=\(sortBy.rawValue)", startTime: startTime)

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

    // MARK: - Two-Phase Performer Loading (for performance)

    /// Fetch performer summary - fast endpoint for initial page load
    /// Returns performer metadata, instruments, images, and recording count - NO recordings
    func fetchPerformerSummary(id: String) async -> PerformerDetail? {
        let startTime = Date()
        guard let url = URL(string: "\(NetworkManager.baseURL)/performers/\(id)/summary") else {
            print("Invalid URL for performer summary")
            return nil
        }

        do {
            let (data, response) = try await URLSession.shared.data(from: url)

            if let httpResponse = response as? HTTPURLResponse {
                guard (200...299).contains(httpResponse.statusCode) else {
                    print("HTTP error fetching performer summary: \(httpResponse.statusCode)")
                    return nil
                }
            }

            let decoder = JSONDecoder()
            let performer = try decoder.decode(PerformerDetail.self, from: data)
            NetworkManager.logRequest("GET /performers/\(id)/summary", startTime: startTime)

            if NetworkManager.diagnosticsEnabled {
                print("   ↳ Summary: \(performer.recordingCount ?? 0) total recordings")
            }
            return performer
        } catch {
            print("Error fetching performer summary: \(error)")
            if let decodingError = error as? DecodingError {
                print("Decoding error details: \(decodingError)")
            }
            return nil
        }
    }

    /// Fetch all recordings for a performer - heavier endpoint, call after summary loads
    func fetchPerformerRecordings(id: String, sortBy: PerformerRecordingSortOrder = .year) async -> [PerformerRecording]? {
        let startTime = Date()
        guard let url = URL(string: "\(NetworkManager.baseURL)/performers/\(id)/recordings?sort=\(sortBy.rawValue)") else {
            print("Invalid URL for performer recordings")
            return nil
        }

        do {
            let (data, response) = try await URLSession.shared.data(from: url)

            if let httpResponse = response as? HTTPURLResponse {
                guard (200...299).contains(httpResponse.statusCode) else {
                    print("HTTP error fetching performer recordings: \(httpResponse.statusCode)")
                    return nil
                }
            }

            let decoder = JSONDecoder()
            let recordingsResponse = try decoder.decode(PerformerRecordingsResponse.self, from: data)
            NetworkManager.logRequest("GET /performers/\(id)/recordings", startTime: startTime)

            if NetworkManager.diagnosticsEnabled {
                print("   ↳ Loaded \(recordingsResponse.recordingCount) recordings")
            }
            return recordingsResponse.recordings
        } catch {
            print("Error fetching performer recordings: \(error)")
            if let decodingError = error as? DecodingError {
                print("Decoding error details: \(decodingError)")
            }
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
        
        // Build URL - "all" uses lightweight /songs/index endpoint, others use protected /repertoires endpoint
        var urlString: String
        if repertoireId == "all" {
            // Use the lightweight songs index endpoint (no auth required, faster loading)
            urlString = "\(NetworkManager.baseURL)/songs/index"
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

            // Check if cancelled before updating UI (avoids race with newer request)
            guard !Task.isCancelled else { return }

            await MainActor.run {
                self.songs = decodedSongs
                self.isLoading = false
            }

            let endpoint = repertoireId == "all" ?
                "GET /songs/index" :
                "GET /repertoires/\(repertoireId)/songs"
            NetworkManager.logRequest(endpoint + (searchQuery.isEmpty ? "" : "?search=..."), startTime: startTime)

            if NetworkManager.diagnosticsEnabled {
                print("   ↳ Returned \(decodedSongs.count) songs")
            }
        } catch is CancellationError {
            // Task was cancelled (user typed again) - silently ignore
            return
        } catch let error as NSError where error.code == NSURLErrorCancelled {
            // URLSession request was cancelled - silently ignore
            return
        } catch {
            // Only show error if this task wasn't cancelled
            guard !Task.isCancelled else { return }
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

    // MARK: - Two-Phase Song Loading (for performance)

    /// Fetch song summary - fast endpoint for initial page load
    /// Returns song metadata, transcriptions, and only featured (authoritative) recordings
    func fetchSongSummary(id: String) async -> Song? {
        let startTime = Date()
        guard let url = URL(string: "\(Self.baseURL)/songs/\(id)/summary") else {
            print("Invalid URL for song summary")
            return nil
        }

        do {
            let (data, response) = try await URLSession.shared.data(from: url)

            if let httpResponse = response as? HTTPURLResponse {
                guard (200...299).contains(httpResponse.statusCode) else {
                    print("HTTP error fetching song summary: \(httpResponse.statusCode)")
                    return nil
                }
            }

            let decoder = JSONDecoder()
            let song = try decoder.decode(Song.self, from: data)
            NetworkManager.logRequest("GET /songs/\(id)/summary", startTime: startTime)

            if NetworkManager.diagnosticsEnabled {
                print("   ↳ Summary: \(song.featuredRecordings?.count ?? 0) featured recordings, \(song.recordingCount ?? 0) total")
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

    /// Fetch all recordings for a song - heavier endpoint, call after summary loads
    func fetchSongRecordings(id: String, sortBy: RecordingSortOrder = .year) async -> [Recording]? {
        let startTime = Date()
        guard let url = URL(string: "\(Self.baseURL)/songs/\(id)/recordings?sort=\(sortBy.rawValue)") else {
            print("Invalid URL for song recordings")
            return nil
        }

        do {
            let (data, response) = try await URLSession.shared.data(from: url)

            if let httpResponse = response as? HTTPURLResponse {
                guard (200...299).contains(httpResponse.statusCode) else {
                    print("HTTP error fetching song recordings: \(httpResponse.statusCode)")
                    return nil
                }
            }

            let decoder = JSONDecoder()
            let recordingsResponse = try decoder.decode(SongRecordingsResponse.self, from: data)
            NetworkManager.logRequest("GET /songs/\(id)/recordings", startTime: startTime)

            if NetworkManager.diagnosticsEnabled {
                print("   ↳ Loaded \(recordingsResponse.recordingCount) recordings")
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

    // MARK: - Song Search

    func searchSongs(query: String) async throws -> [Song] {
        let encodedQuery = query.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? query
        guard let url = URL(string: "\(NetworkManager.baseURL)/songs?search=\(encodedQuery)&limit=20") else {
            throw URLError(.badURL)
        }

        let (data, response) = try await URLSession.shared.data(from: url)

        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw URLError(.badServerResponse)
        }

        let decoder = JSONDecoder()
        let songs = try decoder.decode([Song].self, from: data)
        return songs
    }

    // MARK: - Create Transcription

    func createTranscription(songId: String, recordingId: String, youtubeUrl: String) async throws {
        guard let url = URL(string: "\(NetworkManager.baseURL)/transcriptions") else {
            throw URLError(.badURL)
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body: [String: Any] = [
            "song_id": songId,
            "recording_id": recordingId,
            "youtube_url": youtubeUrl
        ]

        request.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw URLError(.badServerResponse)
        }

        if httpResponse.statusCode >= 400 {
            // Try to extract error message from response
            if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let error = json["error"] as? String {
                throw NSError(domain: "APIError", code: httpResponse.statusCode, userInfo: [NSLocalizedDescriptionKey: error])
            }
            throw URLError(.badServerResponse)
        }
    }

    // MARK: - Create Video

    func createVideo(songId: String, youtubeUrl: String, videoType: String, title: String) async throws {
        guard let url = URL(string: "\(NetworkManager.baseURL)/videos") else {
            throw URLError(.badURL)
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body: [String: Any] = [
            "song_id": songId,
            "youtube_url": youtubeUrl,
            "video_type": videoType,
            "title": title
        ]

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

            // Check if cancelled before updating UI (avoids race with newer request)
            guard !Task.isCancelled else { return }

            await MainActor.run {
                self.recordings = decodedRecordings
                self.isLoading = false
            }
            NetworkManager.logRequest("GET /recordings?search=...", startTime: startTime)

            if NetworkManager.diagnosticsEnabled {
                print("   ↳ Returned \(decodedRecordings.count) recordings")
            }
        } catch is CancellationError {
            // Task was cancelled (user typed again) - silently ignore
            return
        } catch let error as NSError where error.code == NSURLErrorCancelled {
            // URLSession request was cancelled - silently ignore
            return
        } catch {
            // Only show error if this task wasn't cancelled
            guard !Task.isCancelled else { return }
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

    // MARK: - Content Reports

    /// Submit a content error report to the API
    /// - Parameters:
    ///   - entityType: Type of entity (e.g., "recording", "performer")
    ///   - entityId: ID of the entity
    ///   - entityName: Human-readable name of the entity
    ///   - externalSource: Source being reported (e.g., "spotify", "wikipedia")
    ///   - externalUrl: The URL being reported as incorrect
    ///   - explanation: User's explanation of the issue
    /// - Returns: True if report was submitted successfully
    static func submitContentReport(
        entityType: String,
        entityId: String,
        entityName: String,
        externalSource: String,
        externalUrl: String,
        explanation: String
    ) async throws -> Bool {
        guard let url = URL(string: "\(baseURL)/content-reports") else {
            throw URLError(.badURL)
        }

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
            // Log error for debugging
            if let errorDict = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let errorMessage = errorDict["error"] as? String {
                print("API Error submitting content report: \(errorMessage)")
            }
            return false
        }
    }
}

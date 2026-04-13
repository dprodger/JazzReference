// MARK: - Performer Recording Sort Order Enum
enum PerformerRecordingSortOrder: String, CaseIterable, Identifiable {
    case year = "year"
    case name = "name"

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .year: return "Year"
        case .name: return "Song"
        }
    }
}

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

/// Represents a song waiting in the research queue
struct QueuedSong: Codable, Identifiable {
    let songId: String
    let songName: String

    var id: String { songId }

    enum CodingKeys: String, CodingKey {
        case songId = "song_id"
        case songName = "song_name"
    }
}

/// Response wrapper for /research/queue/items endpoint
private struct QueuedSongsResponse: Codable {
    let queuedSongs: [QueuedSong]

    enum CodingKeys: String, CodingKey {
        case queuedSongs = "queued_songs"
    }
}

/// Research status for a specific song
enum SongResearchStatus {
    case notInQueue
    case inQueue(position: Int)
    case currentlyResearching(progress: ResearchProgress?)
}

// MARK: - URL Helper

extension URL {
    /// Constructs an API URL from a path relative to `NetworkManager.baseURL`.
    /// Crashes with a descriptive message instead of a generic force-unwrap failure.
    static func api(path: String) -> URL {
        guard let url = URL(string: "\(NetworkManager.baseURL)\(path)") else {
            preconditionFailure("Invalid API URL: \(NetworkManager.baseURL)\(path)")
        }
        return url
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

    // MARK: - Search Text Normalization

    /// Normalize search text by converting straight apostrophes to smart apostrophes.
    /// The database stores song titles with smart apostrophes ('), so we convert
    /// user input to match (e.g., "We'll" becomes "We'll").
    private static func normalizeSearchText(_ text: String) -> String {
        text.replacingOccurrences(of: "'", with: "\u{2019}")
    }

    // MARK: - Network Methods
    
    func fetchSongs(searchQuery: String = "") async {
        let startTime = Date()
        await MainActor.run {
            isLoading = true
            errorMessage = nil
        }
        
        var path = "/songs"
        if !searchQuery.isEmpty {
            let normalizedQuery = Self.normalizeSearchText(searchQuery)
            path += "?search=\(normalizedQuery.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? "")"
        }

        let url = URL.api(path: path)
        
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

        var path = "/performers/index"
        if !searchQuery.isEmpty {
            let normalizedQuery = Self.normalizeSearchText(searchQuery)
            path += "?search=\(normalizedQuery.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? "")"
        }

        let url = URL.api(path: path)

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

        var path = "/performers?limit=\(performersPageSize)&offset=0"
        if !searchQuery.isEmpty {
            let normalizedQuery = Self.normalizeSearchText(searchQuery)
            path += "&search=\(normalizedQuery.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? "")"
        }

        let url = URL.api(path: path)

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

        var path = "/performers?limit=\(performersPageSize)&offset=\(currentPerformersOffset)"
        if !searchQuery.isEmpty {
            let normalizedQuery = Self.normalizeSearchText(searchQuery)
            path += "&search=\(normalizedQuery.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? "")"
        }

        let url = URL.api(path: path)

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
        let url = URL.api(path: "/recordings/\(id)")
        
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
        let url = URL.api(path: "/performers/\(id)?sort=\(sortBy.rawValue)")

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
        let url = URL.api(path: "/performers/\(id)/summary")

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
        let url = URL.api(path: "/performers/\(id)/recordings?sort=\(sortBy.rawValue)")

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
        let url = URL.api(path: "/repertoires")
        
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
        var path: String
        if repertoireId == "all" {
            // Use the lightweight songs index endpoint (no auth required, faster loading)
            path = "/songs/index"
        } else {
            // Use the protected repertoire endpoint (requires auth)
            path = "/repertoires/\(repertoireId)/songs"
        }

        // Add search query if present
        if !searchQuery.isEmpty {
            let normalizedQuery = Self.normalizeSearchText(searchQuery)
            path += "?search=\(normalizedQuery.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? "")"
        }

        let url = URL.api(path: path)
        
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
        let url = URL.api(path: "/repertoires/\(repertoireId)/songs")
        
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
        
    /// Queue a song for background research to update its data from external sources
    /// - Parameters:
    ///   - songId: The UUID of the song to refresh
    ///   - forceRefresh: If true (default), bypass cache and re-fetch all data ("deep refresh").
    ///                   If false, use cached data where available ("quick refresh").
    /// - Returns: True if successfully queued, false otherwise
    func refreshSongData(songId: String, forceRefresh: Bool = true) async -> Bool {
        let forceRefreshParam = forceRefresh ? "true" : "false"
        let url = URL.api(path: "/songs/\(songId)/refresh?force_refresh=\(forceRefreshParam)")
        
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
                    let refreshType = forceRefresh ? "deep" : "quick"
                    if let queueSize = json["queue_size"] as? Int {
                        print("✓ Song queued for \(refreshType) refresh (queue size: \(queueSize))")
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
        let url = URL.api(path: "/research/queue")
        
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
    
    /// Fetch the list of songs currently in the research queue
    func fetchQueuedSongs() async -> [QueuedSong] {
        let startTime = Date()
        let url = URL.api(path: "/research/queue/items")

        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            let response = try JSONDecoder().decode(QueuedSongsResponse.self, from: data)

            NetworkManager.logRequest("GET /research/queue/items", startTime: startTime)

            if NetworkManager.diagnosticsEnabled {
                print("   ↳ Queued songs: \(response.queuedSongs.count)")
            }

            return response.queuedSongs
        } catch {
            print("Error fetching queued songs: \(error.localizedDescription)")
            return []
        }
    }

    /// Check the research status for a specific song
    /// - Parameter songId: The song ID to check
    /// - Returns: The research status (not in queue, in queue with position, or currently researching)
    func checkSongResearchStatus(songId: String) async -> SongResearchStatus {
        // Fetch both queue status and queued items in parallel
        async let queueStatusTask = fetchQueueStatus()
        async let queuedSongsTask = fetchQueuedSongs()

        let (queueStatus, queuedSongs) = await (queueStatusTask, queuedSongsTask)

        // Check if this song is currently being researched
        if let current = queueStatus?.currentSong, current.songId == songId {
            return .currentlyResearching(progress: queueStatus?.progress)
        }

        // Check if this song is in the queue
        if let position = queuedSongs.firstIndex(where: { $0.songId == songId }) {
            return .inQueue(position: position + 1) // 1-indexed position
        }

        return .notInQueue
    }

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
    
    func fetchSongDetail(id: String, sortBy: RecordingSortOrder) async -> Song? {
        // Build URL with sort parameter
        let url = URL.api(path: "/songs/\(id)?sort=\(sortBy.rawValue)")

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
        let url = URL.api(path: "/songs/\(id)/summary")

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
        let url = URL.api(path: "/songs/\(id)/recordings?sort=\(sortBy.rawValue)")

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
        
        let url = URL.api(path: "/songs/\(songId)/transcriptions")
        
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
        
        let url = URL.api(path: "/recordings/\(recordingId)/transcriptions")
        
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

    // MARK: - Song Search

    func searchSongs(query: String) async throws -> [Song] {
        let encodedQuery = query.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? query
        let url = URL.api(path: "/songs?search=\(encodedQuery)&limit=20")

        let (data, response) = try await URLSession.shared.data(from: url)

        guard let httpResponse = response as? HTTPURLResponse, httpResponse.statusCode == 200 else {
            throw URLError(.badServerResponse)
        }

        let decoder = JSONDecoder()
        let songs = try decoder.decode([Song].self, from: data)
        return songs
    }

    // MARK: - Create Transcription

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
            // Try to extract error message from response
            if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let error = json["error"] as? String {
                throw NSError(domain: "APIError", code: httpResponse.statusCode, userInfo: [NSLocalizedDescriptionKey: error])
            }
            throw URLError(.badServerResponse)
        }
    }

    // MARK: - Create Video

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

    // MARK: - Fetch Song Videos

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

    // MARK: - Recordings

    /// Total count of recordings in the database (fetched separately for performance)
    @Published var recordingsCount: Int = 0

    /// Fetch total recordings count (lightweight endpoint)
    func fetchRecordingsCount() async {
        let url = URL.api(path: "/recordings/count")

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

        let normalizedQuery = Self.normalizeSearchText(searchQuery)
        let url = URL.api(path: "/recordings?search=\(normalizedQuery.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? "")")

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
            // Log error for debugging
            if let errorDict = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let errorMessage = errorDict["error"] as? String {
                print("API Error submitting content report: \(errorMessage)")
            }
            return false
        }
    }

    // MARK: - Favorites API

    /// Response from /favorites endpoint (user's favorited recordings)
    struct FavoriteRecordingResponse: Codable {
        let id: String
        let songTitle: String?
        let albumTitle: String?
        let recordingYear: Int?
        let bestAlbumArtSmall: String?
        let favoritedAt: String?

        enum CodingKeys: String, CodingKey {
            case id
            case songTitle = "song_title"
            case albumTitle = "album_title"
            case recordingYear = "recording_year"
            case bestAlbumArtSmall = "best_album_art_small"
            case favoritedAt = "favorited_at"
        }
    }

    /// Response from POST/DELETE /recordings/{id}/favorite
    struct FavoriteToggleResponse: Codable {
        let message: String
        let favoriteCount: Int

        enum CodingKeys: String, CodingKey {
            case message
            case favoriteCount = "favorite_count"
        }
    }

    /// Fetch the current user's favorited recordings
    /// - Parameter authToken: The user's auth token
    /// - Returns: Array of favorited recordings
    func fetchUserFavorites(authToken: String) async -> [FavoriteRecordingResponse] {
        let startTime = Date()
        let url = URL.api(path: "/favorites")

        var request = URLRequest(url: url)
        request.setValue("Bearer \(authToken)", forHTTPHeaderField: "Authorization")

        do {
            let (data, response) = try await URLSession.shared.data(for: request)

            if let httpResponse = response as? HTTPURLResponse {
                if httpResponse.statusCode == 401 {
                    print("Error: Unauthorized - user needs to re-authenticate")
                    return []
                }
                guard (200...299).contains(httpResponse.statusCode) else {
                    print("HTTP error fetching favorites: \(httpResponse.statusCode)")
                    return []
                }
            }

            let favorites = try JSONDecoder().decode([FavoriteRecordingResponse].self, from: data)
            NetworkManager.logRequest("GET /favorites", startTime: startTime)

            if NetworkManager.diagnosticsEnabled {
                print("   ↳ Returned \(favorites.count) favorites")
            }
            return favorites
        } catch {
            print("Error fetching favorites: \(error)")
            return []
        }
    }

    /// Add a recording to the user's favorites
    /// - Parameters:
    ///   - recordingId: The recording ID to favorite
    ///   - authToken: The user's auth token
    /// - Returns: The new favorite count, or nil on error
    func addFavorite(recordingId: String, authToken: String) async -> Int? {
        let startTime = Date()
        let url = URL.api(path: "/recordings/\(recordingId)/favorite")

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(authToken)", forHTTPHeaderField: "Authorization")

        do {
            let (data, response) = try await URLSession.shared.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                return nil
            }

            NetworkManager.logRequest("POST /recordings/\(recordingId)/favorite", startTime: startTime)

            if httpResponse.statusCode == 201 {
                let toggleResponse = try JSONDecoder().decode(FavoriteToggleResponse.self, from: data)
                if NetworkManager.diagnosticsEnabled {
                    print("   ↳ \(toggleResponse.message), count: \(toggleResponse.favoriteCount)")
                }
                return toggleResponse.favoriteCount
            } else if httpResponse.statusCode == 409 {
                print("Recording already favorited")
                return nil
            } else if httpResponse.statusCode == 401 {
                print("Error: Unauthorized")
                return nil
            } else {
                print("Error adding favorite: HTTP \(httpResponse.statusCode)")
                return nil
            }
        } catch {
            print("Error adding favorite: \(error)")
            return nil
        }
    }

    /// Remove a recording from the user's favorites
    /// - Parameters:
    ///   - recordingId: The recording ID to unfavorite
    ///   - authToken: The user's auth token
    /// - Returns: The new favorite count, or nil on error
    func removeFavorite(recordingId: String, authToken: String) async -> Int? {
        let startTime = Date()
        let url = URL.api(path: "/recordings/\(recordingId)/favorite")

        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"
        request.setValue("Bearer \(authToken)", forHTTPHeaderField: "Authorization")

        do {
            let (data, response) = try await URLSession.shared.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                return nil
            }

            NetworkManager.logRequest("DELETE /recordings/\(recordingId)/favorite", startTime: startTime)

            if httpResponse.statusCode == 200 {
                let toggleResponse = try JSONDecoder().decode(FavoriteToggleResponse.self, from: data)
                if NetworkManager.diagnosticsEnabled {
                    print("   ↳ \(toggleResponse.message), count: \(toggleResponse.favoriteCount)")
                }
                return toggleResponse.favoriteCount
            } else if httpResponse.statusCode == 404 {
                print("Recording not in favorites")
                return nil
            } else if httpResponse.statusCode == 401 {
                print("Error: Unauthorized")
                return nil
            } else {
                print("Error removing favorite: HTTP \(httpResponse.statusCode)")
                return nil
            }
        } catch {
            print("Error removing favorite: \(error)")
            return nil
        }
    }

    // MARK: - Recording Contributions API

    /// Response from contribution endpoints
    struct ContributionResponse: Codable {
        let consensus: CommunityConsensus
        let counts: ContributionCounts
        let userContribution: UserContribution?
        let message: String?

        enum CodingKeys: String, CodingKey {
            case consensus, counts, message
            case userContribution = "user_contribution"
        }
    }

    /// Save user's contribution for a recording (creates or updates)
    /// - Parameters:
    ///   - recordingId: The recording ID
    ///   - key: Performance key (e.g., "Eb", "C") or nil to clear
    ///   - tempo: Tempo in BPM (40-400) or nil to clear
    ///   - isInstrumental: Whether recording is instrumental, or nil to clear
    ///   - authToken: The user's auth token
    /// - Returns: Updated contribution response, or nil on error
    func saveRecordingContribution(
        recordingId: String,
        key: String?,
        tempo: Int?,
        isInstrumental: Bool?,
        authToken: String
    ) async -> ContributionResponse? {
        let startTime = Date()
        let url = URL.api(path: "/recordings/\(recordingId)/contribution")

        var request = URLRequest(url: url)
        request.httpMethod = "PUT"
        request.setValue("Bearer \(authToken)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        // Build request body with only non-nil values
        var body: [String: Any] = [:]
        if let key = key { body["performance_key"] = key }
        if let tempo = tempo { body["tempo_bpm"] = tempo }
        if let isInstrumental = isInstrumental { body["is_instrumental"] = isInstrumental }

        do {
            request.httpBody = try JSONSerialization.data(withJSONObject: body)
            let (data, response) = try await URLSession.shared.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                return nil
            }

            NetworkManager.logRequest("PUT /recordings/\(recordingId)/contribution", startTime: startTime)

            if (200...299).contains(httpResponse.statusCode) {
                let contributionResponse = try JSONDecoder().decode(ContributionResponse.self, from: data)
                if NetworkManager.diagnosticsEnabled {
                    print("   ↳ Saved contribution, key_count: \(contributionResponse.counts.key)")
                }
                return contributionResponse
            } else if httpResponse.statusCode == 401 {
                print("Error: Unauthorized")
                return nil
            } else if httpResponse.statusCode == 400 {
                if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   let error = json["error"] as? String {
                    print("Validation error: \(error)")
                }
                return nil
            } else {
                print("Error saving contribution: HTTP \(httpResponse.statusCode)")
                return nil
            }
        } catch {
            print("Error saving contribution: \(error)")
            return nil
        }
    }

    /// Delete user's entire contribution for a recording
    /// - Parameters:
    ///   - recordingId: The recording ID
    ///   - authToken: The user's auth token
    /// - Returns: Updated consensus data, or nil on error
    func deleteRecordingContribution(
        recordingId: String,
        authToken: String
    ) async -> ContributionResponse? {
        let startTime = Date()
        let url = URL.api(path: "/recordings/\(recordingId)/contribution")

        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"
        request.setValue("Bearer \(authToken)", forHTTPHeaderField: "Authorization")

        do {
            let (data, response) = try await URLSession.shared.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                return nil
            }

            NetworkManager.logRequest("DELETE /recordings/\(recordingId)/contribution", startTime: startTime)

            if (200...299).contains(httpResponse.statusCode) {
                let contributionResponse = try JSONDecoder().decode(ContributionResponse.self, from: data)
                if NetworkManager.diagnosticsEnabled {
                    print("   ↳ Deleted contribution")
                }
                return contributionResponse
            } else if httpResponse.statusCode == 404 {
                print("No contribution found to delete")
                return nil
            } else if httpResponse.statusCode == 401 {
                print("Error: Unauthorized")
                return nil
            } else {
                print("Error deleting contribution: HTTP \(httpResponse.statusCode)")
                return nil
            }
        } catch {
            print("Error deleting contribution: \(error)")
            return nil
        }
    }

    // MARK: - User Contribution Stats API

    /// Response from user contribution stats endpoint
    struct UserContributionStats: Codable {
        let transcriptions: Int
        let backingTracks: Int
        let tempoMarkings: Int
        let instrumentalVocal: Int
        let keys: Int

        enum CodingKeys: String, CodingKey {
            case transcriptions
            case backingTracks = "backing_tracks"
            case tempoMarkings = "tempo_markings"
            case instrumentalVocal = "instrumental_vocal"
            case keys
        }

        /// Total number of contributions across all categories
        var totalContributions: Int {
            transcriptions + backingTracks + tempoMarkings + instrumentalVocal + keys
        }
    }

    /// Fetch contribution statistics for the current authenticated user
    /// - Parameter authToken: The user's auth token
    /// - Returns: User contribution stats, or nil on error
    func fetchUserContributionStats(authToken: String) async -> UserContributionStats? {
        let startTime = Date()
        let url = URL.api(path: "/users/me/contribution-stats")

        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("Bearer \(authToken)", forHTTPHeaderField: "Authorization")

        do {
            let (data, response) = try await URLSession.shared.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                return nil
            }

            NetworkManager.logRequest("GET /users/me/contribution-stats", startTime: startTime)

            if httpResponse.statusCode == 200 {
                let stats = try JSONDecoder().decode(UserContributionStats.self, from: data)
                if NetworkManager.diagnosticsEnabled {
                    print("   ↳ Total contributions: \(stats.totalContributions)")
                }
                return stats
            } else if httpResponse.statusCode == 401 {
                print("Error: Unauthorized")
                return nil
            } else {
                print("Error fetching contribution stats: HTTP \(httpResponse.statusCode)")
                return nil
            }
        } catch {
            print("Error fetching contribution stats: \(error)")
            return nil
        }
    }

    // MARK: - MusicBrainz Search and Import

    /// Search MusicBrainz for works (songs) by title
    /// - Parameter query: The song title to search for
    /// - Returns: Array of MusicBrainzWork results, or empty array on error
    func searchMusicBrainzWorks(query: String) async -> [MusicBrainzWork] {
        let startTime = Date()

        let encodedQuery = query.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? query
        let url = URL.api(path: "/musicbrainz/works/search?q=\(encodedQuery)")

        do {
            let (data, response) = try await URLSession.shared.data(from: url)

            guard let httpResponse = response as? HTTPURLResponse else {
                return []
            }

            NetworkManager.logRequest("GET /musicbrainz/works/search", startTime: startTime)

            if httpResponse.statusCode == 200 {
                let searchResponse = try JSONDecoder().decode(MusicBrainzSearchResponse.self, from: data)
                if NetworkManager.diagnosticsEnabled {
                    print("   ↳ Found \(searchResponse.results.count) MusicBrainz works")
                }
                return searchResponse.results
            } else {
                print("Error searching MusicBrainz: HTTP \(httpResponse.statusCode)")
                return []
            }
        } catch {
            print("Error searching MusicBrainz: \(error)")
            return []
        }
    }

    /// Import a song from MusicBrainz into the database
    /// - Parameters:
    ///   - work: The MusicBrainzWork to import
    ///   - authToken: The user's auth token (required for authentication)
    /// - Returns: The imported song response, or nil on error
    func importSongFromMusicBrainz(work: MusicBrainzWork, authToken: String) async -> MusicBrainzImportResponse? {
        let startTime = Date()

        let url = URL.api(path: "/musicbrainz/import")

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(authToken)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        // Build request body
        var body: [String: Any] = [
            "musicbrainz_id": work.id,
            "title": work.title
        ]
        if let composers = work.composers, !composers.isEmpty {
            body["composer"] = composers.joined(separator: ", ")
        }

        do {
            request.httpBody = try JSONSerialization.data(withJSONObject: body)

            let (data, response) = try await URLSession.shared.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                return nil
            }

            NetworkManager.logRequest("POST /musicbrainz/import", startTime: startTime)

            if httpResponse.statusCode == 201 {
                let importResponse = try JSONDecoder().decode(MusicBrainzImportResponse.self, from: data)
                if NetworkManager.diagnosticsEnabled {
                    print("   ↳ Imported song: \(importResponse.song?.title ?? "unknown")")
                }
                return importResponse
            } else if httpResponse.statusCode == 409 {
                // Song already exists - decode and return the error response
                print("Error: Song with this MusicBrainz ID already exists")
                // Try to decode as import response for error info
                if let errorResponse = try? JSONDecoder().decode(MusicBrainzImportResponse.self, from: data) {
                    return errorResponse
                }
                return nil
            } else {
                print("Error importing from MusicBrainz: HTTP \(httpResponse.statusCode)")
                return nil
            }
        } catch {
            print("Error importing from MusicBrainz: \(error)")
            return nil
        }
    }

    // MARK: - Manual Streaming Link Management

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

    /// Add a manual streaming link for a recording on a specific release
    /// - Parameters:
    ///   - recordingId: The recording ID
    ///   - releaseId: The release ID
    ///   - url: The Spotify or Apple Music URL/ID
    ///   - notes: Optional notes about why this link was added
    ///   - authToken: The user's auth token
    /// - Returns: Response with success status and parsed track info
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

            NetworkManager.logRequest("POST /recordings/\(recordingId)/releases/\(releaseId)/streaming-link", startTime: startTime)

            if (200...299).contains(httpResponse.statusCode) {
                let linkResponse = try JSONDecoder().decode(ManualStreamingLinkResponse.self, from: data)
                if NetworkManager.diagnosticsEnabled {
                    print("   ↳ Added \(linkResponse.service ?? "unknown") link: \(linkResponse.trackId ?? "?")")
                }
                return linkResponse
            } else {
                // Try to decode error message
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

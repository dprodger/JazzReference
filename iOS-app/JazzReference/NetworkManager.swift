// MARK: - Network Manager
import SwiftUI
import Combine

class NetworkManager: ObservableObject {
    static let baseURL = "https://jazzreference.onrender.com/api"
    
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
}


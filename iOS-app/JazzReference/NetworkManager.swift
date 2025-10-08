// MARK: - Network Manager
import SwiftUI
import Combine

class NetworkManager: ObservableObject {
    // Change this to your Flask API URL
    // For local testing: "http://localhost:5001"
    // For simulator with local Flask: "http://127.0.0.1:5001"
    static let baseURL = "https://jazzreference.onrender.com/api"
    
    @Published var songs: [Song] = []
    @Published var isLoading = false
    @Published var errorMessage: String?
    
    func fetchSongs(searchQuery: String = "") async {
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
        } catch {
            await MainActor.run {
                self.errorMessage = "Failed to fetch songs: \(error.localizedDescription)"
                self.isLoading = false
            }
        }
    }
    
    func fetchSongDetail(id: String) async -> Song? {
        guard let url = URL(string: "\(NetworkManager.baseURL)/songs/\(id)") else {
            return nil
        }
        
        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            let song = try JSONDecoder().decode(Song.self, from: data)
            return song
        } catch {
            print("Error fetching song detail: \(error)")
            return nil
        }
    }
    
    func fetchRecordingDetail(id: String) async -> Recording? {
        guard let url = URL(string: "\(NetworkManager.baseURL)/recordings/\(id)") else {
            return nil
        }
        
        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            let recording = try JSONDecoder().decode(Recording.self, from: data)
            return recording
        } catch {
            print("Error fetching recording detail: \(error)")
            return nil
        }
    }
}

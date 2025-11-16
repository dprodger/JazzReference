//
//  RepertoireManager.swift
//  JazzReference
//
//  Manages repertoire selection and persistence across app launches
//  UPDATED FOR PHASE 5: Added authentication support for user-specific repertoires
//

import SwiftUI
import Combine

/// Manages the current repertoire selection and provides repertoire list
@MainActor
class RepertoireManager: ObservableObject {
    /// All available repertoires (including "All Songs")
    @Published var repertoires: [Repertoire] = []
    
    /// Currently selected repertoire for viewing
    @Published var selectedRepertoire: Repertoire = .allSongs
    
    /// Last repertoire used for adding songs (for quick-add)
    @Published var lastUsedRepertoire: Repertoire?
    
    /// Whether repertoires are being loaded
    @Published var isLoading = false
    
    /// Error message if loading fails
    @Published var errorMessage: String?
    
    /// Whether user is authenticated (updated by AuthenticationManager)
    @Published var isAuthenticated = false
    
    private let networkManager = NetworkManager()
    private let selectedRepertoireKey = "selectedRepertoireId"
    private let lastUsedRepertoireKey = "lastUsedRepertoireId"
    
    // Reference to AuthenticationManager (set by app)
    private weak var authManager: AuthenticationManager?
    
    init() {
        // Restore previously selected repertoire from UserDefaults
        if let savedId = UserDefaults.standard.string(forKey: selectedRepertoireKey) {
            print("📚 Restored saved repertoire ID: \(savedId)")
        }
        
        // Restore last used repertoire for adding
        if let lastUsedId = UserDefaults.standard.string(forKey: lastUsedRepertoireKey) {
            print("📚 Restored last used repertoire ID: \(lastUsedId)")
        }
    }
    
    /// Connect to AuthenticationManager and load repertoires if authenticated
    func setAuthManager(_ authManager: AuthenticationManager) {
        self.authManager = authManager
        self.isAuthenticated = authManager.isAuthenticated
        
        // Load repertoires if already authenticated
        if authManager.isAuthenticated {
            Task {
                await loadRepertoires()
            }
        }
    }
    
    /// Load all repertoires from the API (requires authentication)
    func loadRepertoires() async {
        // Check authentication
        guard let authManager = authManager,
              authManager.isAuthenticated,
              let token = authManager.getAccessToken() else {
            await MainActor.run {
                self.repertoires = [.allSongs]
                self.selectedRepertoire = .allSongs
                self.isAuthenticated = false
                print("📚 Not authenticated - showing only 'All Songs'")
            }
            return
        }
        
        await MainActor.run {
            isLoading = true
            errorMessage = nil
        }
        
        // Build authenticated request
        let urlString = "\(NetworkManager.baseURL)/repertoires/"
        guard let url = URL(string: urlString) else {
            await MainActor.run {
                errorMessage = "Invalid URL"
                isLoading = false
            }
            return
        }
        
        var request = URLRequest(url: url)
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        
        // DEBUG: Log request details
        print("🔐 Sending token to /repertoires")
        print("   URL: \(url.absoluteString)")
        print("   Token prefix: \(String(token.prefix(20)))...")
        print("   Token length: \(token.count)")
        print("   Authorization header set: \(request.value(forHTTPHeaderField: "Authorization") != nil)")
        if let authHeader = request.value(forHTTPHeaderField: "Authorization") {
            print("   Header value prefix: \(String(authHeader.prefix(30)))...")
        }
        print("   All headers: \(request.allHTTPHeaderFields ?? [:])")
        
        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            
            // DEBUG: Log response details
            print("📥 Response received from /repertoires")
            if let httpResponse = response as? HTTPURLResponse {
                print("   Status: \(httpResponse.statusCode)")
                print("   URL: \(httpResponse.url?.absoluteString ?? "nil")")
            }
            if let responseString = String(data: data, encoding: .utf8) {
                print("   Body preview: \(String(responseString.prefix(200)))...")
            }
            
            // Check for auth errors
            if let httpResponse = response as? HTTPURLResponse {
                if httpResponse.statusCode == 401 {
                    // Try to parse error message
                    if let errorJson = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                       let errorMsg = errorJson["error"] as? String {
                        print("⚠️ 401 Unauthorized - Backend says: \(errorMsg)")
                    } else if let errorText = String(data: data, encoding: .utf8) {
                        print("⚠️ 401 Unauthorized - Raw response: \(errorText)")
                    } else {
                        print("⚠️ 401 Unauthorized - token expired")
                    }
                    await MainActor.run {
                        errorMessage = "Authentication expired. Please sign in again."
                        isLoading = false
                        isAuthenticated = false
                    }
                    return
                } else if httpResponse.statusCode != 200 {
                    await MainActor.run {
                        errorMessage = "Failed to load repertoires"
                        isLoading = false
                        print("❌ HTTP \(httpResponse.statusCode)")
                    }
                    return
                }
            }
            
            let fetchedRepertoires = try JSONDecoder().decode([Repertoire].self, from: data)
            
            await MainActor.run {
                // Add "All Songs" as first option
                self.repertoires = [.allSongs] + fetchedRepertoires
                
                // Restore previously selected repertoire if it exists
                if let savedId = UserDefaults.standard.string(forKey: selectedRepertoireKey),
                   let saved = self.repertoires.first(where: { $0.id == savedId }) {
                    self.selectedRepertoire = saved
                    print("📚 Restored repertoire: \(saved.name)")
                } else {
                    self.selectedRepertoire = .allSongs
                }
                
                // Restore last used repertoire if it exists
                if let lastUsedId = UserDefaults.standard.string(forKey: lastUsedRepertoireKey),
                   let lastUsed = fetchedRepertoires.first(where: { $0.id == lastUsedId }) {
                    self.lastUsedRepertoire = lastUsed
                    print("📚 Restored last used repertoire: \(lastUsed.name)")
                }
                
                self.isLoading = false
                self.isAuthenticated = true
                
                print("📚 Loaded \(fetchedRepertoires.count) user repertoires")
            }
        } catch {
            await MainActor.run {
                errorMessage = "Failed to load repertoires: \(error.localizedDescription)"
                isLoading = false
                print("❌ Error loading repertoires: \(error)")
            }
        }
    }
    
    /// Add song to repertoire (requires authentication)
    func addSongToRepertoire(songId: String, repertoireId: String) async -> Bool {
        guard let authManager = authManager,
              let token = authManager.getAccessToken() else {
            await MainActor.run {
                errorMessage = "Not authenticated"
            }
            return false
        }
        
        let urlString = "\(NetworkManager.baseURL)/repertoires/\(repertoireId)/songs/\(songId)"
        guard let url = URL(string: urlString) else {
            return false
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        
        do {
            let (_, response) = try await URLSession.shared.data(for: request)
            
            if let httpResponse = response as? HTTPURLResponse {
                if httpResponse.statusCode == 201 {
                    print("✅ Song added to repertoire")
                    // Refresh repertoires to update counts
                    await loadRepertoires()
                    return true
                } else if httpResponse.statusCode == 409 {
                    await MainActor.run {
                        errorMessage = "Song already in repertoire"
                    }
                    return false
                } else if httpResponse.statusCode == 401 {
                    await MainActor.run {
                        errorMessage = "Authentication expired"
                        isAuthenticated = false
                    }
                    return false
                }
            }
            
            return false
        } catch {
            await MainActor.run {
                errorMessage = "Failed to add song: \(error.localizedDescription)"
            }
            return false
        }
    }
    
    /// Create new repertoire (requires authentication)
    func createRepertoire(name: String, description: String?) async -> Bool {
        guard let authManager = authManager,
              let token = authManager.getAccessToken() else {
            await MainActor.run {
                errorMessage = "Not authenticated"
            }
            return false
        }
        
        let urlString = "\(NetworkManager.baseURL)/repertoires/"
        guard let url = URL(string: urlString) else {
            return false
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        var body: [String: Any] = ["name": name]
        if let desc = description {
            body["description"] = desc
        }
        
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        
        do {
            let (_, response) = try await URLSession.shared.data(for: request)
            
            if let httpResponse = response as? HTTPURLResponse,
               httpResponse.statusCode == 201 {
                print("✅ Repertoire created: \(name)")
                await loadRepertoires()
                return true
            }
            
            return false
        } catch {
            await MainActor.run {
                errorMessage = "Failed to create repertoire: \(error.localizedDescription)"
            }
            return false
        }
    }
    
    /// Delete repertoire (requires authentication)
    func deleteRepertoire(id: String) async -> Bool {
        guard let authManager = authManager,
              let token = authManager.getAccessToken() else {
            return false
        }
        
        let urlString = "\(NetworkManager.baseURL)/repertoires/\(id)"
        guard let url = URL(string: urlString) else {
            return false
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        
        do {
            let (_, response) = try await URLSession.shared.data(for: request)
            
            if let httpResponse = response as? HTTPURLResponse,
               httpResponse.statusCode == 200 {
                print("✅ Repertoire deleted")
                await loadRepertoires()
                return true
            }
            
            return false
        } catch {
            return false
        }
    }
    
    /// Select a new repertoire and persist the choice
    func selectRepertoire(_ repertoire: Repertoire) {
        selectedRepertoire = repertoire
        
        // Save to UserDefaults
        UserDefaults.standard.set(repertoire.id, forKey: selectedRepertoireKey)
        
        print("📚 Selected repertoire: \(repertoire.name) (ID: \(repertoire.id))")
    }
    
    /// Update last used repertoire (when adding a song)
    func setLastUsedRepertoire(_ repertoire: Repertoire) {
        lastUsedRepertoire = repertoire
        
        // Save to UserDefaults
        UserDefaults.standard.set(repertoire.id, forKey: lastUsedRepertoireKey)
        
        print("📚 Last used repertoire updated: \(repertoire.name)")
    }
    
    /// Get display name for current repertoire with song count
    var currentRepertoireDisplayName: String {
        if selectedRepertoire.id == "all" {
            return "All Songs"
        } else {
            let count = selectedRepertoire.songCount
            return "\(selectedRepertoire.name) (\(count))"
        }
    }
    
    /// Whether we're currently showing all songs
    var isShowingAllSongs: Bool {
        selectedRepertoire.id == "all"
    }
    
    /// Get repertoires available for adding songs (excludes "All Songs")
    var addableRepertoires: [Repertoire] {
        repertoires.filter { $0.id != "all" }
    }
}

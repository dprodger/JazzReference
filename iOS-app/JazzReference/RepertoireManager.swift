//
//  RepertoireManager.swift
//  JazzReference
//
//  Manages repertoire selection and persistence across app launches
//  UPDATED: Added last used repertoire tracking for quick-add feature
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
    
    private let networkManager = NetworkManager()
    private let selectedRepertoireKey = "selectedRepertoireId"
    private let lastUsedRepertoireKey = "lastUsedRepertoireId"
    
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
    
    /// Load all repertoires from the API
    func loadRepertoires() async {
        isLoading = true
        errorMessage = nil
        
        let fetchedRepertoires = await networkManager.fetchRepertoires()
        
        // Add "All Songs" as first option
        repertoires = [.allSongs] + fetchedRepertoires
        
        // Restore previously selected repertoire if it exists
        if let savedId = UserDefaults.standard.string(forKey: selectedRepertoireKey),
           let saved = repertoires.first(where: { $0.id == savedId }) {
            selectedRepertoire = saved
            print("📚 Restored repertoire: \(saved.name)")
        }
        
        // Restore last used repertoire if it exists
        if let lastUsedId = UserDefaults.standard.string(forKey: lastUsedRepertoireKey),
           let lastUsed = fetchedRepertoires.first(where: { $0.id == lastUsedId }) {
            lastUsedRepertoire = lastUsed
            print("📚 Restored last used repertoire: \(lastUsed.name)")
        }
        
        isLoading = false
        
        print("📚 Loaded \(fetchedRepertoires.count) repertoires (plus 'All Songs')")
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

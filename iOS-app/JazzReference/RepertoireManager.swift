//
//  RepertoireManager.swift
//  JazzReference
//
//  Manages repertoire selection and persistence across app launches
//

import SwiftUI
import Combine

/// Manages the current repertoire selection and provides repertoire list
@MainActor
class RepertoireManager: ObservableObject {
    /// All available repertoires (including "All Songs")
    @Published var repertoires: [Repertoire] = []
    
    /// Currently selected repertoire
    @Published var selectedRepertoire: Repertoire = .allSongs
    
    /// Whether repertoires are being loaded
    @Published var isLoading = false
    
    /// Error message if loading fails
    @Published var errorMessage: String?
    
    private let networkManager = NetworkManager()
    private let userDefaultsKey = "selectedRepertoireId"
    
    init() {
        // Restore previously selected repertoire from UserDefaults
        if let savedId = UserDefaults.standard.string(forKey: userDefaultsKey) {
            // We'll set this after loading repertoires
            print("📚 Restored saved repertoire ID: \(savedId)")
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
        if let savedId = UserDefaults.standard.string(forKey: userDefaultsKey),
           let saved = repertoires.first(where: { $0.id == savedId }) {
            selectedRepertoire = saved
            print("📚 Restored repertoire: \(saved.name)")
        }
        
        isLoading = false
        
        print("📚 Loaded \(fetchedRepertoires.count) repertoires (plus 'All Songs')")
    }
    
    /// Select a new repertoire and persist the choice
    func selectRepertoire(_ repertoire: Repertoire) {
        selectedRepertoire = repertoire
        
        // Save to UserDefaults
        UserDefaults.standard.set(repertoire.id, forKey: userDefaultsKey)
        
        print("📚 Selected repertoire: \(repertoire.name) (ID: \(repertoire.id))")
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
}

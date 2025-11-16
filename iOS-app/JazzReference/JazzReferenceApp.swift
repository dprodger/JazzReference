// Jazz Reference iOS App
// SwiftUI application for browsing jazz standards
// UPDATED FOR PHASE 5: Connected AuthenticationManager to RepertoireManager

import SwiftUI
import Combine


// MARK: - Main View

struct ContentView: View {
    @EnvironmentObject var authManager: AuthenticationManager
    
    var body: some View {
        TabView {
            SongsListView()
                .tabItem {
                    Label("Songs", systemImage: "music.note.list")
                }
            
            ArtistsListView()
                .tabItem {
                    Label("Artists", systemImage: "person.2.fill")
                }
            
            // Repertoire Tab (protected)
            Group {
                if authManager.isAuthenticated {
                    Text("My Repertoire - Coming in Phase 5!")
                } else {
                    RepertoireLoginPromptView()
                }
            }
            .tabItem {
                Label("Repertoire", systemImage: "bookmark.fill")
            }
            
            AboutView()
                .tabItem {
                    Label("About", systemImage: "info.circle")
                }
        }
        .tint(JazzTheme.burgundy) // Sets the active tab color
    }
}


import SwiftUI

// Add this to JazzReferenceApp.swift in the App struct
// This will verify the URL scheme is properly registered

@main
struct JazzReferenceApp: App {
    @State private var showingArtistCreation = false
    @State private var importedArtistData: ImportedArtistData?
    @Environment(\.scenePhase) var scenePhase
    @State private var showingSongCreation = false
    @State private var importedSongData: ImportedSongData?
    @StateObject private var repertoireManager = RepertoireManager()
    @StateObject private var authManager = AuthenticationManager()

    // ADD THIS INITIALIZER
    init() {
        // Diagnostic: Check URL scheme registration
        NSLog("========================================")
        NSLog("🔧 MAIN APP URL SCHEME DIAGNOSTICS")
        NSLog("========================================")
        
        // Check if CFBundleURLTypes is in Info.plist
        if let urlTypes = Bundle.main.object(forInfoDictionaryKey: "CFBundleURLTypes") as? [[String: Any]] {
            NSLog("✅ CFBundleURLTypes found in Info.plist")
            NSLog("   Number of URL types: %d", urlTypes.count)
            
            for (index, urlType) in urlTypes.enumerated() {
                NSLog("\n   URL Type %d:", index)
                
                if let name = urlType["CFBundleURLName"] as? String {
                    NSLog("   - Name: %@", name)
                }
                
                if let schemes = urlType["CFBundleURLSchemes"] as? [String] {
                    NSLog("   - Schemes: %@", schemes.joined(separator: ", "))
                    
                    if schemes.contains("jazzreference") {
                        NSLog("   ✅ Contains 'jazzreference'")
                    }
                }
                
                if let role = urlType["CFBundleTypeRole"] as? String {
                    NSLog("   - Role: %@", role)
                }
            }
        } else {
            NSLog("❌ CFBundleURLTypes NOT FOUND in Info.plist")
            NSLog("   URL scheme may be in build settings only")
            NSLog("   Extensions require it in Info.plist!")
        }
        
        NSLog("\nBundle ID: %@", Bundle.main.bundleIdentifier ?? "nil")
        NSLog("========================================\n")
    }
    
    var body: some Scene {
        WindowGroup {
            ContentView()
                .onOpenURL { url in
                    if url.scheme == "jazzreference" && url.host == "import-artist" {
                        checkForImportedArtist()
                    }
                }
                .onAppear {
                    checkForImportedArtist()
                    checkForImportedSong()
                    
                    // PHASE 5: Connect RepertoireManager to AuthenticationManager
                    repertoireManager.setAuthManager(authManager)
                    print("📚 Connected RepertoireManager to AuthenticationManager")
                }
                .onChange(of: scenePhase) { oldPhase, newPhase in
                    if newPhase == .active {
                        checkForImportedArtist()
                        checkForImportedSong()
                    }
                }
                .onChange(of: authManager.isAuthenticated) { wasAuthenticated, isAuthenticated in
                    // PHASE 5: Update repertoire manager when auth state changes
                    if isAuthenticated {
                        print("📚 User authenticated - loading repertoires")
                        Task {
                            await repertoireManager.loadRepertoires()
                        }
                    } else {
                        print("📚 User logged out - clearing repertoires")
                        Task {
                            await repertoireManager.loadRepertoires()
                        }
                    }
                }
                .sheet(item: $importedArtistData) { data in
                    // CHANGED: Use .sheet(item:) instead of isPresented
                    NavigationStack {
                        ArtistCreationView(importedData: data)
                    }
                }
                .sheet(item: $importedSongData) { data in
                    NavigationStack {
                        SongCreationView(importedData: data)
                    }
                }
                .ignoresSafeArea()
                .environmentObject(authManager)
                .environmentObject(repertoireManager)
        }
    }
    
    private func checkForImportedArtist() {
        if let data = SharedArtistDataManager.retrieveSharedData() {
            NSLog("🔥 Imported artist data detected: %@", data.name)
            importedArtistData = data
            showingArtistCreation = true
        } else {
            NSLog("ℹ️ No imported artist data found")
        }
    }
    
    private func checkForImportedSong() {
        if let data = SharedSongDataManager.retrieveSharedData() {
            NSLog("🔥 Imported song data detected: %@", data.title)
            importedSongData = data
            showingSongCreation = true
        } else {
            NSLog("ℹ️ No imported song data found")
        }
    }
}

// MARK: - Preview

#Preview {
    ContentView()
}

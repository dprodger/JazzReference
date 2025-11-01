// Jazz Reference iOS App
// SwiftUI application for browsing jazz standards

import SwiftUI
import Combine


// MARK: - Main View

struct ContentView: View {
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
                }
                .onChange(of: scenePhase) { oldPhase, newPhase in
                    if newPhase == .active {
                        checkForImportedArtist()
                        checkForImportedSong()
                    }
                }
                .sheet(item: $importedArtistData) { data in
                    // CHANGED: Use .sheet(item:) instead of isPresented
                    NavigationStack {
                        ArtistCreationView(importedData: data)
                    }
                }
                .sheet(item: $importedSongData) { data in           // ← ADD THIS
                    NavigationStack {                                 // ← ADD THIS
                        SongCreationView(importedData: data)         // ← ADD THIS
                    }                                                 // ← ADD THIS
                }                                                     // ← ADD THIS
                .ignoresSafeArea()
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

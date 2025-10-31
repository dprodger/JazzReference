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

@main
struct JazzReferenceApp: App {
    // State for showing artist creation sheet
    @State private var showingArtistCreation = false
    // State for holding imported artist data
    @State private var importedArtistData: ImportedArtistData?
    
    var body: some Scene {
        WindowGroup {
            ContentView()
                .onOpenURL { url in
                         if url.scheme == "jazzreference" && url.host == "import-artist" {
                             checkForImportedArtist()
                         }
                     }
                .onAppear {
                    // Check for imported artist data when app launches
                    checkForImportedArtist()
                }
                .sheet(isPresented: $showingArtistCreation) {
                    // Show artist creation view with imported data
                    if let data = importedArtistData {
                        ArtistCreationView(importedData: data)
                    }
                }
                .ignoresSafeArea()
        }
    }
    
    private func checkForImportedArtist() {
        // Use SharedArtistDataManager to retrieve data from extension
        if let data = SharedArtistDataManager.retrieveSharedData() {
            print("📥 Imported artist data detected: \(data.name)")
            importedArtistData = data
            showingArtistCreation = true
        }
    }
}
// MARK: - Preview

#Preview {
    ContentView()
}

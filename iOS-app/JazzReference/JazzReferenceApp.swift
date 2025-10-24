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


// MARK: - App Entry Point

@main
struct JazzReferenceApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
                .ignoresSafeArea()
        }
    }
}

// MARK: - Preview

#Preview {
    ContentView()
}

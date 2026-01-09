// ContentView.swift
// Main tab-based navigation view for the iOS app

import SwiftUI

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

            RecordingsListView()
                .tabItem {
                    Label("Recordings", systemImage: "opticaldisc")
                }

            // Settings Tab (protected)
            Group {
                if authManager.isAuthenticated {
                    SettingsView()
                        .environmentObject(authManager)
                } else {
                    RepertoireLoginPromptView()
                }
            }
            .tabItem {
                Label("Settings", systemImage: "gearshape.fill")
            }

            AboutView()
                .tabItem {
                    Label("About", systemImage: "info.circle")
                }

        }
        .onAppear {
            // Set up tab bar appearance with opaque background
            let appearance = UITabBarAppearance()
            appearance.configureWithOpaqueBackground()
            appearance.backgroundColor = UIColor(JazzTheme.backgroundLight)

            // Set unselected item color (light gray)
            appearance.stackedLayoutAppearance.normal.iconColor = UIColor.lightGray
            appearance.stackedLayoutAppearance.normal.titleTextAttributes = [.foregroundColor: UIColor.lightGray]

            // Set selected item color (burgundy)
            appearance.stackedLayoutAppearance.selected.iconColor = UIColor(JazzTheme.burgundy)
            appearance.stackedLayoutAppearance.selected.titleTextAttributes = [.foregroundColor: UIColor(JazzTheme.burgundy)]

            UITabBar.appearance().standardAppearance = appearance
            UITabBar.appearance().scrollEdgeAppearance = appearance
        }
        .tint(JazzTheme.burgundy) // Sets the active tab color
    }
}

#Preview {
    ContentView()
        .environmentObject(AuthenticationManager())
}

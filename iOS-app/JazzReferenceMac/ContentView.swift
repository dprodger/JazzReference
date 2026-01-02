//
//  ContentView.swift
//  JazzReferenceMac
//
//  Main content view with tab navigation for macOS
//

import SwiftUI

enum NavigationItem: String, CaseIterable, Identifiable {
    case songs = "Songs"
    case artists = "Artists"
    case recordings = "Recordings"

    var id: String { rawValue }

    var icon: String {
        switch self {
        case .songs: return "music.note.list"
        case .artists: return "person.2.fill"
        case .recordings: return "opticaldisc"
        }
    }
}

struct ContentView: View {
    @State private var selectedTab: NavigationItem = .songs
    @EnvironmentObject var authManager: AuthenticationManager
    @EnvironmentObject var repertoireManager: RepertoireManager

    var body: some View {
        TabView(selection: $selectedTab) {
            SongsListView()
                .tabItem {
                    Label("Songs", systemImage: "music.note.list")
                }
                .tag(NavigationItem.songs)

            ArtistsListView()
                .tabItem {
                    Label("Artists", systemImage: "person.2.fill")
                }
                .tag(NavigationItem.artists)

            RecordingsListView()
                .tabItem {
                    Label("Recordings", systemImage: "opticaldisc")
                }
                .tag(NavigationItem.recordings)
        }
        .onReceive(NotificationCenter.default.publisher(for: .navigateToSongs)) { _ in
            selectedTab = .songs
        }
        .onReceive(NotificationCenter.default.publisher(for: .navigateToArtists)) { _ in
            selectedTab = .artists
        }
        .onReceive(NotificationCenter.default.publisher(for: .navigateToRecordings)) { _ in
            selectedTab = .recordings
        }
    }
}

// MARK: - Settings View (macOS Preferences)

struct SettingsView: View {
    @EnvironmentObject var authManager: AuthenticationManager

    var body: some View {
        TabView {
            AccountSettingsView()
                .tabItem {
                    Label("Account", systemImage: "person.circle")
                }

            GeneralSettingsView()
                .tabItem {
                    Label("General", systemImage: "gearshape")
                }
        }
        .frame(width: 450, height: 250)
    }
}

struct AccountSettingsView: View {
    @EnvironmentObject var authManager: AuthenticationManager

    var body: some View {
        Form {
            if authManager.isAuthenticated {
                Section {
                    LabeledContent("Name") {
                        Text(authManager.currentUser?.displayName ?? "—")
                    }
                    LabeledContent("Email") {
                        Text(authManager.currentUser?.email ?? "—")
                    }
                }

                Section {
                    Button("Sign Out") {
                        authManager.logout()
                    }
                    .foregroundColor(.red)
                }
            } else {
                Section {
                    Text("Sign in to access your repertoires and sync your data.")
                        .foregroundColor(.secondary)

                    // Login form would go here
                    Text("Login functionality coming soon")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
        }
        .formStyle(.grouped)
        .padding()
    }
}

struct GeneralSettingsView: View {
    var body: some View {
        Form {
            Section("Display") {
                Text("Display settings will appear here")
                    .foregroundColor(.secondary)
            }
        }
        .formStyle(.grouped)
        .padding()
    }
}

#Preview {
    ContentView()
        .environmentObject(AuthenticationManager())
        .environmentObject(RepertoireManager())
}

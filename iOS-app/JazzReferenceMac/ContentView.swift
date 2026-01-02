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
        .frame(width: 450, height: authManager.isAuthenticated ? 200 : 550)
        .animation(.easeInOut, value: authManager.isAuthenticated)
    }
}

struct AccountSettingsView: View {
    @EnvironmentObject var authManager: AuthenticationManager

    var body: some View {
        if authManager.isAuthenticated {
            authenticatedView
        } else {
            MacLoginView(isInline: true)
                .environmentObject(authManager)
        }
    }

    @ViewBuilder
    private var authenticatedView: some View {
        Form {
            Section {
                HStack(spacing: 12) {
                    // Profile image or placeholder
                    if let imageUrl = authManager.currentUser?.profileImageUrl,
                       let url = URL(string: imageUrl) {
                        AsyncImage(url: url) { image in
                            image
                                .resizable()
                                .aspectRatio(contentMode: .fill)
                        } placeholder: {
                            Image(systemName: "person.circle.fill")
                                .font(.system(size: 40))
                                .foregroundColor(JazzTheme.smokeGray)
                        }
                        .frame(width: 50, height: 50)
                        .clipShape(Circle())
                    } else {
                        Image(systemName: "person.circle.fill")
                            .font(.system(size: 50))
                            .foregroundColor(JazzTheme.smokeGray)
                    }

                    VStack(alignment: .leading, spacing: 4) {
                        Text(authManager.currentUser?.displayName ?? "User")
                            .font(JazzTheme.headline())
                            .foregroundColor(JazzTheme.charcoal)
                        Text(authManager.currentUser?.email ?? "")
                            .font(JazzTheme.subheadline())
                            .foregroundColor(.secondary)
                    }
                }
                .padding(.vertical, 8)
            }

            Section {
                Button("Sign Out") {
                    authManager.logout()
                }
                .foregroundColor(.red)
            }
        }
        .formStyle(.grouped)
        .padding()
    }
}

struct GeneralSettingsView: View {
    @AppStorage("preferredStreamingService") private var preferredStreamingService: String = "spotify"

    var body: some View {
        Form {
            Section("Playback") {
                Picker("Preferred Streaming Service", selection: $preferredStreamingService) {
                    Text("Spotify").tag("spotify")
                    Text("Apple Music").tag("apple_music")
                    Text("YouTube").tag("youtube")
                }
                .pickerStyle(.radioGroup)
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

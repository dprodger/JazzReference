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
    @EnvironmentObject var favoritesManager: FavoritesManager

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
        .frame(width: 500, height: authManager.isAuthenticated ? 400 : 550)
        .animation(.easeInOut, value: authManager.isAuthenticated)
    }
}

struct AccountSettingsView: View {
    @EnvironmentObject var authManager: AuthenticationManager
    @EnvironmentObject var favoritesManager: FavoritesManager
    @State private var selectedRecordingId: String?

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
        VStack(spacing: 0) {
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

                        Spacer()

                        Button("Sign Out") {
                            authManager.logout()
                        }
                        .foregroundColor(.red)
                    }
                    .padding(.vertical, 8)
                }
            }
            .formStyle(.grouped)

            // Favorites Section
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Image(systemName: "heart.fill")
                        .foregroundColor(.red)
                    Text("Favorite Recordings")
                        .font(JazzTheme.headline())
                        .foregroundColor(JazzTheme.charcoal)

                    if !favoritesManager.favoriteRecordings.isEmpty {
                        Text("(\(favoritesManager.favoriteRecordings.count))")
                            .font(JazzTheme.subheadline())
                            .foregroundColor(JazzTheme.charcoal.opacity(0.7))
                    }

                    Spacer()
                }
                .padding(.horizontal)

                if favoritesManager.isLoading {
                    HStack {
                        Spacer()
                        ProgressView()
                        Spacer()
                    }
                    .padding()
                } else if favoritesManager.favoriteRecordings.isEmpty {
                    Text("No favorite recordings yet")
                        .font(JazzTheme.body())
                        .foregroundColor(JazzTheme.charcoal.opacity(0.7))
                        .padding(.horizontal)
                } else {
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 12) {
                            ForEach(favoritesManager.favoriteRecordings, id: \.id) { recording in
                                FavoriteRecordingCard(recording: recording)
                                    .onTapGesture {
                                        selectedRecordingId = recording.id
                                    }
                            }
                        }
                        .padding(.horizontal)
                    }
                }
            }
            .padding(.vertical)
            .background(JazzTheme.backgroundLight)
        }
        .sheet(isPresented: Binding(
            get: { selectedRecordingId != nil },
            set: { if !$0 { selectedRecordingId = nil } }
        )) {
            if let recordingId = selectedRecordingId {
                RecordingDetailView(recordingId: recordingId)
                    .frame(minWidth: 600, minHeight: 500)
            }
        }
        .task {
            if favoritesManager.favoriteRecordings.isEmpty {
                await favoritesManager.loadFavorites()
            }
        }
    }
}

// MARK: - Favorite Recording Card

struct FavoriteRecordingCard: View {
    let recording: NetworkManager.FavoriteRecordingResponse
    @State private var isHovering = false

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            // Album art
            AsyncImage(url: URL(string: recording.bestAlbumArtSmall ?? "")) { image in
                image
                    .resizable()
                    .aspectRatio(contentMode: .fill)
            } placeholder: {
                Rectangle()
                    .fill(JazzTheme.cardBackground)
                    .overlay {
                        Image(systemName: "music.note")
                            .foregroundColor(JazzTheme.smokeGray)
                    }
            }
            .frame(width: 80, height: 80)
            .cornerRadius(8)

            // Song title
            Text(recording.songTitle ?? "Unknown")
                .font(JazzTheme.caption())
                .foregroundColor(JazzTheme.charcoal)
                .lineLimit(2)
                .frame(width: 80, alignment: .leading)
        }
        .padding(8)
        .background(isHovering ? JazzTheme.cardBackground : Color.clear)
        .cornerRadius(8)
        .onHover { hovering in
            isHovering = hovering
        }
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
        .environmentObject(FavoritesManager())
}

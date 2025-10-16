// Jazz Reference iOS App
// SwiftUI application for browsing jazz standards

import SwiftUI
import Combine


// MARK: - Models

struct Song: Codable, Identifiable {
    let id: String
    let title: String
    let composer: String?
    let structure: String?
    let externalReferences: [String: String]?
    let recordings: [Recording]?
    let recordingCount: Int?
    
    enum CodingKeys: String, CodingKey {
        case id, title, composer, structure, recordings
        case externalReferences = "external_references"
        case recordingCount = "recording_count"
    }
}

struct Recording: Codable, Identifiable {
    let id: String
    let songId: String?
    let songTitle: String?
    let albumTitle: String?
    let recordingDate: String?
    let recordingYear: Int?
    let label: String?
    let spotifyUrl: String?
    let youtubeUrl: String?
    let appleMusicUrl: String?
    let isCanonical: Bool?
    let notes: String?
    let performers: [Performer]?
    let composer: String?
    
    enum CodingKeys: String, CodingKey {
        case id, label, notes, composer, performers
        case songId = "song_id"
        case songTitle = "song_title"
        case albumTitle = "album_title"
        case recordingDate = "recording_date"
        case recordingYear = "recording_year"
        case spotifyUrl = "spotify_url"
        case youtubeUrl = "youtube_url"
        case appleMusicUrl = "apple_music_url"
        case isCanonical = "is_canonical"
    }
}

struct Performer: Codable, Identifiable {
    let id: String
    let name: String
    let instrument: String?
    let role: String?
    let biography: String?
    let birthDate: String?
    let deathDate: String?
    
    enum CodingKeys: String, CodingKey {
        case id, name, instrument, role, biography
        case birthDate = "birth_date"
        case deathDate = "death_date"
    }
}


// MARK: - Main View

struct ContentView: View {
    @StateObject private var networkManager = NetworkManager()
    @State private var searchText = ""
    @State private var searchTask: Task<Void, Never>?
    
    var body: some View {
        NavigationStack {
            VStack {
                if networkManager.isLoading {
                    ProgressView("Loading songs...")
                        .padding()
                } else if let error = networkManager.errorMessage {
                    VStack(spacing: 16) {
                        Image(systemName: "exclamationmark.triangle")
                            .font(.system(size: 50))
                            .foregroundColor(.orange)
                        Text("Error")
                            .font(.headline)
                        Text(error)
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal)
                        Button("Retry") {
                            Task {
                                await networkManager.fetchSongs()
                            }
                        }
                        .buttonStyle(.borderedProminent)
                    }
                    .padding()
                } else {
                    List(networkManager.songs) { song in
                        NavigationLink(destination: SongDetailView(songId: song.id)) {
                            VStack(alignment: .leading, spacing: 4) {
                                Text(song.title)
                                    .font(.headline)
                                if let composer = song.composer {
                                    Text(composer)
                                        .font(.subheadline)
                                        .foregroundColor(.secondary)
                                }
                            }
                            .padding(.vertical, 4)
                        }
                    }
                    .listStyle(.insetGrouped)
                }
            }
            .navigationTitle("Jazz Standards")
            .searchable(text: $searchText, prompt: "Search songs")
            .onChange(of: searchText) { oldValue, newValue in
                searchTask?.cancel()
                searchTask = Task {
                    try? await Task.sleep(nanoseconds: 300_000_000) // 0.3 second debounce
                    if !Task.isCancelled {
                        await networkManager.fetchSongs(searchQuery: newValue)
                    }
                }
            }
            .task {
                await networkManager.fetchSongs()
            }
        }
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

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
    let songReference: String?
    let musicbrainzId: String?
    let externalReferences: [String: String]?
    let recordings: [Recording]?
    let recordingCount: Int?
    
    enum CodingKeys: String, CodingKey {
        case id, title, composer, structure, recordings
        case songReference = "song_reference"
        case musicbrainzId = "musicbrainz_id"
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

struct PerformerDetail: Codable, Identifiable {
    let id: String
    let name: String
    let biography: String?
    let birthDate: String?
    let deathDate: String?
    let externalLinks: [String: String]?
    let instruments: [PerformerInstrument]?
    let recordings: [PerformerRecording]?
    
    enum CodingKeys: String, CodingKey {
        case id, name, biography, instruments, recordings
        case birthDate = "birth_date"
        case deathDate = "death_date"
        case externalLinks = "external_links"
    }
}

struct PerformerInstrument: Codable {
    let name: String
    let isPrimary: Bool?
    
    enum CodingKeys: String, CodingKey {
        case name
        case isPrimary = "is_primary"
    }
}

struct PerformerRecording: Codable, Identifiable {
    let songId: String
    let songTitle: String
    let recordingId: String
    let albumTitle: String?
    let recordingYear: Int?
    let isCanonical: Bool?
    let role: String?
    
    var id: String { recordingId }
    
    enum CodingKeys: String, CodingKey {
        case songId = "song_id"
        case songTitle = "song_title"
        case recordingId = "recording_id"
        case albumTitle = "album_title"
        case recordingYear = "recording_year"
        case isCanonical = "is_canonical"
        case role
    }
}
// MARK: - Main View

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

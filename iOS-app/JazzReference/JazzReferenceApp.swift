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
    let images: [ArtistImage]?  // <-- ADD THIS LINE

    enum CodingKeys: String, CodingKey {
        case id, name, biography, instruments, recordings, images
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

// ============================================================================
// ADD THESE TO YOUR JazzReferenceApp.swift FILE
// Add after your existing PerformerDetail struct
// ============================================================================

// MARK: - Image Models (ADD THIS)

struct ArtistImage: Codable, Identifiable {
    let id: String
    let url: String
    let source: String
    let sourceIdentifier: String?
    let licenseType: String?
    let licenseUrl: String?
    let attribution: String?
    let width: Int?
    let height: Int?
    let thumbnailUrl: String?
    let sourcePageUrl: String?
    let isPrimary: Bool
    let displayOrder: Int
    
    enum CodingKeys: String, CodingKey {
        case id, url, source, width, height, attribution
        case sourceIdentifier = "source_identifier"
        case licenseType = "license_type"
        case licenseUrl = "license_url"
        case thumbnailUrl = "thumbnail_url"
        case sourcePageUrl = "source_page_url"
        case isPrimary = "is_primary"
        case displayOrder = "display_order"
    }
}


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

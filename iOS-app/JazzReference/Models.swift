//
//  Models.swift
//  JazzReference
//
//  Updated with Repertoire support
//

import Foundation

struct Song: Codable, Identifiable {
    let id: String
    let title: String
    let composer: String?
    let structure: String?
    let songReference: String?
    let musicbrainzId: String?
    let wikipediaUrl: String?
    let externalReferences: [String: String]?
    let recordings: [Recording]?
    let recordingCount: Int?
    
    enum CodingKeys: String, CodingKey {
        case id, title, composer, structure, recordings
        case songReference = "song_reference"
        case musicbrainzId = "musicbrainz_id"
        case wikipediaUrl = "wikipedia_url"
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
    let spotifyTrackId: String?
    let albumArtSmall: String?
    let albumArtMedium: String?
    let albumArtLarge: String?
    let youtubeUrl: String?
    let appleMusicUrl: String?
    let musicbrainzId: String?
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
        case spotifyTrackId = "spotify_track_id"
        case albumArtSmall = "album_art_small"
        case albumArtMedium = "album_art_medium"
        case albumArtLarge = "album_art_large"
        case youtubeUrl = "youtube_url"
        case appleMusicUrl = "apple_music_url"
        case isCanonical = "is_canonical"
        case musicbrainzId = "musicbrainz_id"
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
    let wikipediaUrl: String?
    let musicbrainzId: String?
    let instruments: [PerformerInstrument]?
    let recordings: [PerformerRecording]?
    let images: [ArtistImage]?

    enum CodingKeys: String, CodingKey {
        case id, name, biography, instruments, recordings, images
        case birthDate = "birth_date"
        case deathDate = "death_date"
        case externalLinks = "external_links"
        case wikipediaUrl = "wikipedia_url"
        case musicbrainzId = "musicbrainz_id"
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
    
    enum CodingKeys: String, CodingKey {
        case id, url, source, width, height, attribution
        case sourceIdentifier = "source_identifier"
        case licenseType = "license_type"
        case licenseUrl = "license_url"
        case thumbnailUrl = "thumbnail_url"
        case sourcePageUrl = "source_page_url"
    }
}

// MARK: - NEW: Repertoire Models

/// Represents a named collection of songs (a repertoire)
struct Repertoire: Codable, Identifiable, Hashable {
    let id: String
    let name: String
    let description: String?
    let songCount: Int
    let createdAt: String?
    let updatedAt: String?
    
    enum CodingKeys: String, CodingKey {
        case id, name, description
        case songCount = "song_count"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }
    
    // Hashable conformance for use in Picker
    func hash(into hasher: inout Hasher) {
        hasher.combine(id)
    }
    
    static func == (lhs: Repertoire, rhs: Repertoire) -> Bool {
        lhs.id == rhs.id
    }
}






// Solo Transcriptions - iOS Models and API Methods
// Add these to iOS-app/JazzReference/JazzReferenceApp.swift

// MARK: - Solo Transcription Model

struct SoloTranscription: Codable, Identifiable {
    let id: String
    let songId: String
    let recordingId: String
    let youtubeUrl: String?
    let createdAt: String?
    let updatedAt: String?
    
    // Optional joined data from API
    let songTitle: String?
    let albumTitle: String?
    let recordingYear: Int?
    let composer: String?
    let label: String?
    
    enum CodingKeys: String, CodingKey {
        case id
        case songId = "song_id"
        case recordingId = "recording_id"
        case youtubeUrl = "youtube_url"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
        case songTitle = "song_title"
        case albumTitle = "album_title"
        case recordingYear = "recording_year"
        case composer
        case label
    }
}

// MARK: - Preview Data for Solo Transcriptions

#if DEBUG
extension SoloTranscription {
    static var preview1: SoloTranscription {
        SoloTranscription(
            id: "preview-transcription-1",
            songId: "preview-song-1",
            recordingId: "preview-recording-1",
            youtubeUrl: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            createdAt: "2024-01-15T10:30:00Z",
            updatedAt: "2024-01-15T10:30:00Z",
            songTitle: "Autumn Leaves",
            albumTitle: "Kind of Blue",
            recordingYear: 1959,
            composer: "Joseph Kosma",
            label: "Columbia"
        )
    }
    
    static var preview2: SoloTranscription {
        SoloTranscription(
            id: "preview-transcription-2",
            songId: "preview-song-1",
            recordingId: "preview-recording-2",
            youtubeUrl: "https://www.youtube.com/watch?v=abc123xyz",
            createdAt: "2024-02-20T14:15:00Z",
            updatedAt: "2024-02-20T14:15:00Z",
            songTitle: "Autumn Leaves",
            albumTitle: "Waltz for Debby",
            recordingYear: 1961,
            composer: "Joseph Kosma",
            label: "Riverside"
        )
    }
    
    static var previewMinimal: SoloTranscription {
        SoloTranscription(
            id: "preview-transcription-3",
            songId: "preview-song-2",
            recordingId: "preview-recording-3",
            youtubeUrl: "https://www.youtube.com/watch?v=xyz789abc",
            createdAt: "2024-03-10T09:00:00Z",
            updatedAt: "2024-03-10T09:00:00Z",
            songTitle: "Blue in Green",
            albumTitle: nil,
            recordingYear: nil,
            composer: nil,
            label: nil
        )
    }
}
#endif


/// Special repertoire option for "All Songs"
extension Repertoire {
    static var allSongs: Repertoire {
        Repertoire(
            id: "all",
            name: "All Songs",
            description: "View all songs in the database",
            songCount: 0,
            createdAt: nil,
            updatedAt: nil
        )
    }
}

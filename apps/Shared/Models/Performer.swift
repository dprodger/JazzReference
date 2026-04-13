import Foundation

struct Performer: Codable, Identifiable {
    let id: String
    let name: String
    let sortName: String?
    let instrument: String?
    let role: String?
    let biography: String?
    let birthDate: String?
    let deathDate: String?

    enum CodingKeys: String, CodingKey {
        case id, name, instrument, role, biography
        case sortName = "sort_name"
        case birthDate = "birth_date"
        case deathDate = "death_date"
    }
}

struct PerformerDetail: Codable, Identifiable {
    let id: String
    let name: String
    let sortName: String?
    let biography: String?
    let birthDate: String?
    let deathDate: String?
    let externalLinks: [String: String]?
    let wikipediaUrl: String?
    let musicbrainzId: String?
    let instruments: [PerformerInstrument]?
    var recordings: [PerformerRecording]?  // Mutable for two-phase loading
    let images: [ArtistImage]?
    let recordingCount: Int?  // Total count from summary endpoint

    enum CodingKeys: String, CodingKey {
        case id, name, biography, instruments, recordings, images
        case sortName = "sort_name"
        case birthDate = "birth_date"
        case deathDate = "death_date"
        case externalLinks = "external_links"
        case wikipediaUrl = "wikipedia_url"
        case musicbrainzId = "musicbrainz_id"
        case recordingCount = "recording_count"
    }
}

/// Response from /performers/{id}/recordings endpoint
struct PerformerRecordingsResponse: Codable {
    let recordings: [PerformerRecording]
    let recordingCount: Int

    enum CodingKeys: String, CodingKey {
        case recordings
        case recordingCount = "recording_count"
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
    let artistCredit: String?
    let recordingYear: Int?
    let isCanonical: Bool?
    let role: String?
    let bestCoverArtSmall: String?
    let bestCoverArtMedium: String?

    var id: String { recordingId }

    enum CodingKeys: String, CodingKey {
        case songId = "song_id"
        case songTitle = "song_title"
        case recordingId = "recording_id"
        case albumTitle = "album_title"
        case artistCredit = "artist_credit"
        case recordingYear = "recording_year"
        case isCanonical = "is_canonical"
        case role
        case bestCoverArtSmall = "best_cover_art_small"
        case bestCoverArtMedium = "best_cover_art_medium"
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

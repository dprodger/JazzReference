import Foundation

struct Song: Identifiable, Codable {
    let id: String
    let title: String
    let composer: String?
    let composedYear: Int?
    let composedKey: String?
    let structure: String?
    let songReference: String?
    let musicbrainzId: String?
    let wikipediaUrl: String?
    let externalReferences: [String: String]?
    let createdAt: String?
    let updatedAt: String?

    // Recordings data (included in detail view)
    var recordings: [Recording]?
    let recordingCount: Int?

    // Featured recordings (only authoritative ones, from summary endpoint)
    let featuredRecordings: [Recording]?

    // Transcriptions data (included in song response)
    let transcriptions: [SoloTranscription]?
    let transcriptionCount: Int?

    var authorityRecommendationCount: Int?

    // Whether any recording has streaming links (for play button visibility)
    let hasAnyStreaming: Bool?

    enum CodingKeys: String, CodingKey {
        case id, title, composer, structure
        case composedYear = "composed_year"
        case composedKey = "composed_key"
        case songReference = "song_reference"
        case musicbrainzId = "musicbrainz_id"
        case wikipediaUrl = "wikipedia_url"
        case externalReferences = "external_references"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
        case recordings
        case recordingCount = "recording_count"
        case featuredRecordings = "featured_recordings"
        case transcriptions
        case transcriptionCount = "transcription_count"
        case authorityRecommendationCount = "authority_recommendation_count"
        case hasAnyStreaming = "has_any_streaming"
    }

    var hasAuthorityRecommendations: Bool {
        guard let count = authorityRecommendationCount else { return false }
        return count > 0
    }

    // Convert external_references JSONB to ExternalReference array
    var externalReferencesList: [ExternalReference] {
        guard let refs = externalReferences else { return [] }
        return refs.map { ExternalReference(source: $0.key, url: $0.value) }
            .sorted { $0.displayName < $1.displayName }
    }
}

// MARK: - Song Recordings Response (from /api/songs/{id}/recordings)

struct SongRecordingsResponse: Codable {
    let songId: String
    let recordings: [Recording]
    let recordingCount: Int

    enum CodingKeys: String, CodingKey {
        case songId = "song_id"
        case recordings
        case recordingCount = "recording_count"
    }
}

// MARK: - Recording Sort Order Enum

enum RecordingSortOrder: String, CaseIterable, Identifiable {
    case year = "year"
    case name = "name"

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .year: return "Year"
        case .name: return "Name"
        }
    }

    var icon: String {
        switch self {
        case .year: return "calendar"
        case .name: return "person.text.rectangle"
        }
    }
}

// MARK: - External Reference Model

struct ExternalReference: Identifiable {
    let id = UUID()
    let source: String
    let url: String
    let displayName: String

    init(source: String, url: String) {
        self.source = source
        self.url = url

        switch source.lowercased() {
        case "wikipedia":
            self.displayName = "Wikipedia"
        case "jazzstandards":
            self.displayName = "JazzStandards.com"
        case "allmusic":
            self.displayName = "AllMusic"
        case "discogs":
            self.displayName = "Discogs"
        case "musicbrainz":
            self.displayName = "MusicBrainz"
        default:
            self.displayName = source.capitalized
        }
    }

    var iconName: String {
        switch source.lowercased() {
        case "wikipedia":
            return "book.fill"
        case "jazzstandards":
            return "music.note.list"
        case "allmusic":
            return "music.quarternote.3"
        case "discogs":
            return "opticaldisc"
        case "musicbrainz":
            return "waveform"
        default:
            return "link"
        }
    }
}

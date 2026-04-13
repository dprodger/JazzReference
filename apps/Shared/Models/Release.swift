import Foundation

struct Release: Identifiable, Codable {
    let id: String
    let title: String
    let artistCredit: String?
    let releaseDate: String?
    let releaseYear: Int?
    let country: String?
    let label: String?
    let catalogNumber: String?

    // Spotify integration
    let spotifyAlbumId: String?
    let spotifyAlbumUrl: String?
    let spotifyTrackId: String?
    let spotifyTrackUrl: String?

    // Cover art
    let coverArtSmall: String?
    let coverArtMedium: String?
    let coverArtLarge: String?

    // Cover art source (for watermark/attribution)
    let coverArtSource: String?
    let coverArtSourceUrl: String?

    // Back cover art (from Cover Art Archive)
    let backCoverArtSmall: String?
    let backCoverArtMedium: String?
    let backCoverArtLarge: String?
    let hasBackCover: Bool?
    let backCoverSource: String?
    let backCoverSourceUrl: String?

    // Track position on release
    let discNumber: Int?
    let trackNumber: Int?
    let totalTracks: Int?

    // Format info
    let formatName: String?
    let statusName: String?

    // MusicBrainz reference
    let musicbrainzReleaseId: String?

    // Performers on this release
    let performers: [Performer]?
    let performerCount: Int?

    enum CodingKeys: String, CodingKey {
        case id, title, country, label, performers
        case artistCredit = "artist_credit"
        case releaseDate = "release_date"
        case releaseYear = "release_year"
        case catalogNumber = "catalog_number"
        case spotifyAlbumId = "spotify_album_id"
        case spotifyAlbumUrl = "spotify_album_url"
        case spotifyTrackId = "spotify_track_id"
        case spotifyTrackUrl = "spotify_track_url"
        case coverArtSmall = "cover_art_small"
        case coverArtMedium = "cover_art_medium"
        case coverArtLarge = "cover_art_large"
        case coverArtSource = "cover_art_source"
        case coverArtSourceUrl = "cover_art_source_url"
        case backCoverArtSmall = "back_cover_art_small"
        case backCoverArtMedium = "back_cover_art_medium"
        case backCoverArtLarge = "back_cover_art_large"
        case hasBackCover = "has_back_cover"
        case backCoverSource = "back_cover_source"
        case backCoverSourceUrl = "back_cover_source_url"
        case discNumber = "disc_number"
        case trackNumber = "track_number"
        case totalTracks = "total_tracks"
        case formatName = "format_name"
        case statusName = "status_name"
        case musicbrainzReleaseId = "musicbrainz_release_id"
        case performerCount = "performer_count"
    }

    // MARK: - Computed Properties

    var hasSpotify: Bool {
        spotifyTrackId != nil || spotifyTrackUrl != nil
    }

    var trackPositionDisplay: String? {
        guard let track = trackNumber else { return nil }
        if let disc = discNumber, disc > 1 {
            return "Disc \(disc), Track \(track)"
        }
        return "Track \(track)"
    }

    var yearDisplay: String {
        if let year = releaseYear {
            return String(year)
        }
        return "Unknown year"
    }

    var formatDisplay: String {
        formatName ?? "Unknown format"
    }

    var canFlipToBackCover: Bool {
        hasBackCover == true && backCoverArtMedium != nil
    }
}

import Foundation

/// Response from /api/musicbrainz/works/search
struct MusicBrainzSearchResponse: Codable {
    let query: String
    let results: [MusicBrainzWork]
}

/// A work (song) from MusicBrainz search results
struct MusicBrainzWork: Codable, Identifiable {
    let id: String
    let title: String
    let composers: [String]?
    let score: Int?
    let type: String?
    let musicbrainzUrl: String

    enum CodingKeys: String, CodingKey {
        case id, title, composers, score, type
        case musicbrainzUrl = "musicbrainz_url"
    }

    var composerDisplay: String {
        guard let composers = composers, !composers.isEmpty else {
            return "Unknown composer"
        }
        return composers.joined(separator: ", ")
    }

    var matchQuality: String {
        guard let score = score else { return "" }
        if score >= 90 { return "Excellent match" }
        if score >= 70 { return "Good match" }
        if score >= 50 { return "Possible match" }
        return "Weak match"
    }

    // MARK: - Preview Data

    static var preview1: MusicBrainzWork {
        MusicBrainzWork(
            id: "a74b1b7f-71a5-311f-8151-4c86ebfc8d8e",
            title: "Autumn Leaves",
            composers: ["Joseph Kosma"],
            score: 100,
            type: "Song",
            musicbrainzUrl: "https://musicbrainz.org/work/a74b1b7f-71a5-311f-8151-4c86ebfc8d8e"
        )
    }

    static var preview2: MusicBrainzWork {
        MusicBrainzWork(
            id: "b85c2c8f-82b6-422f-9262-5d97fce9e9f9",
            title: "Giant Steps",
            composers: ["John Coltrane"],
            score: 95,
            type: "Song",
            musicbrainzUrl: "https://musicbrainz.org/work/b85c2c8f-82b6-422f-9262-5d97fce9e9f9"
        )
    }

    static var previewMinimal: MusicBrainzWork {
        MusicBrainzWork(
            id: "c96d3d9f-93c7-533f-a373-6e08gdf0f0f0",
            title: "Autumn Leaves (alternate)",
            composers: nil,
            score: 60,
            type: nil,
            musicbrainzUrl: "https://musicbrainz.org/work/c96d3d9f-93c7-533f-a373-6e08gdf0f0f0"
        )
    }
}

/// Response from /api/musicbrainz/import
struct MusicBrainzImportResponse: Codable {
    let success: Bool
    let message: String
    let song: Song?
    let researchQueued: Bool?
    let queueSize: Int?

    enum CodingKeys: String, CodingKey {
        case success, message, song
        case researchQueued = "research_queued"
        case queueSize = "queue_size"
    }
}

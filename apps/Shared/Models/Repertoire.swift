import Foundation

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

    func hash(into hasher: inout Hasher) {
        hasher.combine(id)
    }

    static func == (lhs: Repertoire, rhs: Repertoire) -> Bool {
        lhs.id == rhs.id
    }

    /// Special repertoire option for "All Songs"
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

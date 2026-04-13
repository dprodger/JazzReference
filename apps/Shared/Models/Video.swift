import Foundation

struct Video: Codable, Identifiable {
    let id: String
    let songId: String
    let recordingId: String?
    let youtubeUrl: String?
    let title: String?
    let description: String?
    let videoType: String
    let durationSeconds: Int?
    let tempo: Int?
    let keySignature: String?
    let createdAt: String?
    let updatedAt: String?

    enum CodingKeys: String, CodingKey {
        case id
        case songId = "song_id"
        case recordingId = "recording_id"
        case youtubeUrl = "youtube_url"
        case title, description
        case videoType = "video_type"
        case durationSeconds = "duration_seconds"
        case tempo
        case keySignature = "key_signature"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }

    // MARK: - Preview Data

    static var preview1: Video {
        Video(
            id: "preview-video-1",
            songId: "preview-song-1",
            recordingId: nil,
            youtubeUrl: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            title: "All of Me - Backing Track in C",
            description: "Professional backing track for practice",
            videoType: "backing_track",
            durationSeconds: 300,
            tempo: 130,
            keySignature: "C Major",
            createdAt: "2024-01-15T10:30:00Z",
            updatedAt: "2024-01-15T10:30:00Z"
        )
    }

    static var preview2: Video {
        Video(
            id: "preview-video-2",
            songId: "preview-song-1",
            recordingId: nil,
            youtubeUrl: "https://www.youtube.com/watch?v=abc123xyz",
            title: "All of Me - Slow Tempo Practice",
            description: nil,
            videoType: "backing_track",
            durationSeconds: 360,
            tempo: 100,
            keySignature: nil,
            createdAt: "2024-02-20T14:15:00Z",
            updatedAt: "2024-02-20T14:15:00Z"
        )
    }
}

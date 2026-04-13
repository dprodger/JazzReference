import Foundation

struct SoloTranscription: Codable, Identifiable {
    let id: String
    let songId: String
    let recordingId: String?
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

    // MARK: - Preview Data

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

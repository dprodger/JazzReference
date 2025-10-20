//
//  PreviewHelpers.swift
//  JazzReference
//
//  Preview mock data for SwiftUI previews
//

import Foundation

#if DEBUG

// MARK: - Mock Data Extensions

extension Song {
    static let preview = Song(
        id: "preview-song-1",
        title: "Take Five",
        composer: "Paul Desmond",
        structure: "AABA form in 5/4 time",
        songReference: "One of the most iconic jazz compositions, known for its unusual 5/4 time signature.",
        externalReferences: [
            "wikipedia": "https://en.wikipedia.org/wiki/Take_Five",
            "jazzstandards": "https://www.jazzstandards.com/compositions/takefive.htm"
        ],
        recordings: [Recording.preview1, Recording.preview2],
        recordingCount: 2
    )
    
    static let previewNoRecordings = Song(
        id: "preview-song-2",
        title: "Blue in Green",
        composer: "Miles Davis / Bill Evans",
        structure: "10-bar form",
        songReference: "A hauntingly beautiful ballad from Kind of Blue.",
        externalReferences: nil,
        recordings: [],
        recordingCount: 0
    )
}

extension Recording {
    static let preview1 = Recording(
        id: "preview-recording-1",
        songId: "preview-song-1",
        songTitle: "Take Five",
        albumTitle: "Time Out",
        recordingDate: "1959-07-01",
        recordingYear: 1959,
        label: "Columbia Records",
        spotifyUrl: "https://open.spotify.com/track/example",
        youtubeUrl: "https://youtube.com/watch?v=example",
        appleMusicUrl: "https://music.apple.com/album/example",
        isCanonical: true,
        notes: "The definitive recording that made this song famous worldwide.",
        performers: [Performer.preview1, Performer.preview2, Performer.preview3],
        composer: "Paul Desmond"
    )
    
    static let preview2 = Recording(
        id: "preview-recording-2",
        songId: "preview-song-1",
        songTitle: "Take Five",
        albumTitle: "Jazz Impressions of Japan",
        recordingDate: nil,
        recordingYear: 1964,
        label: "Columbia",
        spotifyUrl: nil,
        youtubeUrl: "https://youtube.com/watch?v=example2",
        appleMusicUrl: nil,
        isCanonical: false,
        notes: "Live recording from their Japan tour.",
        performers: [Performer.preview1, Performer.preview4],
        composer: "Paul Desmond"
    )
    
    static let previewMinimal = Recording(
        id: "preview-recording-3",
        songId: nil,
        songTitle: "Blue Rondo à la Turk",
        albumTitle: "Time Out",
        recordingDate: nil,
        recordingYear: 1959,
        label: nil,
        spotifyUrl: nil,
        youtubeUrl: nil,
        appleMusicUrl: nil,
        isCanonical: false,
        notes: nil,
        performers: nil,
        composer: nil
    )
}

extension Performer {
    static let preview1 = Performer(
        id: "preview-performer-1",
        name: "Dave Brubeck",
        instrument: "Piano",
        role: "leader",
        biography: nil,
        birthDate: nil,
        deathDate: nil
    )
    
    static let preview2 = Performer(
        id: "preview-performer-2",
        name: "Paul Desmond",
        instrument: "Alto Saxophone",
        role: "sideman",
        biography: nil,
        birthDate: nil,
        deathDate: nil
    )
    
    static let preview3 = Performer(
        id: "preview-performer-3",
        name: "Joe Morello",
        instrument: "Drums",
        role: "sideman",
        biography: nil,
        birthDate: nil,
        deathDate: nil
    )
    
    static let preview4 = Performer(
        id: "preview-performer-4",
        name: "Eugene Wright",
        instrument: "Bass",
        role: "sideman",
        biography: nil,
        birthDate: nil,
        deathDate: nil
    )
}

extension PerformerDetail {
    static let preview = PerformerDetail(
        id: "preview-performer-detail-1",
        name: "Miles Davis",
        biography: "Miles Dewey Davis III was an American jazz trumpeter, bandleader, and composer. He is among the most influential and acclaimed figures in the history of jazz and 20th-century music.",
        birthDate: "1926-05-26",
        deathDate: "1991-09-28",
        externalLinks: [
            "wikipedia": "https://en.wikipedia.org/wiki/Miles_Davis"
        ],
        instruments: [
            PerformerInstrument(name: "Trumpet", isPrimary: true),
            PerformerInstrument(name: "Flugelhorn", isPrimary: false)
        ],
        recordings: [
            PerformerRecording(
                songId: "song-1",
                songTitle: "So What",
                recordingId: "rec-1",
                albumTitle: "Kind of Blue",
                recordingYear: 1959,
                isCanonical: true,
                role: "leader"
            ),
            PerformerRecording(
                songId: "song-2",
                songTitle: "All Blues",
                recordingId: "rec-2",
                albumTitle: "Kind of Blue",
                recordingYear: 1959,
                isCanonical: true,
                role: "leader"
            ),
            PerformerRecording(
                songId: "song-3",
                songTitle: "Round Midnight",
                recordingId: "rec-3",
                albumTitle: "Round About Midnight",
                recordingYear: 1957,
                isCanonical: false,
                role: "leader"
            )
        ]
    )
    
    static let previewMinimal = PerformerDetail(
        id: "preview-performer-detail-2",
        name: "John Coltrane",
        biography: nil,
        birthDate: nil,
        deathDate: nil,
        externalLinks: nil,
        instruments: [
            PerformerInstrument(name: "Tenor Saxophone", isPrimary: true)
        ],
        recordings: []
    )
}

// MARK: - Preview Mode Support

extension NetworkManager {
    static var isPreviewMode: Bool {
        ProcessInfo.processInfo.environment["XCODE_RUNNING_FOR_PREVIEWS"] == "1"
    }
    
    static var preview: NetworkManager {
        let manager = NetworkManager()
        manager.setupPreviewData()
        return manager
    }
    
    private func setupPreviewData() {
        // Set up mock data that can be accessed synchronously
    }
    
    func fetchSongDetailSync(id: String) -> Song? {
        if Self.isPreviewMode {
            switch id {
            case "preview-song-1":
                return Song.preview
            case "preview-song-2":
                return Song.previewNoRecordings
            default:
                return Song.preview
            }
        }
        return nil
    }
    
    func fetchRecordingDetailSync(id: String) -> Recording? {
        if Self.isPreviewMode {
            switch id {
            case "preview-recording-1":
                return Recording.preview1
            case "preview-recording-2":
                return Recording.preview2
            case "preview-recording-3":
                return Recording.previewMinimal
            default:
                return Recording.preview1
            }
        }
        return nil
    }
    
    func fetchPerformerDetailSync(id: String) -> PerformerDetail? {
        if Self.isPreviewMode {
            switch id {
            case "preview-performer-detail-1":
                return PerformerDetail.preview
            case "preview-performer-detail-2":
                return PerformerDetail.previewMinimal
            default:
                return PerformerDetail.preview
            }
        }
        return nil
    }
}

#endif

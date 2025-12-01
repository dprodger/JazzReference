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
        musicbrainzId: "musicbrainz id",
        wikipediaUrl: "wiki id",
        externalReferences: [
            "wikipedia": "https://en.wikipedia.org/wiki/Take_Five",
            "jazzstandards": "https://www.jazzstandards.com/compositions/takefive.htm"
        ],
        createdAt: "2024-01-15T10:30:00Z",
        updatedAt: "2024-01-15T10:30:00Z",
        recordings: [Recording.preview1, Recording.preview2],
        recordingCount: 2,
        transcriptions: [SoloTranscription.preview1, SoloTranscription.preview2],
        transcriptionCount: 2
    )
    
    static let previewNoRecordings = Song(
        id: "preview-song-2",
        title: "Blue in Green",
        composer: "Miles Davis / Bill Evans",
        structure: "10-bar form",
        songReference: "A hauntingly beautiful ballad from Kind of Blue.",
        musicbrainzId: "musicbrainz id",
        wikipediaUrl: "wiki id",
        externalReferences: nil,
        createdAt: "2024-01-15T10:30:00Z",
        updatedAt: "2024-01-15T10:30:00Z",
        recordings: [],
        recordingCount: 0,
        transcriptions: [],
        transcriptionCount: 0
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
        spotifyTrackId: "trackid",
        albumArtSmall: "https://open.spotify.com/image/foo_small.jpg",
        albumArtMedium: "https://open.spotify.com/image/foo_medium.jpg",
        albumArtLarge: "https://open.spotify.com/image/foo_large.jpg",
        youtubeUrl: "https://youtube.com/watch?v=example",
        appleMusicUrl: "https://music.apple.com/album/example",
        musicbrainzId: "mbid",
        isCanonical: true,
        notes: "The definitive recording that made this song famous worldwide.",
        performers: [Performer.preview1, Performer.preview2, Performer.preview3],
        composer: "Paul Desmond",
        releases: [Release.preview, Release.previewNoSpotify]
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
        spotifyTrackId: nil,
        albumArtSmall: nil,
        albumArtMedium: nil,
        albumArtLarge: nil,
        youtubeUrl: "https://youtube.com/watch?v=example2",
        appleMusicUrl: nil,
        musicbrainzId: "mbid",
        isCanonical: false,
        notes: "Live recording from their Japan tour.",
        performers: [Performer.preview1, Performer.preview4],
        composer: "Paul Desmond",
        releases: nil
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
        spotifyTrackId: nil,
        albumArtSmall: nil,
        albumArtMedium: nil,
        albumArtLarge: nil,
        youtubeUrl: nil,
        appleMusicUrl: nil,
        musicbrainzId: "mbid",
        isCanonical: false,
        notes: nil,
        performers: nil,
        composer: nil,
        releases: nil
    )
}

extension Release {
    static let preview = Release(
        id: "preview-release-1",
        title: "Time Out",
        artistCredit: "The Dave Brubeck Quartet",
        releaseDate: "1959-12-14",
        releaseYear: 1959,
        country: "US",
        label: "Columbia",
        catalogNumber: "CL 1397",
        spotifyAlbumId: "0nTTEAhCZsbbeplyDMIFuA",
        spotifyAlbumUrl: "https://open.spotify.com/album/0nTTEAhCZsbbeplyDMIFuA",
        spotifyTrackId: "1YQWosTIljIvxAgHWTp7KP",
        spotifyTrackUrl: "https://open.spotify.com/track/1YQWosTIljIvxAgHWTp7KP",
        coverArtSmall: "https://i.scdn.co/image/ab67616d0000485196384c98ac4f3e7c2440f5b5",
        coverArtMedium: "https://i.scdn.co/image/ab67616d0000b27396384c98ac4f3e7c2440f5b5",
        coverArtLarge: "https://i.scdn.co/image/ab67616d000082c196384c98ac4f3e7c2440f5b5",
        discNumber: 1,
        trackNumber: 1,
        totalTracks: 7,
        formatName: "CD",
        statusName: "official",
        musicbrainzReleaseId: "b84ee12a-09ef-421b-82de-0441a926375b",
        performers: nil,
        performerCount: 4
    )
    
    static let previewNoSpotify = Release(
        id: "preview-release-2",
        title: "Time Out (Original Mono)",
        artistCredit: "The Dave Brubeck Quartet",
        releaseDate: "1959-12-14",
        releaseYear: 1959,
        country: "US",
        label: "Columbia",
        catalogNumber: "CL 1397",
        spotifyAlbumId: nil,
        spotifyAlbumUrl: nil,
        spotifyTrackId: nil,
        spotifyTrackUrl: nil,
        coverArtSmall: nil,
        coverArtMedium: nil,
        coverArtLarge: nil,
        discNumber: 1,
        trackNumber: 1,
        totalTracks: 7,
        formatName: "12\" Vinyl",
        statusName: "official",
        musicbrainzReleaseId: "c94ee12a-09ef-421b-82de-0441a926375c",
        performers: nil,
        performerCount: 4
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
        wikipediaUrl: "https://en.wikipedia.org/wiki/Miles_Davis",
        musicbrainzId: "mb-id",
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
        ],
        images: nil
    )
    
    static let previewMinimal = PerformerDetail(
        id: "preview-performer-detail-2",
        name: "John Coltrane",
        biography: nil,
        birthDate: nil,
        deathDate: nil,
        externalLinks: nil,
        wikipediaUrl: "wikipedia.org/john_coltrane",
        musicbrainzId: "mb-id",
        instruments: [
            PerformerInstrument(name: "Tenor Saxophone", isPrimary: true)
        ],
        recordings: [],
        images: nil
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

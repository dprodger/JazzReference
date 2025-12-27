//
//  ArtistData.swift
//  JazzReference
//
//  Created by Dave Rodger on 11/1/25.
//


// MARK: - Data Models (Must be in extension target)

struct ArtistData: Codable {
    let name: String
    let musicbrainzId: String
    let wikipediaUrl: String?
    let sourceUrl: String?
}

// MARK: - Artist Match Result

enum ArtistMatchResult {
    case notFound                    // Artist doesn't exist at all
    case exactMatch(existingArtist: ExistingArtist)  // Same name and same MusicBrainz ID
    case nameMatchNoMbid(existingArtist: ExistingArtist)  // Same name but blank MusicBrainz ID
    case nameMatchDifferentMbid(existingArtist: ExistingArtist)  // Same name but different MusicBrainz ID
}

struct ExistingArtist: Codable {
    let id: String
    let name: String
    let biography: String?
    let birthDate: String?
    let deathDate: String?
    var musicbrainzId: String?
    
    var shortBio: String {
        guard let bio = biography, !bio.isEmpty else {
            return "No biography available"
        }
        // Return first 200 characters
        let prefix = String(bio.prefix(200))
        return bio.count > 200 ? prefix + "..." : prefix
    }
    
    enum CodingKeys: String, CodingKey {
        case id, name, biography
        case birthDate = "birth_date"
        case deathDate = "death_date"
        case musicbrainzId = "musicbrainz_id"
    }
}

// MARK: - Song Data Models

struct SongData: Codable {
    let title: String
    let musicbrainzId: String
    let composers: [String]?
    let workType: String?
    let key: String?
    let annotation: String?
    let wikipediaUrl: String?
    let sourceUrl: String?
    
    var composerString: String? {
        guard let composers = composers, !composers.isEmpty else {
            return nil
        }
        return composers.joined(separator: ", ")
    }
}

enum SongMatchResult {
    case notFound
    case exactMatch(existingSong: ExistingSong)
    case titleMatchNoMbid(existingSong: ExistingSong)
    case titleMatchDifferentMbid(existingSong: ExistingSong)
}

struct ExistingSong: Codable {
    let id: String
    let title: String
    let composer: String?
    let structure: String?
    var musicbrainzId: String?

    var shortInfo: String {
        if let composer = composer, !composer.isEmpty {
            return "by \(composer)"
        }
        return "No composer information"
    }

    enum CodingKeys: String, CodingKey {
        case id, title, composer, structure
        case musicbrainzId = "musicbrainz_id"
    }
}

// MARK: - YouTube Data Models

enum YouTubeVideoType: String, Codable {
    case transcription = "transcription"
    case backingTrack = "backing_track"

    var displayName: String {
        switch self {
        case .transcription:
            return "Solo Transcription"
        case .backingTrack:
            return "Backing Track"
        }
    }

    var description: String {
        switch self {
        case .transcription:
            return "A video showing a transcribed solo with notation or analysis"
        case .backingTrack:
            return "A play-along or backing track for practicing"
        }
    }

    var iconName: String {
        switch self {
        case .transcription:
            return "music.quarternote.3"
        case .backingTrack:
            return "play.circle"
        }
    }
}

struct YouTubeData: Codable {
    let videoId: String
    let title: String
    let url: String
    let channelName: String?
    let description: String?
    var videoType: YouTubeVideoType?
    var songId: String?
    var recordingId: String?
}

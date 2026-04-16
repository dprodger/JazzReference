//
//  SharedDataManagers.swift
//  Approach Note
//
//  Handles shared data from the MusicBrainz Safari Share Extension
//  THIS FILE GOES IN THE MAC APP TARGET ONLY
//

import Foundation
import os

// MARK: - Imported Artist Data

/// Artist data structure shared between the extension and main app
struct ImportedArtistData: Codable, Identifiable {
    let id = UUID()
    let name: String
    let musicbrainzId: String
    let sourceUrl: String?
    let importedAt: Date

    enum CodingKeys: String, CodingKey {
        case name, musicbrainzId, sourceUrl, importedAt
    }

    init(name: String, musicbrainzId: String, sourceUrl: String?, importedAt: Date = Date()) {
        self.name = name
        self.musicbrainzId = musicbrainzId
        self.sourceUrl = sourceUrl
        self.importedAt = importedAt
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        name = try container.decode(String.self, forKey: .name)
        musicbrainzId = try container.decode(String.self, forKey: .musicbrainzId)
        sourceUrl = try container.decodeIfPresent(String.self, forKey: .sourceUrl)
        importedAt = try container.decodeIfPresent(Date.self, forKey: .importedAt) ?? Date()
    }
}

/// Manager for handling shared artist data between extension and main app
class SharedArtistDataManager {

    private static let appGroupIdentifier = "group.me.rodger.david.JazzReference"
    private static let sharedDataKey = "pendingArtistImport"

    /// Retrieve artist data in the main app
    static func retrieveSharedData() -> ImportedArtistData? {
        guard let sharedDefaults = UserDefaults(suiteName: appGroupIdentifier) else {
            Log.data.error("Failed to access App Group UserDefaults")
            return nil
        }

        guard let savedData = sharedDefaults.data(forKey: sharedDataKey) else {
            return nil
        }

        Log.data.debug("Found pending artist import data")

        let decoder = JSONDecoder()
        // Don't use ISO8601 - extension uses default encoding

        do {
            // Try to decode with timestamp first
            let artistData = try decoder.decode(ImportedArtistDataWithTimestamp.self, from: savedData)

            let result = ImportedArtistData(
                name: artistData.name,
                musicbrainzId: artistData.musicbrainzId,
                sourceUrl: artistData.sourceUrl,
                importedAt: Date()
            )

            clearSharedData()
            let name = result.name
            Log.data.info("Retrieved artist data: \(name, privacy: .public)")
            return result

        } catch {
            Log.data.warning("Could not decode with timestamp, trying simple format...")

            do {
                let basicData = try decoder.decode(BasicArtistData.self, from: savedData)
                let result = ImportedArtistData(
                    name: basicData.name,
                    musicbrainzId: basicData.musicbrainzId,
                    sourceUrl: basicData.sourceUrl,
                    importedAt: Date()
                )

                clearSharedData()
                let basicName = result.name
                Log.data.info("Retrieved artist data (basic format): \(basicName, privacy: .public)")
                return result

            } catch {
                Log.data.error("Failed to decode artist data: \(error.localizedDescription)")
                clearSharedData()
                return nil
            }
        }
    }

    /// Check if there's pending artist data to import
    static func hasPendingData() -> Bool {
        guard let sharedDefaults = UserDefaults(suiteName: appGroupIdentifier) else {
            return false
        }
        return sharedDefaults.data(forKey: sharedDataKey) != nil
    }

    /// Clear the shared data
    static func clearSharedData() {
        guard let sharedDefaults = UserDefaults(suiteName: appGroupIdentifier) else {
            return
        }
        sharedDefaults.removeObject(forKey: sharedDataKey)
        sharedDefaults.synchronize()
        Log.data.debug("Cleared pending artist import data")
    }
}

// MARK: - Internal Data Models for Decoding

private struct ImportedArtistDataWithTimestamp: Codable {
    let name: String
    let musicbrainzId: String
    let sourceUrl: String?
    let importedAt: Date
}

private struct BasicArtistData: Codable {
    let name: String
    let musicbrainzId: String
    let sourceUrl: String?
    let wikipediaUrl: String?
}

// MARK: - Imported Song Data

/// Data structure for song imported from the share extension
struct ImportedSongData: Identifiable {
    let id = UUID()
    let title: String
    let musicbrainzId: String
    let composers: [String]?
    let workType: String?
    let key: String?
    let annotation: String?
    let wikipediaUrl: String?
    let sourceUrl: String?
    let importedAt: Date

    var composerString: String? {
        guard let composers = composers, !composers.isEmpty else {
            return nil
        }
        return composers.joined(separator: ", ")
    }
}

/// Manager for handling shared song data between extension and main app
class SharedSongDataManager {

    private static let appGroupIdentifier = "group.me.rodger.david.JazzReference"
    private static let sharedDataKey = "pendingSongImport"

    /// Retrieve song data in the main app
    static func retrieveSharedData() -> ImportedSongData? {
        guard let sharedDefaults = UserDefaults(suiteName: appGroupIdentifier) else {
            Log.data.error("Failed to access App Group UserDefaults")
            return nil
        }

        guard let savedData = sharedDefaults.data(forKey: sharedDataKey) else {
            return nil
        }

        Log.data.debug("Found pending song import data")

        let decoder = JSONDecoder()
        // Don't use ISO8601 - extension uses default encoding

        do {
            let songData = try decoder.decode(SongDataFromExtension.self, from: savedData)
            let songTitle = songData.title
            Log.data.debug("Successfully decoded song data: \(songTitle, privacy: .public)")

            let result = ImportedSongData(
                title: songData.title,
                musicbrainzId: songData.musicbrainzId,
                composers: songData.composers,
                workType: songData.workType,
                key: songData.key,
                annotation: songData.annotation,
                wikipediaUrl: songData.wikipediaUrl,
                sourceUrl: songData.sourceUrl,
                importedAt: Date()
            )

            clearSharedData()
            let title = result.title
            Log.data.info("Retrieved song data: \(title, privacy: .public)")
            return result

        } catch {
            Log.data.error("Failed to decode song data: \(error.localizedDescription)")
            clearSharedData()
            return nil
        }
    }

    /// Check if there's pending song data to import
    static func hasPendingData() -> Bool {
        guard let sharedDefaults = UserDefaults(suiteName: appGroupIdentifier) else {
            return false
        }
        return sharedDefaults.data(forKey: sharedDataKey) != nil
    }

    /// Clear the shared data
    static func clearSharedData() {
        guard let sharedDefaults = UserDefaults(suiteName: appGroupIdentifier) else {
            return
        }
        sharedDefaults.removeObject(forKey: sharedDataKey)
        sharedDefaults.synchronize()
        Log.data.debug("Cleared pending song import data")
    }
}

private struct SongDataFromExtension: Codable {
    let title: String
    let musicbrainzId: String
    let composers: [String]?
    let workType: String?
    let key: String?
    let annotation: String?
    let wikipediaUrl: String?
    let sourceUrl: String?
}

// MARK: - YouTube Data Manager

/// YouTube data structure shared between the extension and main app
struct ImportedYouTubeData: Codable, Identifiable {
    let id = UUID()
    let videoId: String
    let title: String
    let url: String
    let channelName: String?
    let description: String?
    let videoType: YouTubeVideoType
    var songId: String?
    var recordingId: String?
    let importedAt: Date

    enum CodingKeys: String, CodingKey {
        case videoId, title, url, channelName, description, videoType, songId, recordingId, importedAt
    }

    init(videoId: String, title: String, url: String, channelName: String?, description: String?,
         videoType: YouTubeVideoType, songId: String? = nil, recordingId: String? = nil, importedAt: Date = Date()) {
        self.videoId = videoId
        self.title = title
        self.url = url
        self.channelName = channelName
        self.description = description
        self.videoType = videoType
        self.songId = songId
        self.recordingId = recordingId
        self.importedAt = importedAt
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        videoId = try container.decode(String.self, forKey: .videoId)
        title = try container.decode(String.self, forKey: .title)
        url = try container.decode(String.self, forKey: .url)
        channelName = try container.decodeIfPresent(String.self, forKey: .channelName)
        description = try container.decodeIfPresent(String.self, forKey: .description)
        videoType = try container.decode(YouTubeVideoType.self, forKey: .videoType)
        songId = try container.decodeIfPresent(String.self, forKey: .songId)
        recordingId = try container.decodeIfPresent(String.self, forKey: .recordingId)
        importedAt = try container.decodeIfPresent(Date.self, forKey: .importedAt) ?? Date()
    }
}

/// Video type enum (must match the extension's definition)
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
}

/// Manager for handling shared YouTube data between extension and main app
class SharedYouTubeDataManager {

    private static let appGroupIdentifier = "group.me.rodger.david.JazzReference"
    private static let sharedDataKey = "pendingYouTubeImport"

    /// Retrieve YouTube data in the main app
    static func retrieveSharedData() -> ImportedYouTubeData? {
        guard let sharedDefaults = UserDefaults(suiteName: appGroupIdentifier) else {
            Log.data.error("Failed to access App Group UserDefaults")
            return nil
        }

        guard let savedData = sharedDefaults.data(forKey: sharedDataKey) else {
            return nil
        }

        Log.data.debug("Found pending YouTube import data")

        let decoder = JSONDecoder()

        do {
            let youtubeData = try decoder.decode(YouTubeDataFromExtension.self, from: savedData)
            let ytTitle = youtubeData.title
            Log.data.debug("Successfully decoded YouTube data: \(ytTitle, privacy: .public)")

            guard let videoType = youtubeData.videoType else {
                Log.data.warning("No video type set in YouTube data")
                clearSharedData()
                return nil
            }

            let result = ImportedYouTubeData(
                videoId: youtubeData.videoId,
                title: youtubeData.title,
                url: youtubeData.url,
                channelName: youtubeData.channelName,
                description: youtubeData.description,
                videoType: videoType,
                songId: youtubeData.songId,
                recordingId: youtubeData.recordingId,
                importedAt: Date()
            )

            clearSharedData()
            let retrievedTitle = result.title
            Log.data.info("Retrieved YouTube data: \(retrievedTitle, privacy: .public)")
            return result

        } catch {
            Log.data.error("Failed to decode YouTube data: \(error.localizedDescription)")
            clearSharedData()
            return nil
        }
    }

    /// Check if there's pending YouTube data to import
    static func hasPendingData() -> Bool {
        guard let sharedDefaults = UserDefaults(suiteName: appGroupIdentifier) else {
            return false
        }
        return sharedDefaults.data(forKey: sharedDataKey) != nil
    }

    /// Clear the shared data
    static func clearSharedData() {
        guard let sharedDefaults = UserDefaults(suiteName: appGroupIdentifier) else {
            return
        }
        sharedDefaults.removeObject(forKey: sharedDataKey)
        sharedDefaults.synchronize()
        Log.data.debug("Cleared pending YouTube import data")
    }
}

private struct YouTubeDataFromExtension: Codable {
    let videoId: String
    let title: String
    let url: String
    let channelName: String?
    let description: String?
    let videoType: YouTubeVideoType?
    let songId: String?
    let recordingId: String?
}

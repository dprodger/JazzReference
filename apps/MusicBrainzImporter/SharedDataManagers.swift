//
//  SharedDataManagers.swift
//  Approach Note
//
//  Created by Dave Rodger on 11/1/25.
//

import Foundation
import os

private let logger = Logger(subsystem: Bundle.main.bundleIdentifier ?? "com.approachnote.MusicBrainzImporter", category: "data")

// MARK: - Shared Data Manager

class SharedArtistData {
    static func saveSharedData(_ artistData: ArtistData, appGroup: String) {
        guard let sharedDefaults = UserDefaults(suiteName: appGroup) else {
            logger.error("Failed to get shared UserDefaults")
            return
        }

        let encoder = JSONEncoder()
        if let encoded = try? encoder.encode(artistData) {
            sharedDefaults.set(encoded, forKey: "pendingArtistImport")
            sharedDefaults.synchronize()
            logger.info("Artist data saved to shared container")
        } else {
            logger.error("Failed to encode artist data")
        }
    }
}

class SharedSongData {
    static func saveSharedData(_ songData: SongData, appGroup: String) {
        guard let sharedDefaults = UserDefaults(suiteName: appGroup) else {
            logger.error("Failed to get shared UserDefaults")
            return
        }

        let encoder = JSONEncoder()
        if let encoded = try? encoder.encode(songData) {
            sharedDefaults.set(encoded, forKey: "pendingSongImport")
            sharedDefaults.removeObject(forKey: "pendingArtistImport") // Clear any pending artist import
            sharedDefaults.synchronize()
            logger.info("Song data saved to shared container")
        } else {
            logger.error("Failed to encode song data")
        }
    }
}

class SharedYouTubeData {
    static func saveSharedData(_ youtubeData: YouTubeData, appGroup: String) {
        guard let sharedDefaults = UserDefaults(suiteName: appGroup) else {
            logger.error("Failed to get shared UserDefaults")
            return
        }

        let encoder = JSONEncoder()
        if let encoded = try? encoder.encode(youtubeData) {
            sharedDefaults.set(encoded, forKey: "pendingYouTubeImport")
            // Clear any other pending imports
            sharedDefaults.removeObject(forKey: "pendingArtistImport")
            sharedDefaults.removeObject(forKey: "pendingSongImport")
            sharedDefaults.synchronize()
            logger.info("YouTube data saved to shared container")
        } else {
            logger.error("Failed to encode YouTube data")
        }
    }
}


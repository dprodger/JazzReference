//
//  SharedSongDataManager.swift
//  Approach Note
//
//  Created by Dave Rodger on 11/1/25.
//

import Foundation
import os

// MARK: - Imported Song Data Model

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
    
    private static let appGroupIdentifier = "group.com.approachnote.shared"
    private static let sharedDataKey = "pendingSongImport"
    
    /// Retrieve song data in the main app
    /// Call this when your app launches to check for pending imports
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
        decoder.dateDecodingStrategy = .iso8601

        do {
            // Decode the SongData from the extension
            let songData = try decoder.decode(SongData.self, from: savedData)

            // Convert to ImportedSongData
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

            // Clear the data after reading
            clearSharedData()
            let title = result.title
            Log.data.info("Retrieved song data: \(title, privacy: .public)")
            return result

        } catch {
            Log.data.error("Failed to decode song data: \(error.localizedDescription)")
            // Clear corrupted data
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
// MARK: - Private Decoding Model

/// Private struct matching the SongData structure from the share extension
/// Used only for decoding the saved data
private struct SongData: Codable {
    let title: String
    let musicbrainzId: String
    let composers: [String]?
    let workType: String?
    let key: String?
    let annotation: String?
    let wikipediaUrl: String?
    let sourceUrl: String?
}

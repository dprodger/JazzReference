//
//  SharedArtistData.swift
//  JazzReference
//
//  Handles artist data shared from the MusicBrainz Safari Share Extension
//  THIS FILE GOES IN THE MAIN APP TARGET ONLY
//

import Foundation

/// Artist data structure shared between the extension and main app
struct ImportedArtistData: Codable, Identifiable {
    let id = UUID()
    let name: String
    let musicbrainzId: String
    let sourceUrl: String?
    let importedAt: Date
    
}

/// Manager for handling shared artist data between extension and main app
/// USE THIS CLASS IN THE MAIN APP TO RETRIEVE IMPORTED DATA
class SharedArtistDataManager {
    
    private static let appGroupIdentifier = "group.me.rodger.david.JazzReference"
    private static let sharedDataKey = "pendingArtistImport"
    
    /// Retrieve artist data in the main app
    /// Call this when your app launches to check for pending imports
    static func retrieveSharedData() -> ImportedArtistData? {
        print("🔍 Checking for pending artist import...")
        
        guard let sharedDefaults = UserDefaults(suiteName: appGroupIdentifier) else {
            print("❌ Failed to access App Group UserDefaults")
            return nil
        }
        
        guard let savedData = sharedDefaults.data(forKey: sharedDataKey) else {
            print("ℹ️ No pending import found")
            return nil
        }
        
        print("✓ Found pending import data")
        
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        
        do {
            // First, try to decode with timestamp (new format from extension)
            let artistData = try decoder.decode(ImportedArtistDataWithTimestamp.self, from: savedData)
            
            // Convert to ImportedArtistData
            let result = ImportedArtistData(
                name: artistData.name,
                musicbrainzId: artistData.musicbrainzId,
                sourceUrl: artistData.sourceUrl,
                importedAt: Date() // Current time
            )
            
            // Clear the data after reading
            clearSharedData()
            print("✅ Retrieved artist data: \(result.name)")
            return result
            
        } catch {
            print("⚠️ Could not decode with timestamp, trying simple format...")
            
            // Try simpler format (just the basic artist data)
            do {
                let basicData = try decoder.decode(BasicArtistData.self, from: savedData)
                let result = ImportedArtistData(
                    name: basicData.name,
                    musicbrainzId: basicData.musicbrainzId,
                    sourceUrl: basicData.sourceUrl,
                    importedAt: Date()
                )
                
                clearSharedData()
                print("✅ Retrieved artist data (basic format): \(result.name)")
                return result
                
            } catch {
                print("❌ Failed to decode artist data: \(error)")
                // Clear corrupted data
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
        print("🗑️ Cleared pending import data")
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
}

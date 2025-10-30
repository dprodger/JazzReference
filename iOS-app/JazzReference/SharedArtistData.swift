//
//  SharedArtistData.swift
//  JazzReference
//
//  Handles artist data shared from the MusicBrainz Safari Share Extension
//  THIS FILE GOES IN THE MAIN APP TARGET ONLY
//

import Foundation

/// Artist data structure shared between the extension and main app
struct ImportedArtistData: Codable {
    let name: String
    let musicbrainzId: String
    let biography: String?
    let birthDate: String?
    let deathDate: String?
    let instruments: [String]?
    let wikipediaUrl: String?
    let sourceUrl: String?
    let importedAt: Date
    
    var formattedBirthDate: String? {
        guard let birthDate = birthDate else { return nil }
        return formatDate(birthDate)
    }
    
    var formattedDeathDate: String? {
        guard let deathDate = deathDate else { return nil }
        return formatDate(deathDate)
    }
    
    private func formatDate(_ dateString: String) -> String {
        // Handle various date formats from MusicBrainz
        // e.g., "1926-05-26", "1926-05", "1926"
        let components = dateString.split(separator: "-")
        
        switch components.count {
        case 3: // Full date: YYYY-MM-DD
            return dateString
        case 2: // Year and month: YYYY-MM
            return dateString
        case 1: // Just year: YYYY
            return String(components[0])
        default:
            return dateString
        }
    }
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
                biography: artistData.biography,
                birthDate: artistData.birthDate,
                deathDate: artistData.deathDate,
                instruments: artistData.instruments,
                wikipediaUrl: artistData.wikipediaUrl,
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
                    biography: basicData.biography,
                    birthDate: basicData.birthDate,
                    deathDate: basicData.deathDate,
                    instruments: basicData.instruments,
                    wikipediaUrl: basicData.wikipediaUrl,
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
    let biography: String?
    let birthDate: String?
    let deathDate: String?
    let instruments: [String]?
    let wikipediaUrl: String?
    let sourceUrl: String?
    let importedAt: Date
}

private struct BasicArtistData: Codable {
    let name: String
    let musicbrainzId: String
    let biography: String?
    let birthDate: String?
    let deathDate: String?
    let instruments: [String]?
    let wikipediaUrl: String?
    let sourceUrl: String?
}

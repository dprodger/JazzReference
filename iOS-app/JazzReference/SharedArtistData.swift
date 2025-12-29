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
        guard let sharedDefaults = UserDefaults(suiteName: appGroupIdentifier) else {
            print("❌ Failed to access App Group UserDefaults")
            return nil
        }

        guard let savedData = sharedDefaults.data(forKey: sharedDataKey) else {
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
            print("❌ Failed to access App Group UserDefaults")
            return nil
        }

        guard let savedData = sharedDefaults.data(forKey: sharedDataKey) else {
            return nil
        }

        print("✓ Found pending YouTube import data")

        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601

        do {
            let youtubeData = try decoder.decode(YouTubeDataFromExtension.self, from: savedData)

            // Convert to ImportedYouTubeData
            guard let videoType = youtubeData.videoType else {
                print("❌ No video type set in YouTube data")
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

            // Don't clear the data yet - clear after successful import
            print("✅ Retrieved YouTube data: \(result.title)")
            return result

        } catch {
            print("❌ Failed to decode YouTube data: \(error)")
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
        print("🗑️ Cleared pending YouTube import data")
    }
}

// MARK: - Private Decoding Model

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

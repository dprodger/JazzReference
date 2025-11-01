//
//  SharedDataManagers.swift
//  JazzReference
//
//  Created by Dave Rodger on 11/1/25.
//

import UIKit


// MARK: - Shared Data Manager

class SharedArtistData {
    static func saveSharedData(_ artistData: ArtistData, appGroup: String) {
        guard let sharedDefaults = UserDefaults(suiteName: appGroup) else {
            print("❌ Failed to get shared UserDefaults")
            return
        }
        
        let encoder = JSONEncoder()
        if let encoded = try? encoder.encode(artistData) {
            sharedDefaults.set(encoded, forKey: "pendingArtistImport")
            sharedDefaults.synchronize()
            print("✅ Artist data saved to shared container")
        } else {
            print("❌ Failed to encode artist data")
        }
    }
}

class SharedSongData {
    static func saveSharedData(_ songData: SongData, appGroup: String) {
        guard let sharedDefaults = UserDefaults(suiteName: appGroup) else {
            print("❌ Failed to get shared UserDefaults")
            return
        }
        
        let encoder = JSONEncoder()
        if let encoded = try? encoder.encode(songData) {
            sharedDefaults.set(encoded, forKey: "pendingSongImport")
            sharedDefaults.removeObject(forKey: "pendingArtistImport") // Clear any pending artist import
            sharedDefaults.synchronize()
            print("✅ Song data saved to shared container")
        } else {
            print("❌ Failed to encode song data")
        }
    }
}


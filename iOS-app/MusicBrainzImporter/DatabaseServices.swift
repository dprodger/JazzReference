//
//  DatabaseServices.swift
//  JazzReference
//
//  Created by Dave Rodger on 11/1/25.
//

import Foundation

// MARK: - Database Service

class ArtistDatabaseService {
    static let shared = ArtistDatabaseService()

    // For development, you might use: http://localhost:5001
    // For production, use your deployed backend URL
    private let baseURL = "https://api.approachnote.com"

    private init() {}
    
    /// Check if an artist exists in the database by name and/or MusicBrainz ID
    func checkArtistExists(name: String, musicbrainzId: String) async throws -> ArtistMatchResult {
        // Search by name first
        guard let encodedName = name.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) else {
            throw URLError(.badURL)
        }
        
        let urlString = "\(baseURL)/performers/search?name=\(encodedName)"
        guard let url = URL(string: urlString) else {
            throw URLError(.badURL)
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.timeoutInterval = 10.0
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw URLError(.badServerResponse)
        }
        
        if httpResponse.statusCode == 404 {
            // No artist found with this name
            return .notFound
        }
        
        guard httpResponse.statusCode == 200 else {
            throw URLError(.badServerResponse)
        }
        
        // Parse the response
        let decoder = JSONDecoder()
        let results = try decoder.decode([ExistingArtist].self, from: data)
        
        // Check for exact name match (case-insensitive)
        guard let matchingArtist = results.first(where: { $0.name.lowercased() == name.lowercased() }) else {
            return .notFound
        }
        
        // Now check the MusicBrainz ID
        if let existingMbid = matchingArtist.musicbrainzId {
            if existingMbid == musicbrainzId {
                // Exact match: same name and same MusicBrainz ID
                return .exactMatch(existingArtist: matchingArtist)
            } else {
                // Different MusicBrainz ID
                return .nameMatchDifferentMbid(existingArtist: matchingArtist)
            }
        } else {
            // Name matches but no MusicBrainz ID in database
            return .nameMatchNoMbid(existingArtist: matchingArtist)
        }
    }
}

class SongDatabaseService {
    static let shared = SongDatabaseService()

    private let baseURL = "https://api.approachnote.com"

    private init() {}
    
    /// Check if a song exists in the database by title and/or MusicBrainz ID
    func checkSongExists(title: String, musicbrainzId: String) async throws -> SongMatchResult {
        // Search by title first
        guard let encodedTitle = title.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) else {
            throw URLError(.badURL)
        }
        
        let urlString = "\(baseURL)/songs?search=\(encodedTitle)"
        guard let url = URL(string: urlString) else {
            throw URLError(.badURL)
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.timeoutInterval = 10.0
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw URLError(.badServerResponse)
        }
        
        if httpResponse.statusCode == 404 {
            return .notFound
        }
        
        guard httpResponse.statusCode == 200 else {
            throw URLError(.badServerResponse)
        }
        
        // Parse the response
        let decoder = JSONDecoder()
        let results = try decoder.decode([ExistingSong].self, from: data)
        
        // Check for exact title match (case-insensitive)
        guard let matchingSong = results.first(where: { $0.title.lowercased() == title.lowercased() }) else {
            return .notFound
        }
        
        // Check the MusicBrainz ID
        if let existingMbid = matchingSong.musicbrainzId {
            if existingMbid == musicbrainzId {
                return .exactMatch(existingSong: matchingSong)
            } else {
                return .titleMatchDifferentMbid(existingSong: matchingSong)
            }
        } else {
            return .titleMatchNoMbid(existingSong: matchingSong)
        }
    }
}

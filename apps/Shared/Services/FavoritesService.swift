import Foundation
import os

// MARK: - Favorites Response Types

/// Response from /favorites endpoint (user's favorited recordings)
struct FavoriteRecordingResponse: Codable {
    let id: String
    let songTitle: String?
    let albumTitle: String?
    let recordingYear: Int?
    let bestAlbumArtSmall: String?
    let favoritedAt: String?

    enum CodingKeys: String, CodingKey {
        case id
        case songTitle = "song_title"
        case albumTitle = "album_title"
        case recordingYear = "recording_year"
        case bestAlbumArtSmall = "best_album_art_small"
        case favoritedAt = "favorited_at"
    }
}

/// Response from POST/DELETE /recordings/{id}/favorite
struct FavoriteToggleResponse: Codable {
    let message: String
    let favoriteCount: Int

    enum CodingKeys: String, CodingKey {
        case message
        case favoriteCount = "favorite_count"
    }
}

// MARK: - Favorites Service

@MainActor
class FavoritesService {

    /// Fetch the current user's favorited recordings
    func fetchUserFavorites(authToken: String) async -> [FavoriteRecordingResponse] {
        let startTime = Date()
        let url = URL.api(path: "/favorites")

        var request = URLRequest(url: url)
        request.setValue("Bearer \(authToken)", forHTTPHeaderField: "Authorization")

        do {
            let (data, response) = try await URLSession.shared.data(for: request)

            if let httpResponse = response as? HTTPURLResponse {
                if httpResponse.statusCode == 401 {
                    Log.network.error("Unauthorized - user needs to re-authenticate")
                    return []
                }
                guard (200...299).contains(httpResponse.statusCode) else {
                    Log.network.error("HTTP error fetching favorites: \(httpResponse.statusCode, privacy: .public)")
                    return []
                }
            }

            let favorites = try JSONDecoder().decode([FavoriteRecordingResponse].self, from: data)
            APIClient.logRequest("GET /favorites", startTime: startTime)

            if APIClient.diagnosticsEnabled {
                Log.network.debug("Returned \(favorites.count, privacy: .public) favorites")
            }
            return favorites
        } catch {
            Log.network.error("Error fetching favorites: \(error)")
            return []
        }
    }

    /// Add a recording to the user's favorites
    func addFavorite(recordingId: String, authToken: String) async -> Int? {
        let startTime = Date()
        let url = URL.api(path: "/recordings/\(recordingId)/favorite")

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(authToken)", forHTTPHeaderField: "Authorization")

        do {
            let (data, response) = try await URLSession.shared.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                return nil
            }

            APIClient.logRequest("POST /recordings/\(recordingId)/favorite", startTime: startTime)

            if httpResponse.statusCode == 201 {
                let toggleResponse = try JSONDecoder().decode(FavoriteToggleResponse.self, from: data)
                if APIClient.diagnosticsEnabled {
                    let count = toggleResponse.favoriteCount
                    Log.network.debug("\(toggleResponse.message), count: \(count, privacy: .public)")
                }
                return toggleResponse.favoriteCount
            } else if httpResponse.statusCode == 409 {
                Log.network.warning("Recording already favorited")
                return nil
            } else if httpResponse.statusCode == 401 {
                Log.network.error("Unauthorized")
                return nil
            } else {
                Log.network.error("Error adding favorite: HTTP \(httpResponse.statusCode, privacy: .public)")
                return nil
            }
        } catch {
            Log.network.error("Error adding favorite: \(error)")
            return nil
        }
    }

    /// Remove a recording from the user's favorites
    func removeFavorite(recordingId: String, authToken: String) async -> Int? {
        let startTime = Date()
        let url = URL.api(path: "/recordings/\(recordingId)/favorite")

        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"
        request.setValue("Bearer \(authToken)", forHTTPHeaderField: "Authorization")

        do {
            let (data, response) = try await URLSession.shared.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                return nil
            }

            APIClient.logRequest("DELETE /recordings/\(recordingId)/favorite", startTime: startTime)

            if httpResponse.statusCode == 200 {
                let toggleResponse = try JSONDecoder().decode(FavoriteToggleResponse.self, from: data)
                if APIClient.diagnosticsEnabled {
                    let count = toggleResponse.favoriteCount
                    Log.network.debug("\(toggleResponse.message), count: \(count, privacy: .public)")
                }
                return toggleResponse.favoriteCount
            } else if httpResponse.statusCode == 404 {
                Log.network.warning("Recording not in favorites")
                return nil
            } else if httpResponse.statusCode == 401 {
                Log.network.error("Unauthorized")
                return nil
            } else {
                Log.network.error("Error removing favorite: HTTP \(httpResponse.statusCode, privacy: .public)")
                return nil
            }
        } catch {
            Log.network.error("Error removing favorite: \(error)")
            return nil
        }
    }
}

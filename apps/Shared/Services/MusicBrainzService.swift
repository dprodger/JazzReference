import Foundation
import Combine
import os

// MARK: - MusicBrainz Service

@MainActor
class MusicBrainzService: ObservableObject {

    /// Search MusicBrainz for works (songs) by title
    func searchMusicBrainzWorks(query: String) async -> [MusicBrainzWork] {
        let startTime = Date()

        let encodedQuery = query.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? query
        let url = URL.api(path: "/musicbrainz/works/search?q=\(encodedQuery)")

        do {
            let (data, response) = try await URLSession.shared.data(from: url)

            guard let httpResponse = response as? HTTPURLResponse else {
                return []
            }

            APIClient.logRequest("GET /musicbrainz/works/search", startTime: startTime)

            if httpResponse.statusCode == 200 {
                let searchResponse = try JSONDecoder().decode(MusicBrainzSearchResponse.self, from: data)
                if APIClient.diagnosticsEnabled {
                    Log.network.debug("Found \(searchResponse.results.count, privacy: .public) MusicBrainz works")
                }
                return searchResponse.results
            } else {
                Log.network.error("Error searching MusicBrainz: HTTP \(httpResponse.statusCode, privacy: .public)")
                return []
            }
        } catch {
            Log.network.error("Error searching MusicBrainz: \(error)")
            return []
        }
    }

    /// Import a song from MusicBrainz into the database
    func importSongFromMusicBrainz(work: MusicBrainzWork, authToken: String) async -> MusicBrainzImportResponse? {
        let startTime = Date()

        let url = URL.api(path: "/musicbrainz/import")

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(authToken)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        var body: [String: Any] = [
            "musicbrainz_id": work.id,
            "title": work.title
        ]
        if let composers = work.composers, !composers.isEmpty {
            body["composer"] = composers.joined(separator: ", ")
        }

        do {
            request.httpBody = try JSONSerialization.data(withJSONObject: body)

            let (data, response) = try await URLSession.shared.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                return nil
            }

            APIClient.logRequest("POST /musicbrainz/import", startTime: startTime)

            if httpResponse.statusCode == 201 {
                let importResponse = try JSONDecoder().decode(MusicBrainzImportResponse.self, from: data)
                if APIClient.diagnosticsEnabled {
                    let songTitle = importResponse.song?.title ?? "unknown"
                    Log.network.info("Imported song: \(songTitle, privacy: .private)")
                }
                return importResponse
            } else if httpResponse.statusCode == 409 {
                Log.network.warning("Song with this MusicBrainz ID already exists")
                if let errorResponse = try? JSONDecoder().decode(MusicBrainzImportResponse.self, from: data) {
                    return errorResponse
                }
                return nil
            } else {
                Log.network.error("Error importing from MusicBrainz: HTTP \(httpResponse.statusCode, privacy: .public)")
                return nil
            }
        } catch {
            Log.network.error("Error importing from MusicBrainz: \(error)")
            return nil
        }
    }
}

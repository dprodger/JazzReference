import Foundation

// MARK: - Queue Status Models

struct CurrentSong: Codable {
    let songId: String
    let songName: String

    enum CodingKeys: String, CodingKey {
        case songId = "song_id"
        case songName = "song_name"
    }
}

struct ResearchProgress: Codable {
    let phase: String
    let current: Int
    let total: Int

    /// Human-readable description of the current phase
    var phaseDescription: String {
        switch phase {
        case "musicbrainz_recording_import":
            return "Importing MusicBrainz recordings"
        case "spotify_track_match":
            return "Matching Spotify tracks"
        default:
            return phase.replacingOccurrences(of: "_", with: " ").capitalized
        }
    }

    /// Short label for the phase
    var phaseLabel: String {
        switch phase {
        case "musicbrainz_recording_import":
            return "MusicBrainz"
        case "spotify_track_match":
            return "Spotify"
        default:
            return phase
        }
    }

    /// Progress as a fraction (0.0 to 1.0)
    var progressFraction: Double {
        guard total > 0 else { return 0 }
        return Double(current) / Double(total)
    }
}

struct QueueStatus: Codable {
    let queueSize: Int
    let workerActive: Bool
    let currentSong: CurrentSong?
    let progress: ResearchProgress?

    enum CodingKeys: String, CodingKey {
        case queueSize = "queue_size"
        case workerActive = "worker_active"
        case currentSong = "current_song"
        case progress
    }
}

/// Represents a song waiting in the research queue
struct QueuedSong: Codable, Identifiable {
    let songId: String
    let songName: String

    var id: String { songId }

    enum CodingKeys: String, CodingKey {
        case songId = "song_id"
        case songName = "song_name"
    }
}

/// Response wrapper for /research/queue/items endpoint
private struct QueuedSongsResponse: Codable {
    let queuedSongs: [QueuedSong]

    enum CodingKeys: String, CodingKey {
        case queuedSongs = "queued_songs"
    }
}

/// Research status for a specific song
enum SongResearchStatus {
    case notInQueue
    case inQueue(position: Int)
    case currentlyResearching(progress: ResearchProgress?)
}

// MARK: - Research Service

@MainActor
class ResearchService {

    /// Queue a song for background research to update its data from external sources
    func refreshSongData(songId: String, forceRefresh: Bool = true) async -> Bool {
        let forceRefreshParam = forceRefresh ? "true" : "false"
        let url = URL.api(path: "/songs/\(songId)/refresh?force_refresh=\(forceRefreshParam)")

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        do {
            let (data, response) = try await URLSession.shared.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                print("Error: Invalid response")
                return false
            }

            if httpResponse.statusCode == 202 {
                if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                    let refreshType = forceRefresh ? "deep" : "quick"
                    if let queueSize = json["queue_size"] as? Int {
                        print("\u{2713} Song queued for \(refreshType) refresh (queue size: \(queueSize))")
                    }
                }
                return true
            } else {
                print("Error: Unexpected status code \(httpResponse.statusCode)")
                if let responseString = String(data: data, encoding: .utf8) {
                    print("Response: \(responseString)")
                }
                return false
            }
        } catch {
            print("Error refreshing song data: \(error.localizedDescription)")
            return false
        }
    }

    /// Fetch the current research queue status
    func fetchQueueStatus() async -> QueueStatus? {
        let startTime = Date()
        let url = URL.api(path: "/research/queue")

        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            let queueStatus = try JSONDecoder().decode(QueueStatus.self, from: data)

            APIClient.logRequest("GET /research/queue", startTime: startTime)

            if APIClient.diagnosticsEnabled {
                if let currentSong = queueStatus.currentSong {
                    print("   \u{21B3} Queue: \(queueStatus.queueSize), Processing: \(currentSong.songName)")
                } else {
                    print("   \u{21B3} Queue: \(queueStatus.queueSize)")
                }
            }

            return queueStatus
        } catch {
            print("Error fetching queue status: \(error.localizedDescription)")
            return nil
        }
    }

    /// Fetch the list of songs currently in the research queue
    func fetchQueuedSongs() async -> [QueuedSong] {
        let startTime = Date()
        let url = URL.api(path: "/research/queue/items")

        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            let response = try JSONDecoder().decode(QueuedSongsResponse.self, from: data)

            APIClient.logRequest("GET /research/queue/items", startTime: startTime)

            if APIClient.diagnosticsEnabled {
                print("   \u{21B3} Queued songs: \(response.queuedSongs.count)")
            }

            return response.queuedSongs
        } catch {
            print("Error fetching queued songs: \(error.localizedDescription)")
            return []
        }
    }

    /// Check the research status for a specific song
    func checkSongResearchStatus(songId: String) async -> SongResearchStatus {
        async let queueStatusTask = fetchQueueStatus()
        async let queuedSongsTask = fetchQueuedSongs()

        let (queueStatus, queuedSongs) = await (queueStatusTask, queuedSongsTask)

        if let current = queueStatus?.currentSong, current.songId == songId {
            return .currentlyResearching(progress: queueStatus?.progress)
        }

        if let position = queuedSongs.firstIndex(where: { $0.songId == songId }) {
            return .inQueue(position: position + 1)
        }

        return .notInQueue
    }
}

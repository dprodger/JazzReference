import Foundation

// MARK: - Contribution Response Types

/// Response from contribution endpoints
struct ContributionResponse: Codable {
    let consensus: CommunityConsensus
    let counts: ContributionCounts
    let userContribution: UserContribution?
    let message: String?

    enum CodingKeys: String, CodingKey {
        case consensus, counts, message
        case userContribution = "user_contribution"
    }
}

/// Response from user contribution stats endpoint
struct UserContributionStats: Codable {
    let transcriptions: Int
    let backingTracks: Int
    let tempoMarkings: Int
    let instrumentalVocal: Int
    let keys: Int

    enum CodingKeys: String, CodingKey {
        case transcriptions
        case backingTracks = "backing_tracks"
        case tempoMarkings = "tempo_markings"
        case instrumentalVocal = "instrumental_vocal"
        case keys
    }

    /// Total number of contributions across all categories
    var totalContributions: Int {
        transcriptions + backingTracks + tempoMarkings + instrumentalVocal + keys
    }
}

// MARK: - Contribution Service

@MainActor
class ContributionService {

    /// Save user's contribution for a recording (creates or updates)
    func saveRecordingContribution(
        recordingId: String,
        key: String?,
        tempo: Int?,
        isInstrumental: Bool?,
        authToken: String
    ) async -> ContributionResponse? {
        let startTime = Date()
        let url = URL.api(path: "/recordings/\(recordingId)/contribution")

        var request = URLRequest(url: url)
        request.httpMethod = "PUT"
        request.setValue("Bearer \(authToken)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        var body: [String: Any] = [:]
        if let key = key { body["performance_key"] = key }
        if let tempo = tempo { body["tempo_bpm"] = tempo }
        if let isInstrumental = isInstrumental { body["is_instrumental"] = isInstrumental }

        do {
            request.httpBody = try JSONSerialization.data(withJSONObject: body)
            let (data, response) = try await URLSession.shared.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                return nil
            }

            APIClient.logRequest("PUT /recordings/\(recordingId)/contribution", startTime: startTime)

            if (200...299).contains(httpResponse.statusCode) {
                let contributionResponse = try JSONDecoder().decode(ContributionResponse.self, from: data)
                if APIClient.diagnosticsEnabled {
                    print("   \u{21B3} Saved contribution, key_count: \(contributionResponse.counts.key)")
                }
                return contributionResponse
            } else if httpResponse.statusCode == 401 {
                print("Error: Unauthorized")
                return nil
            } else if httpResponse.statusCode == 400 {
                if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   let error = json["error"] as? String {
                    print("Validation error: \(error)")
                }
                return nil
            } else {
                print("Error saving contribution: HTTP \(httpResponse.statusCode)")
                return nil
            }
        } catch {
            print("Error saving contribution: \(error)")
            return nil
        }
    }

    /// Delete user's entire contribution for a recording
    func deleteRecordingContribution(
        recordingId: String,
        authToken: String
    ) async -> ContributionResponse? {
        let startTime = Date()
        let url = URL.api(path: "/recordings/\(recordingId)/contribution")

        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"
        request.setValue("Bearer \(authToken)", forHTTPHeaderField: "Authorization")

        do {
            let (data, response) = try await URLSession.shared.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                return nil
            }

            APIClient.logRequest("DELETE /recordings/\(recordingId)/contribution", startTime: startTime)

            if (200...299).contains(httpResponse.statusCode) {
                let contributionResponse = try JSONDecoder().decode(ContributionResponse.self, from: data)
                if APIClient.diagnosticsEnabled {
                    print("   \u{21B3} Deleted contribution")
                }
                return contributionResponse
            } else if httpResponse.statusCode == 404 {
                print("No contribution found to delete")
                return nil
            } else if httpResponse.statusCode == 401 {
                print("Error: Unauthorized")
                return nil
            } else {
                print("Error deleting contribution: HTTP \(httpResponse.statusCode)")
                return nil
            }
        } catch {
            print("Error deleting contribution: \(error)")
            return nil
        }
    }

    /// Fetch contribution statistics for the current authenticated user
    func fetchUserContributionStats(authToken: String) async -> UserContributionStats? {
        let startTime = Date()
        let url = URL.api(path: "/users/me/contribution-stats")

        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("Bearer \(authToken)", forHTTPHeaderField: "Authorization")

        do {
            let (data, response) = try await URLSession.shared.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                return nil
            }

            APIClient.logRequest("GET /users/me/contribution-stats", startTime: startTime)

            if httpResponse.statusCode == 200 {
                let stats = try JSONDecoder().decode(UserContributionStats.self, from: data)
                if APIClient.diagnosticsEnabled {
                    print("   \u{21B3} Total contributions: \(stats.totalContributions)")
                }
                return stats
            } else if httpResponse.statusCode == 401 {
                print("Error: Unauthorized")
                return nil
            } else {
                print("Error fetching contribution stats: HTTP \(httpResponse.statusCode)")
                return nil
            }
        } catch {
            print("Error fetching contribution stats: \(error)")
            return nil
        }
    }
}

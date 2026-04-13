import SwiftUI
import Combine

// MARK: - Recording Service

@MainActor
class RecordingService: ObservableObject {
    @Published var recordings: [Recording] = []
    @Published var recordingsCount: Int = 0
    @Published var isLoading = false
    @Published var errorMessage: String?

    // MARK: - Recording List

    func fetchRecordings(searchQuery: String = "") async {
        let startTime = Date()

        if searchQuery.isEmpty {
            self.recordings = []
            self.isLoading = false
            return
        }

        isLoading = true
        errorMessage = nil

        let normalizedQuery = APIClient.normalizeSearchText(searchQuery)
        let url = URL.api(path: "/recordings?search=\(normalizedQuery.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? "")")

        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            let decodedRecordings = try JSONDecoder().decode([Recording].self, from: data)

            guard !Task.isCancelled else { return }

            self.recordings = decodedRecordings
            self.isLoading = false
            APIClient.logRequest("GET /recordings?search=...", startTime: startTime)

            if APIClient.diagnosticsEnabled {
                print("   \u{21B3} Returned \(decodedRecordings.count) recordings")
            }
        } catch is CancellationError {
            return
        } catch let error as NSError where error.code == NSURLErrorCancelled {
            return
        } catch {
            guard !Task.isCancelled else { return }
            self.errorMessage = "Failed to fetch recordings: \(error.localizedDescription)"
            self.isLoading = false
        }
    }

    // MARK: - Recordings Count

    func fetchRecordingsCount() async {
        let url = URL.api(path: "/recordings/count")

        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            if let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
               let count = json["count"] as? Int {
                self.recordingsCount = count
            }
        } catch {
            // Silently fail - count is just for display
        }
    }

    // MARK: - Recording Detail

    func fetchRecordingDetail(id: String) async -> Recording? {
        let startTime = Date()
        let url = URL.api(path: "/recordings/\(id)")

        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            let recording = try JSONDecoder().decode(Recording.self, from: data)
            APIClient.logRequest("GET /recordings/\(id)", startTime: startTime)

            if APIClient.diagnosticsEnabled {
                print("   \u{21B3} Returned recording with \(recording.performers?.count ?? 0) performers")
            }
            return recording
        } catch let error as NSError where error.code == NSURLErrorCancelled {
            return nil
        } catch {
            print("Error fetching recording detail: \(error)")
            return nil
        }
    }

    // MARK: - Recording Transcriptions

    func fetchRecordingTranscriptions(recordingId: String) async -> [SoloTranscription] {
        #if DEBUG
        if APIClient.isPreviewMode {
            return [.preview1]
        }
        #endif

        let url = URL.api(path: "/recordings/\(recordingId)/transcriptions")

        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            return try JSONDecoder().decode([SoloTranscription].self, from: data)
        } catch {
            print("Error fetching recording transcriptions: \(error)")
            return []
        }
    }

    #if DEBUG
    func fetchRecordingTranscriptionsSync(recordingId: String) -> [SoloTranscription] {
        if APIClient.isPreviewMode {
            return [.preview1]
        }
        return []
    }

    func fetchRecordingDetailSync(id: String) -> Recording? {
        if APIClient.isPreviewMode {
            switch id {
            case "preview-recording-1":
                return Recording.preview1
            case "preview-recording-2":
                return Recording.preview2
            case "preview-recording-3":
                return Recording.previewMinimal
            default:
                return Recording.preview1
            }
        }
        return nil
    }
    #endif
}

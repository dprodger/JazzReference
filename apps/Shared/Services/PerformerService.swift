import SwiftUI
import Combine
import os

// MARK: - Performer Service

@MainActor
class PerformerService: ObservableObject {
    @Published var performers: [Performer] = []
    @Published var performersIndex: [Performer] = []
    @Published var isLoading = false
    @Published var errorMessage: String?
    @Published var hasMorePerformers = true
    @Published var isLoadingMorePerformers = false

    private var performersTotalCount = 0
    private var currentPerformersOffset = 0
    private let performersPageSize = 500

    // MARK: - Performer Index

    func fetchPerformersIndex(searchQuery: String = "") async {
        let startTime = Date()
        isLoading = true
        errorMessage = nil

        var path = "/performers/index"
        if !searchQuery.isEmpty {
            let normalizedQuery = APIClient.normalizeSearchText(searchQuery)
            path += "?search=\(normalizedQuery.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? "")"
        }

        let url = URL.api(path: path)

        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            let decodedPerformers = try JSONDecoder().decode([Performer].self, from: data)

            guard !Task.isCancelled else { return }

            self.performersIndex = decodedPerformers
            self.isLoading = false
            APIClient.logRequest("GET /performers/index\(searchQuery.isEmpty ? "" : "?search=...")", startTime: startTime)
        } catch is CancellationError {
            return
        } catch let error as NSError where error.code == NSURLErrorCancelled {
            return
        } catch {
            guard !Task.isCancelled else { return }
            self.errorMessage = "Failed to fetch performers: \(error.localizedDescription)"
            self.isLoading = false
        }
    }

    // MARK: - Performer List with Pagination

    func fetchPerformers(searchQuery: String = "") async {
        let startTime = Date()
        isLoading = true
        errorMessage = nil
        currentPerformersOffset = 0
        hasMorePerformers = true
        performers = []

        var path = "/performers?limit=\(performersPageSize)&offset=0"
        if !searchQuery.isEmpty {
            let normalizedQuery = APIClient.normalizeSearchText(searchQuery)
            path += "&search=\(normalizedQuery.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? "")"
        }

        let url = URL.api(path: path)

        do {
            let (data, response) = try await URLSession.shared.data(from: url)
            let decodedPerformers = try JSONDecoder().decode([Performer].self, from: data)

            var totalCount = decodedPerformers.count
            var hasMore = false
            if let httpResponse = response as? HTTPURLResponse {
                if let totalCountHeader = httpResponse.value(forHTTPHeaderField: "X-Total-Count"),
                   let count = Int(totalCountHeader) {
                    totalCount = count
                }
                if let hasMoreHeader = httpResponse.value(forHTTPHeaderField: "X-Has-More") {
                    hasMore = hasMoreHeader == "true"
                }
            }

            guard !Task.isCancelled else { return }

            self.performers = decodedPerformers
            self.performersTotalCount = totalCount
            self.hasMorePerformers = hasMore
            self.currentPerformersOffset = decodedPerformers.count
            self.isLoading = false
            APIClient.logRequest("GET /performers?limit=\(performersPageSize)&offset=0\(searchQuery.isEmpty ? "" : "&search=...")", startTime: startTime)
        } catch is CancellationError {
            return
        } catch let error as NSError where error.code == NSURLErrorCancelled {
            return
        } catch {
            guard !Task.isCancelled else { return }
            self.errorMessage = "Failed to fetch performers: \(error.localizedDescription)"
            self.isLoading = false
        }
    }

    func loadMorePerformers(searchQuery: String = "") async {
        guard !isLoadingMorePerformers && hasMorePerformers else { return }

        let startTime = Date()
        isLoadingMorePerformers = true

        var path = "/performers?limit=\(performersPageSize)&offset=\(currentPerformersOffset)"
        if !searchQuery.isEmpty {
            let normalizedQuery = APIClient.normalizeSearchText(searchQuery)
            path += "&search=\(normalizedQuery.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? "")"
        }

        let url = URL.api(path: path)

        do {
            let (data, response) = try await URLSession.shared.data(from: url)
            let decodedPerformers = try JSONDecoder().decode([Performer].self, from: data)

            var hasMore = false
            if let httpResponse = response as? HTTPURLResponse {
                if let hasMoreHeader = httpResponse.value(forHTTPHeaderField: "X-Has-More") {
                    hasMore = hasMoreHeader == "true"
                }
            }

            guard !Task.isCancelled else { return }

            self.performers.append(contentsOf: decodedPerformers)
            self.hasMorePerformers = hasMore
            self.currentPerformersOffset += decodedPerformers.count
            self.isLoadingMorePerformers = false
            APIClient.logRequest("GET /performers?limit=\(performersPageSize)&offset=\(currentPerformersOffset - decodedPerformers.count)\(searchQuery.isEmpty ? "" : "&search=...")", startTime: startTime)
        } catch is CancellationError {
            return
        } catch let error as NSError where error.code == NSURLErrorCancelled {
            return
        } catch {
            guard !Task.isCancelled else { return }
            self.isLoadingMorePerformers = false
            Log.network.error("Error loading more performers: \(error)")
        }
    }

    // MARK: - Performer Detail

    func fetchPerformerDetail(id: String) async -> PerformerDetail? {
        return await fetchPerformerDetail(id: id, sortBy: .year)
    }

    func fetchPerformerDetail(id: String, sortBy: PerformerRecordingSortOrder) async -> PerformerDetail? {
        let startTime = Date()
        let url = URL.api(path: "/performers/\(id)?sort=\(sortBy.rawValue)")

        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            let performer = try JSONDecoder().decode(PerformerDetail.self, from: data)
            APIClient.logRequest("GET /performers/\(id)?sort=\(sortBy.rawValue)", startTime: startTime)

            if APIClient.diagnosticsEnabled {
                let recordingCount = performer.recordings?.count ?? 0
                Log.network.debug("Returned performer with \(recordingCount, privacy: .public) recordings")
            }
            return performer
        } catch let error as NSError where error.code == NSURLErrorCancelled {
            return nil
        } catch {
            Log.network.error("Error fetching performer detail: \(error)")
            return nil
        }
    }

    // MARK: - Two-Phase Performer Loading

    func fetchPerformerSummary(id: String) async -> PerformerDetail? {
        let startTime = Date()
        let url = URL.api(path: "/performers/\(id)/summary")

        do {
            let (data, response) = try await URLSession.shared.data(from: url)

            if let httpResponse = response as? HTTPURLResponse {
                guard (200...299).contains(httpResponse.statusCode) else {
                    Log.network.error("HTTP error fetching performer summary: \(httpResponse.statusCode, privacy: .public)")
                    return nil
                }
            }

            let performer = try JSONDecoder().decode(PerformerDetail.self, from: data)
            APIClient.logRequest("GET /performers/\(id)/summary", startTime: startTime)

            if APIClient.diagnosticsEnabled {
                let totalRecordings = performer.recordingCount ?? 0
                Log.network.debug("Summary: \(totalRecordings, privacy: .public) total recordings")
            }
            return performer
        } catch {
            Log.network.error("Error fetching performer summary: \(error)")
            if let decodingError = error as? DecodingError {
                Log.network.error("Decoding error details: \(decodingError)")
            }
            return nil
        }
    }

    func fetchPerformerRecordings(id: String, sortBy: PerformerRecordingSortOrder = .year) async -> [PerformerRecording]? {
        let startTime = Date()
        let url = URL.api(path: "/performers/\(id)/recordings?sort=\(sortBy.rawValue)")

        do {
            let (data, response) = try await URLSession.shared.data(from: url)

            if let httpResponse = response as? HTTPURLResponse {
                guard (200...299).contains(httpResponse.statusCode) else {
                    Log.network.error("HTTP error fetching performer recordings: \(httpResponse.statusCode, privacy: .public)")
                    return nil
                }
            }

            let recordingsResponse = try JSONDecoder().decode(PerformerRecordingsResponse.self, from: data)
            APIClient.logRequest("GET /performers/\(id)/recordings", startTime: startTime)

            if APIClient.diagnosticsEnabled {
                let count = recordingsResponse.recordingCount
                Log.network.debug("Loaded \(count, privacy: .public) recordings")
            }
            return recordingsResponse.recordings
        } catch {
            Log.network.error("Error fetching performer recordings: \(error)")
            if let decodingError = error as? DecodingError {
                Log.network.error("Decoding error details: \(decodingError)")
            }
            return nil
        }
    }

    // MARK: - Preview Support

    #if DEBUG
    func fetchPerformerDetailSync(id: String) -> PerformerDetail? {
        if APIClient.isPreviewMode {
            switch id {
            case "preview-performer-detail-1":
                return PerformerDetail.preview
            case "preview-performer-detail-2":
                return PerformerDetail.previewMinimal
            default:
                return PerformerDetail.preview
            }
        }
        return nil
    }
    #endif
}

// MARK: - Performer Recording Sort Order Enum
enum PerformerRecordingSortOrder: String, CaseIterable, Identifiable {
    case year = "year"
    case name = "name"

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .year: return "Year"
        case .name: return "Song"
        }
    }
}

// MARK: - Network Manager (deprecated — use domain-specific services instead)
//
// This class is retained only for backward compatibility with PreviewHelpers.
// All API methods have been extracted to per-domain services under Shared/Services/:
//   - SongService, PerformerService, RecordingService
//   - ResearchService, FavoritesService, ContributionService
//   - MusicBrainzService, ContentService
//   - APIClient (shared infrastructure)

import SwiftUI
import Combine

class NetworkManager: ObservableObject {
    static let baseURL = APIClient.baseURL

    // MARK: - Diagnostics (delegated to APIClient)

    static func resetRequestCounter() {
        APIClient.resetRequestCounter()
    }

    static func printRequestSummary() {
        APIClient.printRequestSummary()
    }
}

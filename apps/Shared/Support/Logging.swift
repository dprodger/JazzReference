import Foundation
import os

/// Structured logging categories for the Approach Note app.
///
/// Usage:
///   Log.network.debug("Fetching songs")
///   Log.auth.info("User logged in")
///   Log.auth.error("Token refresh failed: \(error.localizedDescription)")
///
/// Privacy:
///   Log.auth.debug("Login for \(email, privacy: .private)")
///   Log.network.debug("GET \(endpoint, privacy: .public)")
enum Log {
    private static let subsystem = Bundle.main.bundleIdentifier ?? "com.approachnote"

    /// API calls, HTTP responses, request timing
    static let network  = Logger(subsystem: subsystem, category: "network")
    /// Authentication, token refresh, keychain
    static let auth     = Logger(subsystem: subsystem, category: "auth")
    /// View state, navigation, user interactions
    static let ui       = Logger(subsystem: subsystem, category: "ui")
    /// Data import, persistence, repertoires, favorites
    static let data     = Logger(subsystem: subsystem, category: "data")
    /// Research queue, background enrichment
    static let research = Logger(subsystem: subsystem, category: "research")
}

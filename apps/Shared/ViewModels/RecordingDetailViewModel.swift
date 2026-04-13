//
//  RecordingDetailViewModel.swift
//  JazzReference
//
//  Shared view model for RecordingDetailView (iOS) and RecordingDetailView (Mac).
//  Owns the data-loading, release-auto-selection, and favorite-toggle logic
//  that was previously duplicated byte-for-byte across both platforms.
//
//  Usage pattern:
//    @StateObject private var viewModel = RecordingDetailViewModel()
//    ...
//    .task(id: recordingId) {
//        viewModel.configure(
//            recordingId: recordingId,
//            authManager: authManager,
//            favoritesManager: favoritesManager
//        )
//        await viewModel.load()
//    }
//

import SwiftUI
import Combine

@MainActor
final class RecordingDetailViewModel: ObservableObject {
    // MARK: - Published state

    @Published var recording: Recording?
    @Published var isLoading = true
    @Published var selectedReleaseId: String?
    @Published var showingLoginAlert = false
    @Published var localFavoriteCount: Int?

    // MARK: - Injected dependencies (weak — owned by the environment)

    private var recordingId: String = ""
    private weak var authManager: AuthenticationManager?
    private weak var favoritesManager: FavoritesManager?

    /// Used only for the SwiftUI preview stub loader. Production paths go
    /// directly through `authManager.makeAuthenticatedRequest` / `URLSession`.
    private let networkManager = NetworkManager()

    // MARK: - Configuration

    /// Call from the view's `.task` (or `.task(id:)`) to inject dependencies.
    /// Safe to call repeatedly; subsequent calls update the stored references.
    func configure(
        recordingId: String,
        authManager: AuthenticationManager,
        favoritesManager: FavoritesManager
    ) {
        self.recordingId = recordingId
        self.authManager = authManager
        self.favoritesManager = favoritesManager
    }

    // MARK: - Data loading

    /// Initial load: sets isLoading, fetches, auto-selects a release, clears isLoading.
    func load() async {
        isLoading = true
        recording = await fetchRecordingWithAuth()
        autoSelectFirstRelease()
        isLoading = false
    }

    /// Pull-to-refresh: does NOT set `isLoading`, preserves existing data on failure.
    func refresh() async {
        if let fetched = await fetchRecordingWithAuth() {
            recording = fetched
            autoSelectFirstRelease()
        }
    }

    /// SwiftUI preview loader. Synchronously pulls stub data from NetworkManager's
    /// preview helper. Only call this from inside an `XCODE_RUNNING_FOR_PREVIEWS` guard.
    func loadPreview() {
        recording = networkManager.fetchRecordingDetailSync(id: recordingId)
        autoSelectFirstRelease()
        isLoading = false
    }

    // MARK: - Favorites

    /// Toggle favorite for the current recording, or show a login prompt if
    /// the user is not authenticated.
    func handleFavoriteTap() {
        guard let authManager else { return }
        guard authManager.isAuthenticated else {
            showingLoginAlert = true
            return
        }

        Task { [weak self] in
            guard let self, let favoritesManager = self.favoritesManager else { return }
            if let newCount = await favoritesManager.toggleFavorite(recordingId: self.recordingId) {
                self.localFavoriteCount = newCount
            }
        }
    }

    // MARK: - Private helpers

    /// Fetch recording detail, using an authenticated request if the user is logged in
    /// (so the response includes the user's own contribution, if any).
    private func fetchRecordingWithAuth() async -> Recording? {
        guard let authManager else { return nil }
        let url = URL.api(path: "/recordings/\(recordingId)")

        do {
            let data: Data
            if authManager.isAuthenticated {
                data = try await authManager.makeAuthenticatedRequest(url: url)
            } else {
                let (responseData, _) = try await URLSession.shared.data(from: url)
                data = responseData
            }
            return try JSONDecoder().decode(Recording.self, from: data)
        } catch {
            print("Error fetching recording detail: \(error)")
            return nil
        }
    }

    /// Auto-select the default release from the API, falling back to first release with art.
    private func autoSelectFirstRelease() {
        guard let releases = recording?.releases, !releases.isEmpty else { return }

        // Prefer the API's default_release_id — computed server-side to match
        // best_cover_art_* and best_spotify_url logic.
        if let defaultId = recording?.defaultReleaseId,
           releases.contains(where: { $0.id == defaultId }) {
            selectedReleaseId = defaultId
            return
        }

        // Fallback: sort by (has Spotify, newest year) and pick the first with cover art.
        let sorted = releases.sorted { r1, r2 in
            let r1HasSpotify = r1.spotifyAlbumId != nil
            let r2HasSpotify = r2.spotifyAlbumId != nil
            if r1HasSpotify != r2HasSpotify {
                return r1HasSpotify && !r2HasSpotify
            }
            switch (r1.releaseYear, r2.releaseYear) {
            case (nil, nil): return false
            case (nil, _): return false
            case (_, nil): return true
            case let (y1?, y2?): return y1 > y2
            }
        }

        if let releaseWithSpotifyAndArt = sorted.first(where: {
            $0.spotifyAlbumId != nil && ($0.coverArtLarge != nil || $0.coverArtMedium != nil)
        }) {
            selectedReleaseId = releaseWithSpotifyAndArt.id
            return
        }

        if let releaseWithArt = sorted.first(where: { $0.coverArtLarge != nil || $0.coverArtMedium != nil }) {
            selectedReleaseId = releaseWithArt.id
            return
        }

        selectedReleaseId = sorted.first?.id
    }
}

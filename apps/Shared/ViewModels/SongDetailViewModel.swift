//
//  SongDetailViewModel.swift
//  JazzReference
//
//  Shared view model for SongDetailView (iOS) and SongDetailView (Mac).
//  Owns the two-phase song loading, research-status polling, sort/reload,
//  and refresh-queueing logic that was previously duplicated across both
//  platforms (including the research polling state machine, byte-for-byte).
//
//  Usage pattern:
//    @StateObject private var viewModel = SongDetailViewModel()
//    ...
//    .task(id: currentSongId) {
//        await viewModel.load(songId: currentSongId)
//    }
//    .onDisappear {
//        viewModel.stopResearchStatusPolling()
//    }
//

import SwiftUI
import Combine

@MainActor
final class SongDetailViewModel: ObservableObject {
    // MARK: - Published state

    @Published var song: Song?
    @Published var isLoading = true
    @Published var isRecordingsLoading = true
    @Published var isRecordingsReloading = false
    @Published var transcriptions: [SoloTranscription] = []
    @Published var backingTracks: [Video] = []
    @Published var sortOrder: RecordingSortOrder = .year
    @Published var isRefreshing = false
    @Published var researchStatus: SongResearchStatus = .notInQueue

    // MARK: - Private

    private let networkManager = NetworkManager()
    private var researchStatusTimer: Timer?
    /// The song ID whose data currently populates `song`. Used by `load(songId:)`
    /// to skip re-fetching when the view re-appears with the same song (e.g.
    /// coming back from a child RecordingDetailView).
    private var currentLoadedSongId: String?

    // MARK: - Derived helpers

    /// Whether the song can be queued for refresh (not already in queue or being researched).
    var canQueueForRefresh: Bool {
        if case .notInQueue = researchStatus { return true }
        return false
    }

    /// Progress string for the "researching now" banner.
    func researchingMessage(progress: ResearchProgress?) -> String {
        guard let progress = progress else { return "Processing..." }
        return "\(progress.phaseDescription) (\(progress.current)/\(progress.total))"
    }

    /// Whether a song has any content to show in the Summary Information section.
    func hasSummaryContent(for song: Song) -> Bool {
        return song.structure != nil
            || song.composedKey != nil
            || hasExternalLinks(for: song)
    }

    /// Whether a song has any external reference links (Wikipedia, MusicBrainz, jazzstandards.com).
    func hasExternalLinks(for song: Song) -> Bool {
        return song.wikipediaUrl != nil
            || song.musicbrainzId != nil
            || song.externalReferences?["jazzstandards"] != nil
    }

    /// Whether a song has featured/authoritative recordings available.
    func hasAuthoritativeRecordings(for song: Song) -> Bool {
        guard let featured = song.featuredRecordings else { return false }
        return !featured.isEmpty
    }

    // MARK: - Loading

    /// Two-phase load: summary (fast) + backing tracks + recordings.
    /// Guards against redundant reloads when the view re-appears with the
    /// same song already in state; pass `force: true` to override.
    func load(songId: String, force: Bool = false) async {
        // Skip if we already have this song loaded and aren't mid-load.
        if !force, currentLoadedSongId == songId, song != nil, !isLoading {
            return
        }

        isLoading = true
        isRecordingsLoading = true
        currentLoadedSongId = songId

        // Reset research state before starting the new song.
        researchStatus = .notInQueue
        stopResearchStatusPolling()

        // Phase 1: summary (fast) — song metadata, transcriptions, featured recordings.
        let fetchedSong = await networkManager.fetchSongSummary(id: songId)
        song = fetchedSong
        transcriptions = fetchedSong?.transcriptions ?? []
        isLoading = false

        // Check if this song is in the research queue.
        checkResearchStatus(songId: songId)

        // Backing tracks.
        await refreshBackingTracks(songId: songId)

        // Phase 2: all recordings with streaming data.
        if let recordings = await networkManager.fetchSongRecordings(id: songId, sortBy: sortOrder) {
            song?.recordings = recordings
        }
        isRecordingsLoading = false
    }

    /// Pull-to-refresh variant: does NOT set `isLoading`, so content stays visible.
    /// Only updates state on success.
    func forceRefresh(songId: String) async {
        isRecordingsLoading = true

        if let fetchedSong = await networkManager.fetchSongSummary(id: songId) {
            song = fetchedSong
            transcriptions = fetchedSong.transcriptions ?? []
        }

        await refreshBackingTracks(songId: songId)

        if let recordings = await networkManager.fetchSongRecordings(id: songId, sortBy: sortOrder) {
            song?.recordings = recordings
        }
        isRecordingsLoading = false
    }

    /// Reload just the recordings list (Phase 2), leaving song metadata/transcriptions alone.
    /// Used when the sort order changes or when a child view edits community data.
    func reloadRecordings(songId: String) async {
        isRecordingsReloading = true
        if let recordings = await networkManager.fetchSongRecordings(id: songId, sortBy: sortOrder) {
            song?.recordings = recordings
        }
        isRecordingsReloading = false
    }

    /// Reload backing tracks. Called on initial load and by the `.videoCreated`
    /// notification handler.
    func refreshBackingTracks(songId: String) async {
        do {
            let videos = try await networkManager.fetchSongVideos(songId: songId, videoType: "backing_track")
            backingTracks = videos
        } catch {
            print("Error fetching backing tracks: \(error)")
        }
    }

    /// SwiftUI preview stub loader. Pulls synchronous stub data from NetworkManager.
    /// Only call from inside an `XCODE_RUNNING_FOR_PREVIEWS` guard.
    func loadPreview(songId: String) {
        song = networkManager.fetchSongDetailSync(id: songId)
        transcriptions = song?.transcriptions ?? []
        isLoading = false
        isRecordingsLoading = false
        currentLoadedSongId = songId
    }

    // MARK: - Refresh queue (background research)

    /// Queue this song for background research. Returns `true` if the request was accepted.
    /// The caller is responsible for showing a toast/alert in response.
    func queueRefresh(songId: String, forceRefresh: Bool) async -> Bool {
        isRefreshing = true
        let success = await networkManager.refreshSongData(songId: songId, forceRefresh: forceRefresh)
        isRefreshing = false
        if success {
            // Kick the research-status check so the "in queue" banner shows up quickly.
            checkResearchStatus(songId: songId)
        }
        return success
    }

    // MARK: - Research status polling

    /// Check whether this song is currently being researched or in the queue,
    /// then start/stop polling as appropriate.
    func checkResearchStatus(songId: String) {
        Task { [weak self] in
            guard let self else { return }
            let status = await self.networkManager.checkSongResearchStatus(songId: songId)
            self.researchStatus = status
            self.updateResearchStatusPolling(songId: songId)
        }
    }

    /// Stop the research-status polling timer. Safe to call from `.onDisappear`.
    func stopResearchStatusPolling() {
        researchStatusTimer?.invalidate()
        researchStatusTimer = nil
    }

    private func startResearchStatusPolling(songId: String) {
        guard researchStatusTimer == nil else { return }
        researchStatusTimer = Timer.scheduledTimer(withTimeInterval: 10.0, repeats: true) { [weak self] _ in
            Task { @MainActor [weak self] in
                self?.checkResearchStatus(songId: songId)
            }
        }
    }

    private func updateResearchStatusPolling(songId: String) {
        switch researchStatus {
        case .notInQueue:
            stopResearchStatusPolling()
        case .inQueue, .currentlyResearching:
            startResearchStatusPolling(songId: songId)
        }
    }
}

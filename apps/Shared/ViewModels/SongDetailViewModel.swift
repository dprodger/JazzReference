//
//  SongDetailViewModel.swift
//  Approach Note
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
//  Recordings loading — shell + hydrate
//  ------------------------------------
//  Phase 2 of `load(songId:)` used to fetch the full per-row payload for
//  every recording in one shot. That's ~120 KB gzipped for "Ain't
//  Misbehavin'" (759 rows) and scales badly for popular standards.
//
//  The new flow:
//   1. Fetch the shell (~18 KB) — enough to render group headers, run
//      filters, and show skeleton rows. UI renders immediately.
//   2. Kick off an initial hydration batch for the first N shell rows,
//      so the top-of-scroll has cover art by the time the user looks.
//   3. As each row's `.onAppear` fires, the view calls
//      `requestHydration(for:)` to enqueue that ID. The ViewModel
//      debounces the queue by 100ms, drains up to 50 IDs per batch, and
//      replaces the shell Recording with the hydrated Recording in
//      `song.recordings` — so SwiftUI diffing redraws only that row.

import SwiftUI
import Combine
import os

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

    private let songService = SongService()
    private let contentService = ContentService()
    private let researchService = ResearchService()
    private var researchStatusTimer: Timer?
    /// The song ID whose data currently populates `song`. Used by `load(songId:)`
    /// to skip re-fetching when the view re-appears with the same song (e.g.
    /// coming back from a child RecordingDetailView).
    private var currentLoadedSongId: String?

    /// The Task running the most recent `load` / `forceRefresh` /
    /// `reloadRecordings` call. A new load cancels this one first so a
    /// slower in-flight request for a different song can't overwrite the
    /// newer state when it finally returns (#110). `nil` when no load is
    /// currently running.
    private var currentLoadTask: Task<Void, Never>?

    // MARK: - Hydration state
    //
    // IDs we've already replaced with fully-hydrated Recording instances.
    // Skip re-requesting them when a row re-appears during scroll.
    private var hydratedIDs: Set<String> = []
    // IDs that a row has asked us to hydrate but we haven't sent to the
    // batch endpoint yet. Drained by `flushHydration()`.
    private var pendingHydrationIDs: Set<String> = []
    // Debounced task that eventually calls `flushHydration`. Reset every
    // time a new ID arrives, so we don't fire a batch for every onAppear
    // when a user scrolls quickly.
    private var hydrationDebounceTask: Task<Void, Never>?
    // How many shell rows to hydrate eagerly after the shell arrives,
    // before any row's .onAppear has fired. Sized to cover roughly one
    // screenful on iOS plus a little lookahead.
    private let eagerHydrationCount = 50
    // Cap per batch request. Matches server-side BATCH_MAX_IDS, but the
    // server enforces 100; we go lower so a single batch doesn't take
    // too long and blocks the next one.
    private let hydrationBatchSize = 50
    // Debounce window: long enough to coalesce onAppear events fired in
    // a burst (e.g. a DisclosureGroup expanding), short enough that
    // hydration doesn't lag visibly.
    private let hydrationDebounceNanos: UInt64 = 100_000_000  // 100ms

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

    /// Two-phase load: summary (fast) + backing tracks + recordings shell
    /// + eager first-screen hydration.
    /// Guards against redundant reloads when the view re-appears with the
    /// same song already in state; pass `force: true` to override.
    ///
    /// Any prior in-flight `load` / `forceRefresh` / `reloadRecordings` is
    /// cancelled before this one starts, so a slow response for an older
    /// song ID can't land after a newer one and overwrite the UI with
    /// stale data (#110). The cancellation checks inside `performLoad`
    /// abort mid-flight and leave `currentLoadedSongId` as whatever the
    /// newer load has set.
    func load(songId: String, force: Bool = false) async {
        // Skip if we already have this song loaded and aren't mid-load.
        if !force, currentLoadedSongId == songId, song != nil, !isLoading {
            return
        }
        await runCancellingPrior { [weak self] in
            await self?.performLoad(songId: songId)
        }
    }

    /// Pull-to-refresh variant: does NOT set `isLoading`, so content stays
    /// visible. Only updates state on success. Cancels any in-flight load.
    func forceRefresh(songId: String) async {
        await runCancellingPrior { [weak self] in
            await self?.performForceRefresh(songId: songId)
        }
    }

    /// Reload just the recordings list (Phase 2), leaving song metadata/
    /// transcriptions alone. Used when the sort order changes or when a
    /// child view edits community data. Cancels any in-flight load.
    func reloadRecordings(songId: String) async {
        await runCancellingPrior { [weak self] in
            await self?.performReloadRecordings(songId: songId)
        }
    }

    // MARK: - Load implementations (run inside `currentLoadTask`)

    /// Cancel any prior load Task, then run `work` as the new current load.
    /// The caller awaits completion so `.task { await vm.load(...) }` call
    /// sites still see the load finish (or the new cancel-and-restart
    /// unwind) before returning control to SwiftUI.
    private func runCancellingPrior(_ work: @escaping @Sendable () async -> Void) async {
        currentLoadTask?.cancel()
        let task = Task { await work() }
        currentLoadTask = task
        await task.value
        // If nothing else scheduled a new load while we were running,
        // clear the handle so we don't hold onto a completed Task.
        if currentLoadTask == task {
            currentLoadTask = nil
        }
    }

    private func performLoad(songId: String) async {
        isLoading = true
        isRecordingsLoading = true
        currentLoadedSongId = songId
        resetHydrationState()

        // Reset research state before starting the new song.
        researchStatus = .notInQueue
        stopResearchStatusPolling()

        // Phase 1: summary (fast) — song metadata, transcriptions, featured recordings.
        let fetchedSong = await songService.fetchSongSummary(id: songId)
        if Task.isCancelled { return }
        song = fetchedSong
        transcriptions = fetchedSong?.transcriptions ?? []
        isLoading = false

        // Check if this song is in the research queue.
        checkResearchStatus(songId: songId)

        // Backing tracks.
        await refreshBackingTracks(songId: songId)
        if Task.isCancelled { return }

        // Phase 2: shell (fast, skeleton rows + group headers + filters).
        let shellRecordings = await songService.fetchSongRecordingsShell(id: songId, sortBy: sortOrder)
        if Task.isCancelled { return }
        if let shellRecordings = shellRecordings {
            song?.recordings = shellRecordings
            // Once the shell is in, the rest of the UI can render. Rows
            // will drive their own hydration via `requestHydration(for:)`
            // as they appear.
            isRecordingsLoading = false
            kickOffEagerHydration()
        } else {
            // Shell failed. Clear loading state so UI can show an empty
            // or error state instead of spinning forever.
            isRecordingsLoading = false
        }
    }

    private func performForceRefresh(songId: String) async {
        isRecordingsLoading = true
        resetHydrationState()

        let fetchedSong = await songService.fetchSongSummary(id: songId)
        if Task.isCancelled { return }
        if let fetchedSong = fetchedSong {
            song = fetchedSong
            transcriptions = fetchedSong.transcriptions ?? []
        }

        await refreshBackingTracks(songId: songId)
        if Task.isCancelled { return }

        let shellRecordings = await songService.fetchSongRecordingsShell(id: songId, sortBy: sortOrder)
        if Task.isCancelled { return }
        if let shellRecordings = shellRecordings {
            song?.recordings = shellRecordings
            kickOffEagerHydration()
        }
        isRecordingsLoading = false
    }

    private func performReloadRecordings(songId: String) async {
        isRecordingsReloading = true
        resetHydrationState()
        let shellRecordings = await songService.fetchSongRecordingsShell(id: songId, sortBy: sortOrder)
        if Task.isCancelled { return }
        if let shellRecordings = shellRecordings {
            song?.recordings = shellRecordings
            kickOffEagerHydration()
        }
        isRecordingsReloading = false
    }

    // MARK: - Hydration — called by row views

    /// A recording row became visible in the list. Queue its ID for the
    /// next batch hydration, unless we've already hydrated it or already
    /// have it pending. The debounced task flushes every 100ms so a burst
    /// of onAppear events (typical when a DisclosureGroup expands) turns
    /// into a single batch request.
    func requestHydration(for recordingID: String) {
        guard !hydratedIDs.contains(recordingID),
              !pendingHydrationIDs.contains(recordingID) else {
            return
        }
        pendingHydrationIDs.insert(recordingID)
        scheduleHydrationFlush()
    }

    // MARK: - Hydration — private

    private func resetHydrationState() {
        hydrationDebounceTask?.cancel()
        hydrationDebounceTask = nil
        hydratedIDs.removeAll()
        pendingHydrationIDs.removeAll()
    }

    /// After the shell arrives, eagerly request hydration for the first N
    /// rows so the top-of-scroll has cover art by the time the user
    /// looks at it. Without this the user would see skeleton rows until
    /// they scroll (which triggers onAppear + viewport-driven hydration).
    private func kickOffEagerHydration() {
        guard let recordings = song?.recordings else { return }
        for row in recordings.prefix(eagerHydrationCount) {
            requestHydration(for: row.id)
        }
    }

    private func scheduleHydrationFlush() {
        hydrationDebounceTask?.cancel()
        hydrationDebounceTask = Task { [weak self] in
            guard let self else { return }
            try? await Task.sleep(nanoseconds: self.hydrationDebounceNanos)
            if Task.isCancelled { return }
            await self.flushHydration()
        }
    }

    private func flushHydration() async {
        // Take up to `hydrationBatchSize` IDs for this call; any extras
        // stay in `pendingHydrationIDs` and get picked up by the next
        // flush scheduled at the end of this method.
        let idsToHydrate = Array(pendingHydrationIDs.prefix(hydrationBatchSize))
        guard !idsToHydrate.isEmpty else { return }
        pendingHydrationIDs.subtract(idsToHydrate)

        guard let hydrated = await songService.fetchRecordingsBatch(ids: idsToHydrate) else {
            // Batch failed. Don't re-queue — a real failure is likely
            // systemic (e.g. offline), retries would just pile up.
            // User can pull-to-refresh to retry the whole list.
            return
        }

        // Merge hydrated rows into song.recordings. Each hydrated row
        // replaces the shell version wholesale — RecordingGrouping's
        // filters read from either shape so the swap is transparent.
        guard var recordings = song?.recordings else { return }
        var hydratedByID: [String: Recording] = [:]
        for row in hydrated {
            hydratedByID[row.id] = row
        }
        for idx in recordings.indices {
            if let replacement = hydratedByID[recordings[idx].id] {
                recordings[idx] = replacement
                hydratedIDs.insert(replacement.id)
            }
        }
        song?.recordings = recordings

        // If more IDs accumulated while we were awaiting the batch, flush
        // again. The next call is debounced so this doesn't hot-loop.
        if !pendingHydrationIDs.isEmpty {
            scheduleHydrationFlush()
        }
    }

    /// Reload backing tracks. Called on initial load and by the `.videoCreated`
    /// notification handler.
    func refreshBackingTracks(songId: String) async {
        do {
            let videos = try await contentService.fetchSongVideos(songId: songId, videoType: "backing_track")
            backingTracks = videos
        } catch {
            Log.ui.error("Error fetching backing tracks: \(error.localizedDescription)")
        }
    }

    /// SwiftUI preview stub loader. Pulls synchronous stub data from SongService.
    /// Only call from inside an `XCODE_RUNNING_FOR_PREVIEWS` guard.
    #if DEBUG
    func loadPreview(songId: String) {
        song = songService.fetchSongDetailSync(id: songId)
        transcriptions = song?.transcriptions ?? []
        isLoading = false
        isRecordingsLoading = false
        currentLoadedSongId = songId
    }
    #endif

    // MARK: - Refresh queue (background research)

    /// Queue this song for background research. Returns `true` if the request was accepted.
    /// The caller is responsible for showing a toast/alert in response.
    func queueRefresh(songId: String, forceRefresh: Bool) async -> Bool {
        isRefreshing = true
        let success = await researchService.refreshSongData(songId: songId, forceRefresh: forceRefresh)
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
            let status = await self.researchService.checkSongResearchStatus(songId: songId)
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

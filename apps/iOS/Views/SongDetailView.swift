//
//  SongDetailView.swift
//  JazzReference
//
//  UPDATED: Added visual swipe navigation cues with parallax and arrows
//  UPDATED: Replaced alert with toast notification for song queue confirmation
//  FIXED: Broken up body to avoid type-checker timeout
//  UPDATED: Grouped Structure, Learn More, and References into collapsible Summary Information section
//  FIXED: Recording sort order now consistently passed to all API calls
//

import SwiftUI
import Combine

// MARK: - Song Detail View
struct SongDetailView: View {
    let songId: String
    let allSongs: [Song]
    let repertoireId: String

    // Shared data + network state lives on the view model; layout/presentation
    // state stays here.
    @StateObject private var viewModel = SongDetailViewModel()

    @State private var currentSongId: String

    // NEW: Drag gesture state for visual feedback
    @GestureState private var dragOffset: CGFloat = 0

    // NEW: Repertoire management
    @EnvironmentObject var repertoireManager: RepertoireManager
    @State private var showAddToRepertoireSheet = false
    @State private var showErrorAlert = false
    @State private var alertMessage = ""
    @State private var isAddingToRepertoire = false

    // Song refresh management
    @State private var showRefreshConfirmation = false

    // NEW: Toast notification
    @State private var toast: ToastItem?

    // NEW: Summary Information section expansion state (starts collapsed)
    @State private var isSummaryInfoExpanded = false

    // Read-only aliases so existing reference sites in this view can keep
    // using the short names unchanged.
    private var song: Song? { viewModel.song }
    private var isLoading: Bool { viewModel.isLoading }
    private var transcriptions: [SoloTranscription] { viewModel.transcriptions }
    private var backingTracks: [Video] { viewModel.backingTracks }
    private var isRefreshing: Bool { viewModel.isRefreshing }
    private var researchStatus: SongResearchStatus { viewModel.researchStatus }
    private var recordingSortOrder: RecordingSortOrder { viewModel.sortOrder }
    private var isRecordingsReloading: Bool { viewModel.isRecordingsReloading }
    private var isRecordingsLoading: Bool { viewModel.isRecordingsLoading }
    private var canQueueForRefresh: Bool { viewModel.canQueueForRefresh }

    // Playback preference
    @AppStorage("preferredStreamingService") private var preferredStreamingService: String = StreamingService.spotify.rawValue
    @Environment(\.openURL) private var openURL

    // MARK: - Initializer
    init(songId: String, allSongs: [Song] = [], repertoireId: String = "all") {
        self.songId = songId
        self.allSongs = allSongs
        self.repertoireId = repertoireId
        self._currentSongId = State(initialValue: songId)
    }
    
    // MARK: - Navigation Helpers
    
    private var currentIndex: Int? {
        allSongs.firstIndex { $0.id == currentSongId }
    }
    
    private var canNavigatePrevious: Bool {
        guard let index = currentIndex else { return false }
        return index > 0
    }
    
    private var canNavigateNext: Bool {
        guard let index = currentIndex else { return false }
        return index < allSongs.count - 1
    }
    
    private func navigateToPrevious() {
        guard let index = currentIndex, canNavigatePrevious else { return }
        let previousSong = allSongs[index - 1]
        currentSongId = previousSong.id
        toast = nil
        Task { await viewModel.load(songId: currentSongId, force: true) }
    }

    private func navigateToNext() {
        guard let index = currentIndex, canNavigateNext else { return }
        let nextSong = allSongs[index + 1]
        currentSongId = nextSong.id
        toast = nil
        Task { await viewModel.load(songId: currentSongId, force: true) }
    }

    // MARK: - Song Refresh

    /// Queue song for background research and show a toast with the result.
    private func refreshSongData(forceRefresh: Bool) {
        let refreshType = forceRefresh ? "full" : "quick"
        Task {
            let success = await viewModel.queueRefresh(songId: currentSongId, forceRefresh: forceRefresh)
            if success {
                toast = ToastItem(
                    type: .success,
                    message: "Song queued for \(refreshType) refresh. Data will be updated in the background."
                )
            } else {
                toast = ToastItem(
                    type: .error,
                    message: "Failed to queue song for refresh. Please try again."
                )
            }
        }
    }

    // MARK: - Research Status Indicator

    /// Visual indicator showing research queue status
    @ViewBuilder
    private var researchStatusIndicator: some View {
        switch researchStatus {
        case .currentlyResearching(let progress):
            ResearchStatusBanner(
                icon: "waveform.circle.fill",
                iconColor: JazzTheme.burgundy,
                title: "Researching Now",
                message: viewModel.researchingMessage(progress: progress),
                helperText: "We're scouring the internet to learn more about this song... Check back in a while to see what we've found.",
                isAnimating: true
            )
        case .inQueue(let position):
            ResearchStatusBanner(
                icon: "clock.fill",
                iconColor: JazzTheme.amber,
                title: "In Research Queue",
                message: "Position \(position) in queue",
                helperText: "This song is in the queue to get researched... Check back in a while to see what we've found.",
                isAnimating: false
            )
        case .notInQueue:
            EmptyView()
        }
    }

    // MARK: - Summary predicates (delegated to the view model)

    private func hasSummaryContent(for song: Song) -> Bool {
        viewModel.hasSummaryContent(for: song)
    }

    private func hasAuthoritativeRecordings(for song: Song) -> Bool {
        viewModel.hasAuthoritativeRecordings(for: song)
    }

    // MARK: - Playback Helpers

    /// Whether any recording has streaming links available
    private var canPlay: Bool {
        guard let song = song else { return false }
        return song.hasAnyStreaming == true
    }

    /// Get the best playback URL for the song (from first featured or first available recording)
    private var bestPlaybackInfo: (service: String, url: String)? {
        guard let song = song else { return nil }

        // First try featured recordings
        if let featured = song.featuredRecordings {
            for recording in featured {
                if let playback = recording.playbackUrl(preferring: preferredStreamingService) {
                    return playback
                }
            }
        }

        // Then try all recordings
        if let recordings = song.recordings {
            for recording in recordings {
                if let playback = recording.playbackUrl(preferring: preferredStreamingService) {
                    return playback
                }
            }
        }

        return nil
    }

    /// Open the best available playback URL
    private func openPlayback() {
        guard let playback = bestPlaybackInfo,
              let url = URL(string: playback.url) else { return }
        openURL(url)
    }
    
    // MARK: - Song Content View
    
    @ViewBuilder
    private func songContentView(for song: Song) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            VStack(alignment: .leading, spacing: 16) {
            // Song Information Header
            VStack(alignment: .leading, spacing: 12) {
                HStack(alignment: .firstTextBaseline, spacing: 8) {
                    Text(song.title)
                        .font(JazzTheme.largeTitle())
                        .bold()
                        .foregroundColor(JazzTheme.charcoal)
                    if let year = song.composedYear {
                        Text("(\(String(year)))")
                            .font(JazzTheme.title2())
                            .foregroundColor(JazzTheme.smokeGray)
                    }
                }
                .onLongPressGesture {
                    if canQueueForRefresh {
                        showRefreshConfirmation = true
                    }
                }

                if let composer = song.composer {
                    HStack {
                        Image(systemName: "music.note.list")
                            .foregroundColor(JazzTheme.brass)
                        Text(composer)
                            .font(JazzTheme.title3())
                            .foregroundColor(JazzTheme.smokeGray)
                    }
                }

                // Song Reference (if available)
                if let songRef = song.songReference {
                    HStack(alignment: .top, spacing: 8) {
                        Image(systemName: "book.closed.fill")
                            .foregroundColor(JazzTheme.brass)
                            .font(JazzTheme.subheadline())
                        Text(songRef)
                            .font(JazzTheme.subheadline())
                            .foregroundColor(JazzTheme.smokeGray)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    .padding(.top, 4)
                }

                // MARK: - Research Status Indicator
                researchStatusIndicator

                // MARK: - Summary Information Section (Collapsible)
                if hasSummaryContent(for: song) {
                    summaryInfoSection(for: song)
                }
                
                // MARK: - Authoritative Recordings Carousel
                if hasAuthoritativeRecordings(for: song) {
                    authoritativeRecordingsSection(for: song)
                }
            }
            .padding()
            
            Divider()
                .padding(.horizontal)
            
            // MARK: - RECORDINGS SECTION
                RecordingsSection(
                    recordings: song.recordings ?? [],
                    recordingSortOrder: $viewModel.sortOrder,
                    isReloading: isRecordingsReloading || isRecordingsLoading,
                    onSortOrderChanged: { [self] _ in
                        Task { await viewModel.reloadRecordings(songId: currentSongId) }
                    },
                    onCommunityDataChanged: {
                        Task { await viewModel.reloadRecordings(songId: currentSongId) }
                    }
                )
            // MARK: - TRANSCRIPTIONS SECTION
            TranscriptionsSection(transcriptions: transcriptions)

            // MARK: - BACKING TRACKS SECTION
            BackingTracksSection(videos: backingTracks)
        }
        .padding(.bottom)
        }
    }
    
    // MARK: - Summary Information Section
    
    @ViewBuilder
    private func summaryInfoSection(for song: Song) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            // Collapsible Header
            Button(action: {
                withAnimation {
                    isSummaryInfoExpanded.toggle()
                }
            }) {
                HStack {
                    Text("Summary Information")
                        .font(JazzTheme.title3())
                        .bold()
                        .foregroundColor(JazzTheme.charcoal)
                    Spacer()
                    Image(systemName: isSummaryInfoExpanded ? "chevron.up" : "chevron.down")
                        .foregroundColor(JazzTheme.brass)
                }
                .padding()
                .background(JazzTheme.cardBackground)
            }
            .buttonStyle(.plain)
            
            // Expandable Content
            if isSummaryInfoExpanded {
                VStack(alignment: .leading, spacing: 16) {
                    // Structure
                    if let structure = song.structure {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Structure")
                                .font(JazzTheme.headline())
                                .foregroundColor(JazzTheme.charcoal)
                            Text(structure)
                                .font(JazzTheme.body())
                                .foregroundColor(JazzTheme.smokeGray)
                        }
                        .padding()
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(Color.white)
                        .cornerRadius(8)
                    }

                    // Composed Key
                    if let composedKey = song.composedKey {
                        HStack(spacing: 8) {
                            Image(systemName: "tuningfork")
                                .foregroundColor(JazzTheme.brass)
                            Text("Original Key:")
                                .font(JazzTheme.headline())
                                .foregroundColor(JazzTheme.charcoal)
                            Text(composedKey)
                                .font(JazzTheme.body())
                                .foregroundColor(JazzTheme.smokeGray)
                        }
                        .padding()
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(Color.white)
                        .cornerRadius(8)
                    }

                    // External References Panel (Learn More)
                    ExternalReferencesPanel(
                        wikipediaUrl: song.wikipediaUrl,
                        musicbrainzId: song.musicbrainzId,
                        externalReferences: song.externalReferences,
                        entityId: song.id,
                        entityName: song.title
                    )
                }
                .padding()
                .background(JazzTheme.cardBackground)
            }
        }
        .cornerRadius(10)
        .padding(.top, 8)
    }
    
    // MARK: - Authoritative Recordings Carousel Section
    // Uses featuredRecordings from summary endpoint (already filtered server-side)
    @ViewBuilder
    private func authoritativeRecordingsSection(for song: Song) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            // Header
            Text("Featured Recordings")
                .font(JazzTheme.title2())
                .bold()
                .foregroundColor(JazzTheme.charcoal)

            // Introductory text
            Text("Take a look at these important recordings for this song.")
                .font(JazzTheme.subheadline())
                .foregroundColor(JazzTheme.smokeGray)

            // Horizontal scrolling carousel - use featuredRecordings from summary
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(alignment: .top, spacing: 20) {
                    ForEach(song.featuredRecordings ?? []) { recording in
                        NavigationLink(destination: RecordingDetailView(
                            recordingId: recording.id,
                            onCommunityDataChanged: {
                                Task { await viewModel.reloadRecordings(songId: currentSongId) }
                            }
                        )) {
                            AuthoritativeRecordingCard(recording: recording)
                        }
                        .buttonStyle(.plain)
                    }
                }
                .padding(.horizontal, 4)
            }
        }
        .padding(16)
        .background(Color.white)
        .cornerRadius(12)
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(JazzTheme.smokeGray.opacity(0.3), lineWidth: 1)
        )
        .padding(.top, 8)
    }
    
    // MARK: - Body (broken into smaller chunks to avoid type-checker timeout)
    
    var body: some View {
        contentView
    }
    
    // MARK: - View Builders
    
    private var contentView: some View {
        mainScrollView
            .background(JazzTheme.backgroundLight)
            // NEW: Visual feedback for swipe gestures
            .offset(x: dragOffset * 0.3) // Parallax effect - subtle movement
            .opacity(1 - abs(dragOffset) / 1000.0) // Subtle fade during drag
            .overlay(alignment: .leading) {
                navigationArrow(direction: .left, isVisible: dragOffset > 50 && canNavigatePrevious)
            }
            .overlay(alignment: .trailing) {
                navigationArrow(direction: .right, isVisible: dragOffset < -50 && canNavigateNext)
            }
            .jazzNavigationBar(title: song?.title ?? "")
            .toolbar {
                toolbarContent
            }
            .task {
                await viewModel.load(songId: currentSongId)
            }
            .onReceive(NotificationCenter.default.publisher(for: .transcriptionCreated)) { notification in
                // Refresh if this notification is for our song
                if let songId = notification.userInfo?["songId"] as? String,
                   songId == currentSongId {
                    Task { await viewModel.load(songId: currentSongId) }
                }
            }
            .onReceive(NotificationCenter.default.publisher(for: .videoCreated)) { notification in
                // Refresh backing tracks if this notification is for our song
                if let songId = notification.userInfo?["songId"] as? String,
                   songId == currentSongId {
                    Task { await viewModel.refreshBackingTracks(songId: currentSongId) }
                }
            }
            .highPriorityGesture(swipeGesture)
            .sheet(isPresented: $showAddToRepertoireSheet) {
                repertoireSheet
            }
            .alert("Error", isPresented: $showErrorAlert) {
                Button("OK", role: .cancel) { }
            } message: {
                Text(alertMessage)
            }
            .confirmationDialog(
                "Refresh Song Data",
                isPresented: $showRefreshConfirmation,
                titleVisibility: .visible
            ) {
                Button("Quick Refresh") {
                    refreshSongData(forceRefresh: false)
                }
                Button("Full Refresh") {
                    refreshSongData(forceRefresh: true)
                }
                Button("Cancel", role: .cancel) { }
            } message: {
                Text("Quick refresh uses cached data for faster results. Full refresh re-fetches everything from external sources.")
            }
            .toast($toast)
            .onDisappear {
                viewModel.stopResearchStatusPolling()
            }
            .overlay(alignment: .bottom) {
                pageIndicatorView
            }
    }
    
    private var mainScrollView: some View {
        ScrollView {
            if isLoading {
                loadingView
            } else if let song = song {
                songContentView(for: song)
            } else {
                notFoundView
            }
        }
        .refreshable {
            await viewModel.forceRefresh(songId: currentSongId)
        }
    }
    
    private var loadingView: some View {
        VStack {
            Spacer()
            ProgressView()
                .progressViewStyle(CircularProgressViewStyle(tint: JazzTheme.burgundy))
                .scaleEffect(1.5)
            Spacer()
        }
        .frame(maxWidth: .infinity, minHeight: 300)
    }
    
    private var notFoundView: some View {
        VStack(spacing: 16) {
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 50))
                .foregroundColor(JazzTheme.amber)
            Text("Unable to load song")
                .font(JazzTheme.headline())
                .foregroundColor(JazzTheme.charcoal)
            Text("There was a problem loading the song details.")
                .font(JazzTheme.subheadline())
                .foregroundColor(JazzTheme.smokeGray)
                .multilineTextAlignment(.center)
                .padding(.horizontal)
        }
        .frame(maxWidth: .infinity, minHeight: 300)
    }
    
    // MARK: - Swipe Gesture
    
    private var swipeGesture: some Gesture {
        DragGesture(minimumDistance: 50)
            .updating($dragOffset) { value, state, _ in
                // Only update state if navigation is possible in that direction
                if value.translation.width > 0 && canNavigatePrevious {
                    state = value.translation.width
                } else if value.translation.width < 0 && canNavigateNext {
                    state = value.translation.width
                }
            }
            .onEnded { value in
                let threshold: CGFloat = 100
                
                if value.translation.width > threshold && canNavigatePrevious {
                    // Swipe right - go to previous
                    navigateToPrevious()
                } else if value.translation.width < -threshold && canNavigateNext {
                    // Swipe left - go to next
                    navigateToNext()
                }
            }
    }
    
    // MARK: - Toolbar Content

    @ToolbarContentBuilder
    private var toolbarContent: some ToolbarContent {
        ToolbarItem(placement: .navigationBarTrailing) {
            HStack(spacing: 16) {
                // Play button - only show if streaming is available
                if canPlay {
                    Button(action: openPlayback) {
                        Image(systemName: "play.circle.fill")
                            .font(.system(size: 22))
                            .foregroundColor(playButtonColor)
                    }
                }

                // Add to repertoire button
                Button(action: { showAddToRepertoireSheet = true }) {
                    Image(systemName: "plus.circle")
                }
            }
        }
    }

    /// Color for play button based on which service will be used
    private var playButtonColor: Color {
        guard let playback = bestPlaybackInfo,
              let service = StreamingService(key: playback.service) else {
            return JazzTheme.burgundy
        }
        return service.brandColor
    }
    
    // MARK: - Navigation Arrow
    
    private func navigationArrow(direction: NavigationDirection, isVisible: Bool) -> some View {
        Image(systemName: direction == .left ? "chevron.left" : "chevron.right")
            .font(.system(size: 40, weight: .bold))
            .foregroundColor(JazzTheme.burgundy)
            .opacity(isVisible ? 0.8 : 0)
            .scaleEffect(isVisible ? 1.2 : 0.8)
            .padding(.horizontal, 20)
            .animation(.spring(response: 0.3), value: isVisible)
    }
    
    // MARK: - Navigation Direction Enum
    
    private enum NavigationDirection {
        case left, right
    }
    
    private var repertoireSheet: some View {
        AddToRepertoireSheet(
            songId: currentSongId,
            songTitle: song?.title ?? "Unknown",
            repertoireManager: repertoireManager,
            isPresented: $showAddToRepertoireSheet,
            onSuccess: { message in
                toast = ToastItem(type: .success, message: message)
            },
            onError: { message in
                alertMessage = message
                showErrorAlert = true
            }
        )
    }
    
    @ViewBuilder
    private var pageIndicatorView: some View {
        if !allSongs.isEmpty && allSongs.count > 1 && !isLoading, let index = currentIndex {
            HStack(spacing: 6) {
                let visibleRange = calculateVisibleDotRange(current: index, total: allSongs.count)
                
                ForEach(visibleRange, id: \.self) { dotIndex in
                    Circle()
                        .fill(dotIndex == index ? JazzTheme.burgundy : JazzTheme.smokeGray.opacity(0.3))
                        .frame(width: dotIndex == index ? 8 : 6, height: dotIndex == index ? 8 : 6)
                        .animation(.easeInOut(duration: 0.2), value: index)
                }
            }
            .padding(.vertical, 8)
            .padding(.horizontal, 12)
            .background(.ultraThinMaterial)
            .cornerRadius(12)
            .padding(.bottom, 12)
        }
    }
    
    // MARK: - Helper for Page Dots
    
    private func calculateVisibleDotRange(current: Int, total: Int) -> Range<Int> {
        let maxDots = 5
        
        if total <= maxDots {
            return 0..<total
        }
        
        // Try to center the current dot
        let halfDots = maxDots / 2
        var start = current - halfDots
        var end = current + halfDots + 1
        
        // Adjust if we're near the beginning
        if start < 0 {
            end += abs(start)
            start = 0
        }
        
        // Adjust if we're near the end
        if end > total {
            start -= (end - total)
            end = total
        }
        
        // Ensure we don't go below 0
        start = max(0, start)
        
        return start..<end
    }
}

// MARK: - Authoritative Recording Card
struct AuthoritativeRecordingCard: View {
    let recording: Recording
    @State private var showingBackCover = false

    private let artworkSize: CGFloat = 180

    // Get artist name - prefer artist_credit from default release, fall back to performers
    private var artistName: String {
        // Use artist_credit from the default release if available
        if let artistCredit = recording.artistCredit, !artistCredit.isEmpty {
            return artistCredit
        }
        // Fall back to performers lookup
        if let performers = recording.performers {
            // First try to find a performer with "leader" role
            if let leader = performers.first(where: { $0.role?.lowercased() == "leader" }) {
                return leader.name
            }
            // Fall back to first performer if no leader
            if let first = performers.first {
                return first.name
            }
        }
        return "Various Artists"
    }

    // Front cover URL
    private var frontCoverUrl: String? {
        recording.bestAlbumArtLarge ?? recording.bestAlbumArtMedium
    }

    // Back cover URL
    private var backCoverUrl: String? {
        recording.backCoverArtLarge ?? recording.backCoverArtMedium
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Album Art with flip support
            ZStack(alignment: .topTrailing) {
                // Album art with card-flip animation
                ZStack {
                    // Front cover
                    Group {
                        if let frontUrl = frontCoverUrl {
                            AsyncImage(url: URL(string: frontUrl)) { phase in
                                switch phase {
                                case .empty:
                                    Rectangle()
                                        .fill(JazzTheme.smokeGray.opacity(0.2))
                                        .overlay {
                                            ProgressView()
                                                .tint(JazzTheme.burgundy)
                                        }
                                case .success(let image):
                                    image
                                        .resizable()
                                        .aspectRatio(contentMode: .fill)
                                case .failure:
                                    Rectangle()
                                        .fill(JazzTheme.smokeGray.opacity(0.2))
                                        .overlay {
                                            Image(systemName: "music.note")
                                                .font(.system(size: 40))
                                                .foregroundColor(JazzTheme.smokeGray)
                                        }
                                @unknown default:
                                    EmptyView()
                                }
                            }
                        } else {
                            Rectangle()
                                .fill(JazzTheme.smokeGray.opacity(0.2))
                                .overlay {
                                    Image(systemName: "music.note")
                                        .font(.system(size: 40))
                                        .foregroundColor(JazzTheme.smokeGray)
                                }
                        }
                    }
                    .frame(width: artworkSize, height: artworkSize)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
                    .opacity(showingBackCover ? 0 : 1)

                    // Back cover (pre-rotated so it appears correct after flip)
                    if let backUrl = backCoverUrl {
                        AsyncImage(url: URL(string: backUrl)) { phase in
                            switch phase {
                            case .empty:
                                Rectangle()
                                    .fill(JazzTheme.smokeGray.opacity(0.2))
                                    .overlay {
                                        ProgressView()
                                            .tint(JazzTheme.burgundy)
                                    }
                            case .success(let image):
                                image
                                    .resizable()
                                    .aspectRatio(contentMode: .fill)
                            case .failure:
                                Rectangle()
                                    .fill(JazzTheme.smokeGray.opacity(0.2))
                            @unknown default:
                                EmptyView()
                            }
                        }
                        .frame(width: artworkSize, height: artworkSize)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                        .rotation3DEffect(.degrees(180), axis: (x: 0, y: 1, z: 0))
                        .opacity(showingBackCover ? 1 : 0)
                    }
                }
                .rotation3DEffect(
                    .degrees(showingBackCover ? 180 : 0),
                    axis: (x: 0, y: 1, z: 0)
                )

                // Flip badge (shown when back cover available)
                if recording.canFlipToBackCover {
                    Button(action: {
                        withAnimation(.easeInOut(duration: 0.4)) {
                            showingBackCover.toggle()
                        }
                    }) {
                        Image(systemName: showingBackCover ? "arrow.uturn.backward" : "arrow.trianglehead.2.clockwise.rotate.90")
                            .foregroundColor(.white)
                            .font(.system(size: 10, weight: .semibold))
                            .padding(6)
                            .background(Color.black.opacity(0.6))
                            .clipShape(Circle())
                    }
                    .buttonStyle(PlainButtonStyle())
                    .padding(6)
                }

                // Source badge (bottom-left, shows front or back cover source)
                VStack {
                    Spacer()
                    HStack {
                        if showingBackCover {
                            AlbumArtSourceBadge(
                                source: recording.backCoverSource,
                                sourceUrl: recording.backCoverSourceUrl
                            )
                        } else {
                            AlbumArtSourceBadge(
                                source: recording.displayAlbumArtSource,
                                sourceUrl: recording.displayAlbumArtSourceUrl
                            )
                        }
                        Spacer()
                    }
                }
                .padding(6)
            }
            .frame(width: artworkSize, height: artworkSize)
            .shadow(color: .black.opacity(0.15), radius: 8, x: 0, y: 4)

            // Recording Info - fixed height for consistent card sizing
            VStack(alignment: .leading, spacing: 4) {
                // Artist Name
                Text(artistName)
                    .font(JazzTheme.subheadline())
                    .fontWeight(.semibold)
                    .foregroundColor(JazzTheme.brass)
                    .lineLimit(1)

                // Album Title
                Text(recording.albumTitle ?? "Unknown Album")
                    .font(JazzTheme.body())
                    .fontWeight(.medium)
                    .foregroundColor(JazzTheme.charcoal)
                    .lineLimit(2)

                // Recording title (when different from song title)
                if let recordingTitle = recording.displayTitle {
                    Text("(\(recordingTitle))")
                        .font(JazzTheme.caption())
                        .italic()
                        .foregroundColor(JazzTheme.brass)
                        .lineLimit(1)
                }

                // Year (always reserve space)
                Text(recording.recordingYear.map { String($0) } ?? " ")
                    .font(JazzTheme.caption())
                    .foregroundColor(JazzTheme.smokeGray)
            }
            .frame(width: artworkSize, alignment: .topLeading)
        }
        .padding(12)
        .background(JazzTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}

// MARK: - Previews
#Preview("Song Detail - Full") {
    NavigationStack {
        SongDetailView(songId: "preview-song-1")
            .environmentObject(RepertoireManager())
    }
}

#Preview("Song Detail - Minimal") {
    NavigationStack {
        SongDetailView(songId: "preview-song-2")
            .environmentObject(RepertoireManager())
    }
}

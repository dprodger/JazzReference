//
//  SongDetailView.swift
//  JazzReference
//
//  UPDATED: Added visual swipe navigation cues with parallax and arrows
//  UPDATED: Replaced alert with toast notification for song queue confirmation
//  FIXED: Broken up body to avoid type-checker timeout
//

import SwiftUI
import Combine

// MARK: - Song Detail View
struct SongDetailView: View {
    let songId: String
    let allSongs: [Song]
    let repertoireId: String
    
    @State private var currentSongId: String
    @State private var song: Song?
    @State private var isLoading = true
    @State private var transcriptions: [SoloTranscription] = []
    
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
    @State private var isRefreshing = false
    
    // NEW: Toast notification
    @State private var toast: ToastItem?
    
    @State private var recordingSortOrder: RecordingSortOrder = .authority
    @State private var showingSortOptions = false


    
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
        loadCurrentSong()
    }
    
    private func navigateToNext() {
        guard let index = currentIndex, canNavigateNext else { return }
        let nextSong = allSongs[index + 1]
        currentSongId = nextSong.id
        loadCurrentSong()
    }
    
    private func loadCurrentSong() {
        isLoading = true
        Task {
            let networkManager = NetworkManager()
            // OPTIMIZED: Single API call now includes transcriptions
            let fetchedSong = await networkManager.fetchSongDetail(id: currentSongId)
            await MainActor.run {
                song = fetchedSong
                transcriptions = fetchedSong?.transcriptions ?? []
                isLoading = false
            }
        }
    }
    
    // MARK: - Song Refresh
    
    private func refreshSongData() {
        isRefreshing = true
        
        Task {
            let networkManager = NetworkManager()
            let success = await networkManager.refreshSongData(songId: currentSongId)
            
            await MainActor.run {
                isRefreshing = false
                if success {
                    // Show success toast
                    toast = ToastItem(
                        type: .success,
                        message: "Song queued for research. Data will be updated in the background."
                    )
                } else {
                    // Show error toast
                    toast = ToastItem(
                        type: .error,
                        message: "Failed to queue song for refresh. Please try again."
                    )
                }
            }
        }
    }
    
    // MARK: - Song Content View
    
    @ViewBuilder
    private func songContentView(for song: Song) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            VStack(alignment: .leading, spacing: 16) {
            // Song Information Header
            VStack(alignment: .leading, spacing: 12) {
                Text(song.title)
                    .font(.largeTitle)
                    .bold()
                    .foregroundColor(JazzTheme.charcoal)
                    .onLongPressGesture {
                        showRefreshConfirmation = true
                    }
                
                if let composer = song.composer {
                    HStack {
                        Image(systemName: "music.note.list")
                            .foregroundColor(JazzTheme.brass)
                        Text(composer)
                            .font(.title3)
                            .foregroundColor(JazzTheme.smokeGray)
                    }
                }
                
                // Song Reference (if available)
                if let songRef = song.songReference {
                    HStack(alignment: .top, spacing: 8) {
                        Image(systemName: "book.closed.fill")
                            .foregroundColor(JazzTheme.brass)
                            .font(.subheadline)
                        Text(songRef)
                            .font(.subheadline)
                            .foregroundColor(JazzTheme.smokeGray)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    .padding(.top, 4)
                }
                
                if let structure = song.structure {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Structure")
                            .font(.headline)
                            .foregroundColor(JazzTheme.charcoal)
                        Text(structure)
                            .font(.body)
                            .foregroundColor(JazzTheme.smokeGray)
                    }
                    .padding()
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(JazzTheme.cardBackground)
                    .cornerRadius(10)
                }
                
                // External References Panel
                ExternalReferencesPanel(
                    wikipediaUrl: song.wikipediaUrl,
                    musicbrainzId: song.musicbrainzId,
                    externalReferences: song.externalReferences,
                    entityId: song.id,
                    entityName: song.title
                )
                
                // External References Section
                let externalRefs = song.externalReferencesList
                if !externalRefs.isEmpty {
                    VStack(alignment: .leading, spacing: 12) {
                        Text("References")
                            .font(.headline)
                            .foregroundColor(JazzTheme.charcoal)
                            .padding(.horizontal)
                        
                        ForEach(externalRefs) { ref in
                            ExternalReferenceRow(reference: ref)
                        }
                    }
                    .padding(.vertical, 8)
                    
                    Divider()
                }


            }
            .padding()
            
            Divider()
                .padding(.horizontal)
            
            // MARK: - RECORDINGS SECTION
                RecordingsSection(
                    recordings: song.recordings ?? [],
                    recordingSortOrder: $recordingSortOrder,
                    showingSortOptions: $showingSortOptions
                )
            // MARK: - TRANSCRIPTIONS SECTION
            TranscriptionsSection(transcriptions: transcriptions)
        }
        .padding(.bottom)
        }
    }
    
    // MARK: - Body (broken into smaller chunks to avoid type-checker timeout)
    
    var body: some View {
        contentView
            .onAppear(perform: loadInitialData)
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
            .navigationTitle(song?.title ?? "Song Detail")
            .navigationBarTitleDisplayMode(.large)
            .toolbarBackground(JazzTheme.burgundy, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                toolbarContent
            }
            .task {
                await loadSongData()
            }
            .gesture(swipeGesture)
            .sheet(isPresented: $showAddToRepertoireSheet) {
                repertoireSheet
            }
            .alert("Error", isPresented: $showErrorAlert) {
                Button("OK", role: .cancel) { }
            } message: {
                Text(alertMessage)
            }
            .alert("Queue Song for Research?", isPresented: $showRefreshConfirmation) {
                Button("Cancel", role: .cancel) { }
                Button("Refresh", role: .destructive) {
                    refreshSongData()
                }
            } message: {
                Text("This will queue \"\(song?.title ?? "this song")\" for background research to update its information from external sources.")
            }
            .toast($toast)
            .overlay(alignment: .bottom) {
                pageIndicatorView
            }
            .confirmationDialog("Sort Recordings", isPresented: $showingSortOptions, titleVisibility: .visible) {
                ForEach(RecordingSortOrder.allCases) { sortOrder in
                    Button(sortOrder.displayName) {
                        recordingSortOrder = sortOrder
                        // Reload song with new sort order
                        Task {
                            isLoading = true
                            if let updatedSong = await NetworkManager().fetchSongDetail(id: songId, sortBy: sortOrder) {
                                song = updatedSong
                            }
                            isLoading = false
                        }
                    }
                }
                Button("Cancel", role: .cancel) {}
            } message: {
                Text("Choose how to sort recordings")
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
    }
    
    private var loadingView: some View {
        VStack {
            Spacer()
            ProgressView("Loading...")
                .tint(JazzTheme.burgundy)
            Spacer()
        }
        .frame(maxWidth: .infinity, minHeight: 300)
    }
    
    private var notFoundView: some View {
        VStack {
            Spacer()
            Text("Song not found")
                .font(.title3)
                .foregroundColor(JazzTheme.smokeGray)
            Spacer()
        }
        .frame(maxWidth: .infinity, minHeight: 300)
        .background(JazzTheme.backgroundLight)
    }
    
    @ToolbarContentBuilder
    private var toolbarContent: some ToolbarContent {
        if repertoireManager.isShowingAllSongs && song != nil {
            ToolbarItem(placement: .navigationBarTrailing) {
                Button(action: {
                    showAddToRepertoireSheet = true
                }) {
                    Image(systemName: "plus.circle")
                        .foregroundColor(.white)
                }
                .disabled(isAddingToRepertoire)
            }
        }
    }
    
    // MARK: - Swipe Gesture with Visual Feedback
    
    private var swipeGesture: some Gesture {
        DragGesture(minimumDistance: 50)
            .updating($dragOffset) { value, state, _ in
                // Only track horizontal drags that don't start from the left edge
                // (to avoid conflict with iOS back gesture)
                let isHorizontalDrag = abs(value.translation.width) > abs(value.translation.height)
                let startedFromLeftEdge = value.startLocation.x < 50 // iOS back gesture zone
                
                if isHorizontalDrag && !startedFromLeftEdge {
                    state = value.translation.width
                }
            }
            .onEnded { value in
                // Ignore gestures that started from the left edge (system back gesture)
                let startedFromLeftEdge = value.startLocation.x < 50
                
                if !startedFromLeftEdge && abs(value.translation.width) > abs(value.translation.height) {
                    if value.translation.width < -50 && canNavigateNext {
                        withAnimation(.easeInOut(duration: 0.3)) {
                            navigateToNext()
                        }
                    } else if value.translation.width > 50 && canNavigatePrevious {
                        withAnimation(.easeInOut(duration: 0.3)) {
                            navigateToPrevious()
                        }
                    }
                }
            }
    }
    
    // MARK: - Navigation Arrow Indicator
    
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
    
    // MARK: - Data Loading
    
    private func loadInitialData() {
        // Empty - using .task instead for async loading
    }
    
    private func loadSongData() async {
        #if DEBUG
        if ProcessInfo.processInfo.environment["XCODE_RUNNING_FOR_PREVIEWS"] == "1" {
            let networkManager = NetworkManager()
            song = networkManager.fetchSongDetailSync(id: currentSongId)
            transcriptions = song?.transcriptions ?? []
            isLoading = false
            return
        }
        #endif
        
        let networkManager = NetworkManager()
        // OPTIMIZED: Single API call now includes transcriptions
        let fetchedSong = await networkManager.fetchSongDetail(id: currentSongId)
        await MainActor.run {
            song = fetchedSong
            transcriptions = fetchedSong?.transcriptions ?? []
            isLoading = false
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

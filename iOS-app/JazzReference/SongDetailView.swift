//
//  SongDetailView.swift
//  JazzReference
//
//  UPDATED: Added "Add to Repertoire" functionality
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
    
    // NEW: Repertoire management
    @EnvironmentObject var repertoireManager: RepertoireManager
    @State private var showAddToRepertoireSheet = false
    @State private var showSuccessAlert = false
    @State private var showErrorAlert = false
    @State private var alertMessage = ""
    @State private var isAddingToRepertoire = false
    
    // Song refresh management
    @State private var showRefreshConfirmation = false
    @State private var isRefreshing = false
    @State private var showRefreshSuccess = false
    
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
            let fetchedSong = await networkManager.fetchSongDetail(id: currentSongId)
            let fetchedTranscriptions = await networkManager.fetchSongTranscriptions(songId: currentSongId)
            await MainActor.run {
                song = fetchedSong
                transcriptions = fetchedTranscriptions
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
                    showRefreshSuccess = true
                } else {
                    showErrorAlert = true
                    alertMessage = "Failed to queue song for refresh. Please try again."
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
            }
            .padding()
            
            Divider()
                .padding(.horizontal)
            
            // MARK: - RECORDINGS SECTION
            RecordingsSection(recordings: song.recordings ?? [])
            
            // MARK: - TRANSCRIPTIONS SECTION
            TranscriptionsSection(transcriptions: transcriptions)
        }
        .padding(.bottom)
        }
    }
    
    var body: some View {
        ScrollView {
            if isLoading {
                VStack {
                    Spacer()
                    ProgressView("Loading...")
                        .tint(JazzTheme.burgundy)
                    Spacer()
                }
                .frame(maxWidth: .infinity, minHeight: 300)
            } else if let song = song {
                songContentView(for: song)
            } else {
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
        }
        .background(JazzTheme.backgroundLight)
        .navigationTitle(song?.title ?? "Song Detail")
        .navigationBarTitleDisplayMode(.large)
        .toolbarBackground(JazzTheme.burgundy, for: .navigationBar)
        .toolbarBackground(.visible, for: .navigationBar)
        .toolbarColorScheme(.dark, for: .navigationBar)
        .toolbar {
            // NEW: Add to Repertoire button (only when viewing all songs)
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
        .task {
            #if DEBUG
            if ProcessInfo.processInfo.environment["XCODE_RUNNING_FOR_PREVIEWS"] == "1" {
                let networkManager = NetworkManager()
                song = networkManager.fetchSongDetailSync(id: currentSongId)
                transcriptions = networkManager.fetchSongTranscriptionsSync(songId: currentSongId)
                isLoading = false
                return
            }
            #endif
            
            let networkManager = NetworkManager()
            song = await networkManager.fetchSongDetail(id: currentSongId)
            transcriptions = await networkManager.fetchSongTranscriptions(songId: currentSongId)
            isLoading = false
        }
        .gesture(
            DragGesture(minimumDistance: 50)
                .onEnded { value in
                    if abs(value.translation.width) > abs(value.translation.height) {
                        if value.translation.width < -50 && canNavigateNext {
                            // Swipe left - next song
                            withAnimation(.easeInOut(duration: 0.3)) {
                                navigateToNext()
                            }
                        } else if value.translation.width > 50 && canNavigatePrevious {
                            // Swipe right - previous song
                            withAnimation(.easeInOut(duration: 0.3)) {
                                navigateToPrevious()
                            }
                        }
                    }
                }
        )
        .sheet(isPresented: $showAddToRepertoireSheet) {
            AddToRepertoireSheet(
                songId: songId,
                songTitle: song?.title ?? "Unknown",
                repertoireManager: repertoireManager,
                isPresented: $showAddToRepertoireSheet,
                onSuccess: { message in
                    alertMessage = message
                    showSuccessAlert = true
                },
                onError: { message in
                    alertMessage = message
                    showErrorAlert = true
                }
            )
        }
        .alert("Success", isPresented: $showSuccessAlert) {
            Button("OK", role: .cancel) { }
        } message: {
            Text(alertMessage)
        }
        .alert("Error", isPresented: $showErrorAlert) {
            Button("OK", role: .cancel) { }
        } message: {
            Text(alertMessage)
        }
        .alert("Refresh Song Data?", isPresented: $showRefreshConfirmation) {
            Button("Cancel", role: .cancel) { }
            Button("Refresh", role: .destructive) {
                refreshSongData()
            }
        } message: {
            Text("This will queue \"\(song?.title ?? "this song")\" for background research to update its information from external sources.")
        }
        .alert("Song Queued", isPresented: $showRefreshSuccess) {
            Button("OK", role: .cancel) { }
        } message: {
            Text("The song has been queued for research. Data will be updated in the background.")
        }
        .overlay(alignment: .bottom) {
            // Navigation indicators
            if !allSongs.isEmpty && !isLoading {
                HStack(spacing: 20) {
                    Button(action: {
                        withAnimation(.easeInOut(duration: 0.3)) {
                            navigateToPrevious()
                        }
                    }) {
                        Image(systemName: "chevron.left.circle.fill")
                            .font(.system(size: 36))
                            .foregroundColor(canNavigatePrevious ? JazzTheme.burgundy : JazzTheme.smokeGray.opacity(0.3))
                    }
                    .disabled(!canNavigatePrevious)
                    
                    if let index = currentIndex {
                        Text("\(index + 1) of \(allSongs.count)")
                            .font(.caption)
                            .fontWeight(.medium)
                            .foregroundColor(JazzTheme.charcoal)
                    }
                    
                    Button(action: {
                        withAnimation(.easeInOut(duration: 0.3)) {
                            navigateToNext()
                        }
                    }) {
                        Image(systemName: "chevron.right.circle.fill")
                            .font(.system(size: 36))
                            .foregroundColor(canNavigateNext ? JazzTheme.burgundy : JazzTheme.smokeGray.opacity(0.3))
                    }
                    .disabled(!canNavigateNext)
                }
                .padding(.horizontal, 24)
                .padding(.vertical, 12)
                .background(.ultraThinMaterial)
                .cornerRadius(20)
                .padding(.bottom, 20)
            }
        }
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

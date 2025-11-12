//
//  SongDetailView.swift
//  JazzReference
//
//  UPDATED: Added "Add to Repertoire" functionality
//

import SwiftUI
import Combine

// MARK: - Recording Filter Enum
enum SongRecordingFilter: String, CaseIterable {
    case withSpotify = "With Spotify"
    case all = "All"
}

// MARK: - Instrument Family Enum
enum InstrumentFamily: String, CaseIterable, Hashable {
    case guitar = "Guitar"
    case saxophone = "Saxophone"
    case trumpet = "Trumpet"
    case trombone = "Trombone"
    case piano = "Piano"
    case organ = "Organ"
    case bass = "Bass"
    case drums = "Drums"
    case clarinet = "Clarinet"
    case flute = "Flute"
    case vibraphone = "Vibraphone"
    case vocals = "Vocals"
    
    // Map specific instruments to their family
    static func family(for instrument: String) -> InstrumentFamily? {
        let normalized = instrument.lowercased()
        
        if normalized.contains("guitar") { return .guitar }
        if normalized.contains("sax") { return .saxophone }
        if normalized.contains("trumpet") || normalized.contains("flugelhorn") { return .trumpet }
        if normalized.contains("trombone") { return .trombone }
        if normalized.contains("piano") && !normalized.contains("organ") { return .piano }
        if normalized.contains("organ") { return .organ }
        if normalized.contains("bass") && !normalized.contains("brass") { return .bass }
        if normalized.contains("drum") || normalized == "percussion" { return .drums }
        if normalized.contains("clarinet") { return .clarinet }
        if normalized.contains("flute") { return .flute }
        if normalized.contains("vibraphone") || normalized.contains("vibes") { return .vibraphone }
        if normalized.contains("vocal") || normalized.contains("voice") || normalized.contains("singer") { return .vocals }
        
        return nil
    }
}

// MARK: - Song Detail View
struct SongDetailView: View {
    let songId: String
    let allSongs: [Song]
    let repertoireId: String
    
    @State private var currentSongId: String
    @State private var song: Song?
    @State private var isLoading = true
    @State private var selectedFilter: SongRecordingFilter = .withSpotify
    @State private var transcriptions: [SoloTranscription] = []
    
    // Filter states
    @State private var selectedInstrument: InstrumentFamily? = nil
    @State private var isFiltersExpanded: Bool = false
    
    // Section expansion states
    @State private var isRecordingsSectionExpanded: Bool = true
    @State private var isTranscriptionsSectionExpanded: Bool = true
    
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
    
    // Extract unique instrument families from recordings
    var availableInstruments: [InstrumentFamily] {
        guard let recordings = song?.recordings else { return [] }
        
        var families = Set<InstrumentFamily>()
        for recording in recordings {
            if let performers = recording.performers {
                for performer in performers {
                    if let instrument = performer.instrument,
                       let family = InstrumentFamily.family(for: instrument) {
                        families.insert(family)
                    }
                }
            }
        }
        
        return families.sorted { $0.rawValue < $1.rawValue }
    }
    
    // Apply filters in order: first instrument family, then Spotify
    var filteredRecordings: [Recording] {
        guard let recordings = song?.recordings else { return [] }
        
        // First, apply instrument family filter if selected
        var result = recordings
        if let family = selectedInstrument {
            result = result.filter { recording in
                guard let performers = recording.performers else { return false }
                return performers.contains { performer in
                    guard let instrument = performer.instrument else { return false }
                    return InstrumentFamily.family(for: instrument) == family
                }
            }
        }
        
        // Then, apply Spotify filter
        switch selectedFilter {
        case .withSpotify:
            result = result.filter { $0.spotifyUrl != nil }
        case .all:
            break
        }
        
        return result
    }
    
    // Group recordings by leader, sorted by leader's last name
    var groupedRecordings: [(leader: String, recordings: [Recording])] {
        let recordings = filteredRecordings
        
        // Group by leader name
        var groups: [String: [Recording]] = [:]
        for recording in recordings {
            let leaderName = recording.performers?.first { $0.role == "leader" }?.name ?? "Unknown"
            groups[leaderName, default: []].append(recording)
        }
        
        // Sort by last name
        return groups.map { (leader: $0.key, recordings: $0.value) }
            .sorted { (group1, group2) in
                let lastName1 = group1.leader.components(separatedBy: " ").last ?? group1.leader
                let lastName2 = group2.leader.components(separatedBy: " ").last ?? group2.leader
                return lastName1.localizedCaseInsensitiveCompare(lastName2) == .orderedAscending
            }
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
            
            // MARK: - RECORDINGS SECTION (Collapsible)
            VStack(alignment: .leading, spacing: 0) {
                DisclosureGroup(
                    isExpanded: $isRecordingsSectionExpanded,
                    content: {
                        VStack(alignment: .leading, spacing: 0) {
            
            // MARK: - FILTERS SECTION
            VStack(alignment: .leading, spacing: 0) {
                DisclosureGroup(
                    isExpanded: $isFiltersExpanded,
                    content: {
                        VStack(alignment: .leading, spacing: 16) {
                            // Spotify Filter
                            VStack(alignment: .leading, spacing: 8) {
                                Text("Recording Type")
                                    .font(.subheadline)
                                    .fontWeight(.medium)
                                    .foregroundColor(JazzTheme.smokeGray)
                                
                                Picker("Recording Type", selection: $selectedFilter) {
                                    ForEach(SongRecordingFilter.allCases, id: \.self) { filter in
                                        Text(filter.rawValue).tag(filter)
                                    }
                                }
                                .pickerStyle(SegmentedPickerStyle())
                            }
                            
                            // Instrument Filter
                            if !availableInstruments.isEmpty {
                                VStack(alignment: .leading, spacing: 8) {
                                    HStack {
                                        Text("Instrument")
                                            .font(.subheadline)
                                            .fontWeight(.medium)
                                            .foregroundColor(JazzTheme.smokeGray)
                                        
                                        Spacer()
                                        
                                        if selectedInstrument != nil {
                                            Button(action: {
                                                selectedInstrument = nil
                                            }) {
                                                Text("Clear")
                                                    .font(.caption)
                                                    .foregroundColor(JazzTheme.burgundy)
                                            }
                                        }
                                    }
                                    
                                    ScrollView(.horizontal, showsIndicators: false) {
                                        HStack(spacing: 8) {
                                            ForEach(availableInstruments, id: \.self) { family in
                                                Button(action: {
                                                    if selectedInstrument == family {
                                                        selectedInstrument = nil
                                                    } else {
                                                        selectedInstrument = family
                                                    }
                                                }) {
                                                    Text(family.rawValue)
                                                        .font(.subheadline)
                                                        .foregroundColor(
                                                            selectedInstrument == family
                                                                ? .white
                                                                : JazzTheme.charcoal
                                                        )
                                                        .padding(.horizontal, 12)
                                                        .padding(.vertical, 6)
                                                        .background(
                                                            selectedInstrument == family
                                                                ? JazzTheme.brass
                                                                : JazzTheme.cardBackground
                                                        )
                                                        .cornerRadius(16)
                                                        .overlay(
                                                            RoundedRectangle(cornerRadius: 16)
                                                                .stroke(
                                                                    selectedInstrument == family
                                                                        ? Color.clear
                                                                        : JazzTheme.smokeGray.opacity(0.3),
                                                                    lineWidth: 1
                                                                )
                                                        )
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                        .padding()
                    },
                    label: {
                        HStack {
                            Image(systemName: "line.3.horizontal.decrease.circle")
                                .foregroundColor(JazzTheme.brass)
                            Text("Filters")
                                .font(.headline)
                                .foregroundColor(JazzTheme.charcoal)
                            
                            Spacer()
                            
                            // Active filter indicators
                            HStack(spacing: 6) {
                                if selectedFilter == .withSpotify {
                                    Text("Spotify")
                                        .font(.caption)
                                        .foregroundColor(JazzTheme.brass)
                                        .padding(.horizontal, 6)
                                        .padding(.vertical, 2)
                                        .background(JazzTheme.brass.opacity(0.2))
                                        .cornerRadius(4)
                                }
                                
                                if let family = selectedInstrument {
                                    Text(family.rawValue)
                                        .font(.caption)
                                        .foregroundColor(JazzTheme.brass)
                                        .padding(.horizontal, 6)
                                        .padding(.vertical, 2)
                                        .background(JazzTheme.brass.opacity(0.2))
                                        .cornerRadius(4)
                                }
                            }
                        }
                        .padding(.vertical, 8)
                    }
                )
                .tint(JazzTheme.brass)
                .padding(.horizontal)
                .padding(.vertical, 8)
            }
            .background(JazzTheme.cardBackground)
            .cornerRadius(10)
            .padding(.horizontal)
            .padding(.top, 8)
            
            // Recording count
            HStack {
                Text("\(filteredRecordings.count) Recording\(filteredRecordings.count == 1 ? "" : "s")")
                    .font(.subheadline)
                    .foregroundColor(JazzTheme.smokeGray)
                Spacer()
            }
            .padding(.horizontal)
            .padding(.top, 12)
            
            // Recordings List
            VStack(alignment: .leading, spacing: 12) {
                if !filteredRecordings.isEmpty {
                    ForEach(groupedRecordings, id: \.leader) { group in
                        VStack(alignment: .leading, spacing: 8) {
                            Text("\(group.leader) (\(group.recordings.count))")
                                .font(.headline)
                                .foregroundColor(JazzTheme.burgundy)
                                .padding(.horizontal)
                                .padding(.top, 8)
                            
                            ScrollView(.horizontal, showsIndicators: false) {
                                HStack(spacing: 16) {
                                    ForEach(group.recordings) { recording in
                                        NavigationLink(destination: RecordingDetailView(recordingId: recording.id)) {
                                            RecordingRowView(recording: recording)
                                        }
                                        .buttonStyle(.plain)
                                    }
                                }
                                .padding(.horizontal)
                            }
                        }
                    }
                } else {
                    VStack(spacing: 12) {
                        Image(systemName: "music.note.slash")
                            .font(.system(size: 48))
                            .foregroundColor(JazzTheme.smokeGray.opacity(0.5))
                        Text("No recordings match the current filters")
                            .font(.subheadline)
                            .foregroundColor(JazzTheme.smokeGray)
                            .multilineTextAlignment(.center)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 40)
                }
            }
            .padding(.top)
                        }
                        .padding(.top, 8)
                    },
                    label: {
                        HStack {
                            Image(systemName: "music.note.list")
                                .foregroundColor(JazzTheme.burgundy)
                            Text("Recordings")
                                .font(.title2)
                                .bold()
                                .foregroundColor(JazzTheme.charcoal)
                            
                            Spacer()
                            
                            Text("\(filteredRecordings.count)")
                                .font(.subheadline)
                                .foregroundColor(JazzTheme.smokeGray)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 4)
                                .background(JazzTheme.burgundy.opacity(0.1))
                                .cornerRadius(6)
                        }
                        .padding(.horizontal)
                        .padding(.vertical, 12)
                    }
                )
                .tint(JazzTheme.burgundy)
            }
            .background(JazzTheme.backgroundLight)
            
            // MARK: - TRANSCRIPTIONS SECTION (Collapsible)
            if !transcriptions.isEmpty {
                Divider()
                    .padding(.horizontal)
                    .padding(.top, 16)
                
                VStack(alignment: .leading, spacing: 0) {
                    DisclosureGroup(
                        isExpanded: $isTranscriptionsSectionExpanded,
                        content: {
                            VStack(alignment: .leading, spacing: 12) {
                                ForEach(transcriptions) { transcription in
                                    TranscriptionRowView(transcription: transcription)
                                }
                            }
                            .padding(.top, 12)
                        },
                        label: {
                            HStack {
                                Image(systemName: "music.quarternote.3")
                                    .foregroundColor(JazzTheme.teal)
                                Text("Solo Transcriptions")
                                    .font(.title2)
                                    .bold()
                                    .foregroundColor(JazzTheme.charcoal)
                                
                                Spacer()
                                
                                Text("\(transcriptions.count)")
                                    .font(.subheadline)
                                    .foregroundColor(JazzTheme.smokeGray)
                                    .padding(.horizontal, 8)
                                    .padding(.vertical, 4)
                                    .background(JazzTheme.teal.opacity(0.1))
                                    .cornerRadius(6)
                            }
                            .padding(.horizontal)
                            .padding(.vertical, 12)
                        }
                    )
                    .tint(JazzTheme.teal)
                }
                .background(JazzTheme.backgroundLight)
            }
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

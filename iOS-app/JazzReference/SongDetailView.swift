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
    
    // Instrument filter states
    @State private var selectedInstrument: InstrumentFamily? = nil
    @State private var isInstrumentFilterExpanded: Bool = false
    
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
            await MainActor.run {
                song = fetchedSong
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
                    // Styled Header with Jazz Theme
                    HStack {
                        Image(systemName: "music.note")
                            .font(.title2)
                            .foregroundColor(JazzTheme.cream)
                        Text("SONG")
                            .font(.headline)
                            .fontWeight(.semibold)
                            .foregroundColor(JazzTheme.cream)
                        Spacer()
                    }
                    .padding()
                    .background(JazzTheme.burgundyGradient)
                    
                    VStack(alignment: .leading, spacing: 20) {
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
                            externalReferences: song.externalReferences,
                            musicbrainzId: song.musicbrainzId,
                            entityId: song.id,
                            entityName: song.title
                        )
                    }
                    .padding()
                    
                    Divider()
                        .padding(.horizontal)
                    
                    // MARK: - INSTRUMENT FILTER
                    // Collapsible Instrument Filter (between Learn More and Spotify filter)
                    if !availableInstruments.isEmpty {
                        VStack(alignment: .leading, spacing: 0) {
                            DisclosureGroup(
                                isExpanded: $isInstrumentFilterExpanded,
                                content: {
                                    VStack(alignment: .leading, spacing: 12) {
                                        // Clear filter button if instrument is selected
                                        if selectedInstrument != nil {
                                            Button(action: {
                                                selectedInstrument = nil
                                            }) {
                                                HStack {
                                                    Image(systemName: "xmark.circle.fill")
                                                        .foregroundColor(JazzTheme.burgundy)
                                                    Text("Show All Instruments")
                                                        .foregroundColor(JazzTheme.burgundy)
                                                }
                                                .padding(.vertical, 8)
                                            }
                                        }
                                        
                                        // Instrument buttons
                                        ForEach(availableInstruments, id: \.self) { family in
                                            Button(action: {
                                                if selectedInstrument == family {
                                                    selectedInstrument = nil
                                                } else {
                                                    selectedInstrument = family
                                                }
                                            }) {
                                                HStack {
                                                    Image(systemName: selectedInstrument == family ? "checkmark.circle.fill" : "circle")
                                                        .foregroundColor(selectedInstrument == family ? JazzTheme.brass : JazzTheme.smokeGray)
                                                    Text(family.rawValue)
                                                        .foregroundColor(JazzTheme.charcoal)
                                                    Spacer()
                                                }
                                                .padding(.vertical, 8)
                                                .padding(.horizontal, 12)
                                                .background(
                                                    selectedInstrument == family
                                                        ? JazzTheme.brass.opacity(0.1)
                                                        : Color.clear
                                                )
                                                .cornerRadius(8)
                                            }
                                        }
                                    }
                                    .padding(.top, 8)
                                },
                                label: {
                                    HStack {
                                        Image(systemName: "guitars.fill")
                                            .foregroundColor(JazzTheme.brass)
                                        Text("Filter by Instrument")
                                            .font(.headline)
                                            .foregroundColor(JazzTheme.charcoal)
                                        
                                        if let family = selectedInstrument {
                                            Spacer()
                                            Text(family.rawValue)
                                                .font(.subheadline)
                                                .foregroundColor(JazzTheme.brass)
                                                .padding(.horizontal, 8)
                                                .padding(.vertical, 4)
                                                .background(JazzTheme.brass.opacity(0.2))
                                                .cornerRadius(6)
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
                        
                        Divider()
                            .padding(.horizontal)
                    }
                    
                    // MARK: - SPOTIFY FILTER
                    // Recording Filter Picker
                    VStack(spacing: 0) {
                        Picker("Filter", selection: $selectedFilter) {
                            ForEach(SongRecordingFilter.allCases, id: \.self) { filter in
                                Text(filter.rawValue).tag(filter)
                            }
                        }
                        .pickerStyle(SegmentedPickerStyle())
                        .padding(.horizontal)
                        
                        // Recording count
                        HStack {
                            Text("\(filteredRecordings.count) Recording\(filteredRecordings.count == 1 ? "" : "s")")
                                .font(.subheadline)
                                .foregroundColor(JazzTheme.smokeGray)
                            Spacer()
                        }
                        .padding(.horizontal)
                        .padding(.top, 8)
                    }
                    
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
                isLoading = false
                return
            }
            #endif
            
            let networkManager = NetworkManager()
            song = await networkManager.fetchSongDetail(id: currentSongId)
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

// MARK: - Add to Repertoire Sheet (FIXED)

struct AddToRepertoireSheet: View {
    let songId: String
    let songTitle: String
    @ObservedObject var repertoireManager: RepertoireManager
    @Binding var isPresented: Bool
    let onSuccess: (String) -> Void
    let onError: (String) -> Void
    
    @State private var isAdding = false
    @State private var isLoadingRepertoires = false
    @State private var networkManager = NetworkManager()
    
    var body: some View {
        NavigationStack {
            Group {
                if isLoadingRepertoires {
                    // Loading state
                    VStack(spacing: 16) {
                        ProgressView()
                            .tint(JazzTheme.burgundy)
                        Text("Loading repertoires...")
                            .foregroundColor(JazzTheme.smokeGray)
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else if repertoireManager.addableRepertoires.isEmpty {
                    // Empty state - no repertoires exist
                    VStack(spacing: 20) {
                        Image(systemName: "music.note.list")
                            .font(.system(size: 60))
                            .foregroundColor(JazzTheme.smokeGray.opacity(0.5))
                        
                        Text("No Repertoires Yet")
                            .font(.title2)
                            .fontWeight(.semibold)
                            .foregroundColor(JazzTheme.charcoal)
                        
                        Text("Create a repertoire first to start organizing your songs.")
                            .font(.subheadline)
                            .foregroundColor(JazzTheme.smokeGray)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal, 40)
                        
                        // TODO: Add "Create Repertoire" button when that feature is implemented
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .background(JazzTheme.backgroundLight)
                } else {
                    // Normal state - show repertoires
                    repertoireList
                }
            }
            .navigationTitle("Add \"\(songTitle)\"")
            .navigationBarTitleDisplayMode(.inline)
            .toolbarBackground(JazzTheme.burgundy, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Cancel") {
                        isPresented = false
                    }
                    .foregroundColor(.white)
                    .disabled(isAdding)
                }
            }
            .overlay {
                if isAdding {
                    ZStack {
                        Color.black.opacity(0.3)
                            .ignoresSafeArea()
                        
                        VStack(spacing: 16) {
                            ProgressView()
                                .tint(.white)
                                .scaleEffect(1.5)
                            Text("Adding to repertoire...")
                                .foregroundColor(.white)
                                .font(.headline)
                        }
                        .padding(30)
                        .background(JazzTheme.charcoal)
                        .cornerRadius(16)
                    }
                }
            }
            .task {
                // Ensure repertoires are loaded when sheet appears
                if repertoireManager.repertoires.isEmpty ||
                   repertoireManager.addableRepertoires.isEmpty {
                    isLoadingRepertoires = true
                    await repertoireManager.loadRepertoires()
                    isLoadingRepertoires = false
                    
                    // Debug logging
                    print("🎵 Loaded \(repertoireManager.repertoires.count) total repertoires")
                    print("🎵 Addable repertoires: \(repertoireManager.addableRepertoires.count)")
                    for rep in repertoireManager.addableRepertoires {
                        print("   - \(rep.name) (ID: \(rep.id))")
                    }
                }
            }
        }
    }
    
    private var repertoireList: some View {
        List {
            // Quick add to last used (if available)
            if let lastUsed = repertoireManager.lastUsedRepertoire {
                Section {
                    Button(action: {
                        addToRepertoire(lastUsed)
                    }) {
                        HStack {
                            VStack(alignment: .leading, spacing: 4) {
                                Text("Add to \(lastUsed.name)")
                                    .font(.headline)
                                    .foregroundColor(JazzTheme.charcoal)
                                Text("Last used")
                                    .font(.caption)
                                    .foregroundColor(JazzTheme.smokeGray)
                            }
                            Spacer()
                            Image(systemName: "arrow.right.circle.fill")
                                .foregroundColor(JazzTheme.amber)
                                .font(.title2)
                        }
                    }
                    .disabled(isAdding)
                    .listRowBackground(JazzTheme.amber.opacity(0.1))
                } header: {
                    Text("Quick Add")
                }
            }
            
            // All available repertoires
            Section {
                ForEach(repertoireManager.addableRepertoires) { repertoire in
                    Button(action: {
                        addToRepertoire(repertoire)
                    }) {
                        HStack {
                            VStack(alignment: .leading, spacing: 4) {
                                Text(repertoire.name)
                                    .font(.headline)
                                    .foregroundColor(JazzTheme.charcoal)
                                
                                if let description = repertoire.description {
                                    Text(description)
                                        .font(.subheadline)
                                        .foregroundColor(JazzTheme.smokeGray)
                                        .lineLimit(2)
                                }
                                
                                Text("\(repertoire.songCount) songs")
                                    .font(.caption)
                                    .foregroundColor(JazzTheme.burgundy)
                            }
                            Spacer()
                        }
                    }
                    .disabled(isAdding)
                    .listRowBackground(JazzTheme.cardBackground)
                }
            } header: {
                Text("All Repertoires")
            }
        }
        .listStyle(.insetGrouped)
        .scrollContentBackground(.hidden)
        .background(JazzTheme.backgroundLight)
    }
    
    private func addToRepertoire(_ repertoire: Repertoire) {
        isAdding = true
        
        Task {
            let result = await networkManager.addSongToRepertoire(
                songId: songId,
                repertoireId: repertoire.id
            )
            
            await MainActor.run {
                isAdding = false
                
                switch result {
                case .success(let message):
                    // Update last used repertoire
                    repertoireManager.setLastUsedRepertoire(repertoire)
                    
                    isPresented = false
                    onSuccess("Added \"\(songTitle)\" to \(repertoire.name)")
                    
                case .failure(let error):
                    isPresented = false
                    let errorMessage = (error as NSError).localizedDescription
                    onError(errorMessage)
                }
            }
        }
    }
}

//
//  AddToRepertoireSheet.swift
//  JazzReference
//
//  Created by Dave Rodger on 11/3/25.
//


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

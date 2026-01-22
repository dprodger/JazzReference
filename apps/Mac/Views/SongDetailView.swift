//
//  SongDetailView.swift
//  JazzReferenceMac
//
//  macOS-specific song detail view
//

import SwiftUI

// MARK: - Recording Filter Enum
enum SongRecordingFilter: String, CaseIterable, Identifiable {
    case all = "All"
    case playable = "Playable"
    case withSpotify = "Spotify"
    case withAppleMusic = "Apple Music"

    var id: String { rawValue }

    var displayName: String { rawValue }

    var icon: String {
        switch self {
        case .all: return "music.note.list"
        case .playable: return "play.circle"
        case .withSpotify: return "play.circle.fill"
        case .withAppleMusic: return "play.circle.fill"
        }
    }

    var iconColor: Color {
        switch self {
        case .all: return JazzTheme.smokeGray
        case .playable: return JazzTheme.burgundy
        case .withSpotify: return .green
        case .withAppleMusic: return .pink
        }
    }
}

// MARK: - Instrument Family Enum
enum InstrumentFamily: String, CaseIterable, Hashable, Identifiable {
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

    var id: String { rawValue }

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

    var icon: String {
        switch self {
        case .guitar: return "guitars"
        case .saxophone: return "music.note"
        case .trumpet: return "music.note"
        case .trombone: return "music.note"
        case .piano: return "pianokeys"
        case .organ: return "pianokeys"
        case .bass: return "music.note"
        case .drums: return "drum"
        case .clarinet: return "music.note"
        case .flute: return "music.note"
        case .vibraphone: return "music.note"
        case .vocals: return "mic"
        }
    }
}

// MARK: - Vocal/Instrumental Filter
enum VocalFilter: String, CaseIterable, Identifiable {
    case all = "All"
    case instrumental = "Instrumental"
    case vocal = "Vocal"

    var id: String { rawValue }

    var icon: String {
        switch self {
        case .all: return "music.note.list"
        case .instrumental: return "pianokeys"
        case .vocal: return "mic"
        }
    }

    var iconColor: Color {
        switch self {
        case .all: return JazzTheme.smokeGray
        case .instrumental: return JazzTheme.brass
        case .vocal: return JazzTheme.burgundy
        }
    }
}

struct SongDetailView: View {
    let songId: String
    @State private var song: Song?
    @State private var isLoading = true
    @State private var isRecordingsLoading = true
    @State private var sortOrder: RecordingSortOrder = .year
    @State private var selectedRecordingId: String?
    @State private var selectedFilter: SongRecordingFilter = .playable
    @State private var selectedVocalFilter: VocalFilter = .all
    @State private var selectedInstrument: InstrumentFamily? = nil
    @State private var transcriptions: [SoloTranscription] = []
    @State private var backingTracks: [Video] = []
    @State private var isSummaryInfoExpanded = false
    @State private var showAddToRepertoire = false
    @State private var successMessage: String?
    @State private var errorMessage: String?
    @EnvironmentObject var repertoireManager: RepertoireManager
    @EnvironmentObject var authManager: AuthenticationManager

    @StateObject private var networkManager = NetworkManager()

    var body: some View {
        ScrollView {
            if isLoading {
                ThemedProgressView(message: "Loading...")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .padding(.top, 100)
            } else if let song = song {
                VStack(alignment: .leading, spacing: 16) {
                    // Header
                    songHeader(song)

                    // Summary Information (collapsible)
                    if hasSummaryContent(for: song) {
                        summaryInfoSection(song)
                    }

                    // Featured Recordings carousel
                    if let featured = song.featuredRecordings, !featured.isEmpty {
                        featuredRecordingsSection(featured)
                    }

                    Divider()

                    // Recordings - show section while loading or when we have recordings
                    if isRecordingsLoading || (song.recordings != nil && !song.recordings!.isEmpty) {
                        recordingsSection(song.recordings ?? [])
                    }

                    // Transcriptions
                    if !transcriptions.isEmpty {
                        transcriptionsSection
                    }

                    // Backing Tracks
                    if !backingTracks.isEmpty {
                        backingTracksSection
                    }
                }
                .padding()
            } else {
                Text("Song not found")
                    .foregroundColor(.secondary)
                    .padding(.top, 100)
            }
        }
        .background(JazzTheme.backgroundLight)
        .sheet(isPresented: $showAddToRepertoire) {
            if let song = song {
                MacAddToRepertoireSheet(
                    songId: songId,
                    songTitle: song.title,
                    repertoireManager: repertoireManager,
                    onSuccess: { message in
                        successMessage = message
                        // Auto-dismiss success message after 3 seconds
                        Task {
                            try? await Task.sleep(nanoseconds: 3_000_000_000)
                            await MainActor.run {
                                successMessage = nil
                            }
                        }
                    },
                    onError: { message in
                        errorMessage = message
                        // Auto-dismiss error message after 5 seconds
                        Task {
                            try? await Task.sleep(nanoseconds: 5_000_000_000)
                            await MainActor.run {
                                errorMessage = nil
                            }
                        }
                    }
                )
            }
        }
        .task(id: songId) {
            await loadSong()
        }
        .onChange(of: sortOrder) { _, _ in
            Task {
                await reloadRecordings()
            }
        }
    }

    // MARK: - View Components

    @ViewBuilder
    private func songHeader(_ song: Song) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            // Title row with Add to Repertoire button
            HStack(alignment: .firstTextBaseline) {
                // Title with composed year
                HStack(alignment: .firstTextBaseline, spacing: 8) {
                    Text(song.title)
                        .font(JazzTheme.largeTitle())
                        .foregroundColor(JazzTheme.charcoal)
                    if let year = song.composedYear {
                        Text("(\(String(year)))")
                            .font(JazzTheme.title2())
                            .foregroundColor(JazzTheme.smokeGray)
                    }
                }

                Spacer()

                // Add to Repertoire button
                Button(action: { showAddToRepertoire = true }) {
                    Label("Add to Repertoire", systemImage: "plus.circle")
                        .padding(.vertical, 4)
                }
                .buttonStyle(.borderedProminent)
                .tint(JazzTheme.burgundy)
                .help("Add this song to a repertoire")
            }

            // Composer with icon
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

            // Success/Error messages
            if let message = successMessage {
                HStack {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(.green)
                    Text(message)
                        .foregroundColor(.green)
                }
                .font(JazzTheme.subheadline())
                .padding(.vertical, 4)
            }

            if let message = errorMessage {
                HStack {
                    Image(systemName: "exclamationmark.circle.fill")
                        .foregroundColor(.red)
                    Text(message)
                        .foregroundColor(.red)
                }
                .font(JazzTheme.subheadline())
                .padding(.vertical, 4)
            }
        }
    }

    // MARK: - Summary Information Helpers

    private func hasSummaryContent(for song: Song) -> Bool {
        let hasStructure = song.structure != nil
        let hasComposedKey = song.composedKey != nil
        return hasStructure || hasComposedKey || hasExternalLinks(for: song)
    }

    private func hasExternalLinks(for song: Song) -> Bool {
        let hasWikipedia = song.wikipediaUrl != nil
        let hasMusicbrainz = song.musicbrainzId != nil
        let hasJazzStandards = song.externalReferences?["jazzstandards"] != nil
        return hasWikipedia || hasMusicbrainz || hasJazzStandards
    }

    @ViewBuilder
    private func externalLinkRow(icon: String, label: String, color: Color, url: URL) -> some View {
        Link(destination: url) {
            HStack {
                Image(systemName: icon)
                    .foregroundColor(color)
                    .frame(width: 24)
                Text(label)
                    .font(JazzTheme.body())
                    .foregroundColor(JazzTheme.charcoal)
                Spacer()
                Image(systemName: "arrow.up.right.square")
                    .foregroundColor(JazzTheme.smokeGray)
                    .font(JazzTheme.caption())
            }
            .padding(.vertical, 6)
        }
        .buttonStyle(.plain)
    }

    @ViewBuilder
    private func compactExternalLink(icon: String, label: String, color: Color, url: URL) -> some View {
        Link(destination: url) {
            HStack(spacing: 6) {
                Image(systemName: icon)
                    .foregroundColor(color)
                Text(label)
                    .font(JazzTheme.subheadline())
                    .foregroundColor(JazzTheme.charcoal)
                Image(systemName: "arrow.up.right")
                    .font(JazzTheme.caption2())
                    .foregroundColor(JazzTheme.smokeGray)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 8)
            .background(JazzTheme.cardBackground)
            .cornerRadius(8)
        }
        .buttonStyle(.plain)
    }

    @ViewBuilder
    private func summaryInfoSection(_ song: Song) -> some View {
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

                    // External References (Learn More)
                    if hasExternalLinks(for: song) {
                        VStack(alignment: .leading, spacing: 12) {
                            Text("Learn More")
                                .font(JazzTheme.headline())
                                .foregroundColor(JazzTheme.charcoal)

                            HStack(spacing: 12) {
                                // Wikipedia
                                if let wikipediaUrl = song.wikipediaUrl, let url = URL(string: wikipediaUrl) {
                                    compactExternalLink(icon: "book.fill", label: "Wikipedia", color: JazzTheme.teal, url: url)
                                }

                                // Jazz Standards
                                if let jazzStandardsUrl = song.externalReferences?["jazzstandards"], let url = URL(string: jazzStandardsUrl) {
                                    compactExternalLink(icon: "music.note.list", label: "JazzStandards.com", color: JazzTheme.brass, url: url)
                                }

                                // MusicBrainz
                                if let musicbrainzId = song.musicbrainzId, let url = URL(string: "https://musicbrainz.org/work/\(musicbrainzId)") {
                                    compactExternalLink(icon: "waveform.circle.fill", label: "MusicBrainz", color: JazzTheme.charcoal, url: url)
                                }
                            }
                        }
                        .padding()
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(Color.white)
                        .cornerRadius(8)
                    }
                }
                .padding()
                .background(JazzTheme.cardBackground)
            }
        }
        .cornerRadius(10)
    }

    // MARK: - Available Instruments
    private func availableInstruments(_ recordings: [Recording]) -> [InstrumentFamily] {
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

    // MARK: - Filtered Recordings
    private func filteredRecordings(_ recordings: [Recording]) -> [Recording] {
        var result = recordings

        // First, apply instrument family filter if selected
        if let family = selectedInstrument {
            result = result.filter { recording in
                guard let performers = recording.performers else { return false }
                return performers.contains { performer in
                    guard let instrument = performer.instrument else { return false }
                    return InstrumentFamily.family(for: instrument) == family
                }
            }
        }

        // Then, apply streaming service filter
        switch selectedFilter {
        case .all:
            break
        case .playable:
            result = result.filter { $0.isPlayable }
        case .withSpotify:
            result = result.filter { $0.hasSpotifyAvailable }
        case .withAppleMusic:
            result = result.filter { $0.hasAppleMusicAvailable }
        }

        // Apply vocal/instrumental filter
        switch selectedVocalFilter {
        case .all:
            break
        case .instrumental:
            result = result.filter { recording in
                recording.communityData?.consensus.isInstrumental == true
            }
        case .vocal:
            result = result.filter { recording in
                recording.communityData?.consensus.isInstrumental == false
            }
        }

        return result
    }

    // MARK: - Grouped Recordings
    private func groupedRecordings(_ recordings: [Recording]) -> [(groupKey: String, recordings: [Recording])] {
        let filtered = filteredRecordings(recordings)
        switch sortOrder {
        case .year:
            return groupByDecade(filtered)
        case .name:
            return groupByArtistWithConsolidation(filtered)
        }
    }

    private func groupByDecade(_ recordings: [Recording]) -> [(groupKey: String, recordings: [Recording])] {
        var decadeOrder: [String] = []
        var decades: [String: [Recording]] = [:]

        for recording in recordings {
            let decadeKey: String
            if let year = recording.recordingYear {
                let decade = (year / 10) * 10
                decadeKey = "\(decade)s"
            } else {
                decadeKey = "Unknown Year"
            }

            if decades[decadeKey] == nil {
                decadeOrder.append(decadeKey)
            }
            decades[decadeKey, default: []].append(recording)
        }

        return decadeOrder.compactMap { key in
            guard let recs = decades[key] else { return nil }
            return (groupKey: key, recordings: recs)
        }
    }

    private func groupByArtistWithConsolidation(_ recordings: [Recording]) -> [(groupKey: String, recordings: [Recording])] {
        // First pass: count recordings per artist
        var artistCounts: [String: Int] = [:]
        for recording in recordings {
            let artist = recording.performers?.first { $0.role == "leader" }?.name ?? "Unknown"
            artistCounts[artist, default: 0] += 1
        }

        // Second pass: separate featured artists from singles
        var featuredOrder: [String] = []
        var featuredGroups: [String: [Recording]] = [:]
        var moreRecordings: [Recording] = []

        for recording in recordings {
            let artist = recording.performers?.first { $0.role == "leader" }?.name ?? "Unknown"

            if artistCounts[artist, default: 0] >= 2 {
                if featuredGroups[artist] == nil {
                    featuredOrder.append(artist)
                }
                featuredGroups[artist, default: []].append(recording)
            } else {
                moreRecordings.append(recording)
            }
        }

        // Build result
        var result: [(groupKey: String, recordings: [Recording])] = []

        for artist in featuredOrder {
            if let recs = featuredGroups[artist] {
                result.append((groupKey: artist, recordings: recs))
            }
        }

        if !moreRecordings.isEmpty {
            let sortedMore = moreRecordings.sorted { rec1, rec2 in
                let leader1 = rec1.performers?.first { $0.role == "leader" }
                let leader2 = rec2.performers?.first { $0.role == "leader" }
                let sortKey1 = leader1?.sortName ?? leader1?.name ?? "Unknown"
                let sortKey2 = leader2?.sortName ?? leader2?.name ?? "Unknown"
                return sortKey1.localizedCaseInsensitiveCompare(sortKey2) == .orderedAscending
            }
            result.append((groupKey: "More Recordings", recordings: sortedMore))
        }

        return result
    }

    @ViewBuilder
    private func recordingsSection(_ recordings: [Recording]) -> some View {
        let filtered = filteredRecordings(recordings)
        let grouped = groupedRecordings(recordings)

        VStack(alignment: .leading, spacing: 12) {
            // Header with count, filter, and sort
            HStack {
                Image(systemName: "music.note.list")
                    .foregroundColor(JazzTheme.burgundy)
                Text("Recordings")
                    .font(JazzTheme.title2())
                    .foregroundColor(JazzTheme.charcoal)

                Text("(\(filtered.count))")
                    .font(JazzTheme.subheadline())
                    .foregroundColor(JazzTheme.smokeGray)

                Spacer()

                // Filter menu
                Menu {
                    ForEach(SongRecordingFilter.allCases) { filter in
                        Button(action: { selectedFilter = filter }) {
                            HStack {
                                Image(systemName: filter.icon)
                                    .foregroundColor(filter.iconColor)
                                Text(filter.displayName)
                                if selectedFilter == filter {
                                    Spacer()
                                    Image(systemName: "checkmark")
                                }
                            }
                        }
                    }
                } label: {
                    HStack(spacing: 4) {
                        Image(systemName: selectedFilter.icon)
                            .foregroundColor(selectedFilter == .all ? JazzTheme.charcoal : selectedFilter.iconColor)
                        Text(selectedFilter.displayName)
                            .font(JazzTheme.subheadline())
                            .foregroundColor(JazzTheme.charcoal)
                        Image(systemName: "chevron.down")
                            .font(JazzTheme.caption2())
                            .foregroundColor(JazzTheme.charcoal)
                    }
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
                    .background(selectedFilter == .all ? JazzTheme.cardBackground : selectedFilter.iconColor.opacity(0.15))
                    .cornerRadius(8)
                }
                .menuStyle(.borderlessButton)

                // Vocal/Instrumental filter menu
                Menu {
                    ForEach(VocalFilter.allCases) { filter in
                        Button(action: { selectedVocalFilter = filter }) {
                            HStack {
                                Image(systemName: filter.icon)
                                    .foregroundColor(filter.iconColor)
                                Text(filter.rawValue)
                                if selectedVocalFilter == filter {
                                    Spacer()
                                    Image(systemName: "checkmark")
                                }
                            }
                        }
                    }
                } label: {
                    HStack(spacing: 4) {
                        Image(systemName: selectedVocalFilter.icon)
                            .foregroundColor(selectedVocalFilter == .all ? JazzTheme.charcoal : selectedVocalFilter.iconColor)
                        Text(selectedVocalFilter.rawValue)
                            .font(JazzTheme.subheadline())
                            .foregroundColor(JazzTheme.charcoal)
                        Image(systemName: "chevron.down")
                            .font(JazzTheme.caption2())
                            .foregroundColor(JazzTheme.charcoal)
                    }
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
                    .background(selectedVocalFilter == .all ? JazzTheme.cardBackground : selectedVocalFilter.iconColor.opacity(0.15))
                    .cornerRadius(8)
                }
                .menuStyle(.borderlessButton)

                // Clear button when vocal filter is active
                if selectedVocalFilter != .all {
                    Button(action: { selectedVocalFilter = .all }) {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundColor(JazzTheme.burgundy)
                            .font(.system(size: 16))
                    }
                    .buttonStyle(.plain)
                    .help("Clear type filter")
                }

                // Instrument filter menu (only show if instruments are available)
                let instruments = availableInstruments(recordings)
                if !instruments.isEmpty {
                    Menu {
                        Button(action: { selectedInstrument = nil }) {
                            HStack {
                                Text("All Instruments")
                                if selectedInstrument == nil {
                                    Spacer()
                                    Image(systemName: "checkmark")
                                }
                            }
                        }

                        Divider()

                        ForEach(instruments) { family in
                            Button(action: { selectedInstrument = family }) {
                                HStack {
                                    Image(systemName: family.icon)
                                    Text(family.rawValue)
                                    if selectedInstrument == family {
                                        Spacer()
                                        Image(systemName: "checkmark")
                                    }
                                }
                            }
                        }
                    } label: {
                        HStack(spacing: 4) {
                            Image(systemName: selectedInstrument?.icon ?? "pianokeys")
                            Text(selectedInstrument?.rawValue ?? "Instrument")
                                .font(JazzTheme.subheadline())
                            Image(systemName: "chevron.down")
                                .font(JazzTheme.caption2())
                        }
                        .foregroundColor(JazzTheme.charcoal)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 6)
                        .background(JazzTheme.cardBackground)
                        .cornerRadius(8)
                    }
                    .menuStyle(.borderlessButton)

                    // Clear button when instrument filter is active
                    if selectedInstrument != nil {
                        Button(action: { selectedInstrument = nil }) {
                            Image(systemName: "xmark.circle.fill")
                                .foregroundColor(JazzTheme.burgundy)
                                .font(.system(size: 16))
                        }
                        .buttonStyle(.plain)
                        .help("Clear instrument filter")
                    }
                }

                // Sort menu (matching iOS style)
                Menu {
                    ForEach(RecordingSortOrder.allCases) { order in
                        Button(action: { sortOrder = order }) {
                            HStack {
                                Text(order.displayName)
                                if sortOrder == order {
                                    Image(systemName: "checkmark")
                                }
                            }
                        }
                    }
                } label: {
                    HStack(spacing: 3) {
                        Text(sortOrder.displayName)
                            .font(JazzTheme.caption())
                            .foregroundColor(JazzTheme.charcoal)
                        Image(systemName: "chevron.down")
                            .font(JazzTheme.caption2())
                            .foregroundColor(JazzTheme.charcoal)
                    }
                    .padding(.horizontal, 8)
                    .padding(.vertical, 5)
                    .background(JazzTheme.burgundy.opacity(0.2))
                    .cornerRadius(6)
                }
                .menuStyle(.borderlessButton)
            }

            // Recordings list
            if isRecordingsLoading {
                VStack(spacing: 12) {
                    ProgressView()
                        .scaleEffect(1.2)
                    Text("Loading recordings...")
                        .font(JazzTheme.subheadline())
                        .foregroundColor(JazzTheme.smokeGray)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 40)
            } else if filtered.isEmpty {
                VStack(spacing: 12) {
                    Image(systemName: "music.note.slash")
                        .font(.system(size: 40))
                        .foregroundColor(JazzTheme.smokeGray.opacity(0.5))
                    Text("No recordings match the current filters")
                        .font(JazzTheme.subheadline())
                        .foregroundColor(JazzTheme.smokeGray)
                    Button("Clear Filters") {
                        selectedFilter = .all
                        selectedInstrument = nil
                    }
                    .buttonStyle(.link)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 40)
            } else {
                // Grouped recordings
                ForEach(grouped, id: \.groupKey) { group in
                    VStack(alignment: .leading, spacing: 8) {
                        // Group header
                        Text("\(group.groupKey) (\(group.recordings.count))")
                            .font(JazzTheme.headline())
                            .foregroundColor(JazzTheme.burgundy)
                            .padding(.top, 8)

                        // Horizontal scroll of recordings in this group
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(alignment: .top, spacing: 16) {
                                ForEach(group.recordings) { recording in
                                    RecordingCard(recording: recording, showArtistName: sortOrder == .year || group.groupKey == "More Recordings")
                                        .contentShape(Rectangle())
                                        .onTapGesture {
                                            selectedRecordingId = recording.id
                                        }
                                }
                            }
                            .padding(.horizontal, 4)
                        }
                    }
                }
            }
        }
        .sheet(isPresented: Binding(
            get: { selectedRecordingId != nil },
            set: { if !$0 { selectedRecordingId = nil } }
        )) {
            if let recordingId = selectedRecordingId {
                RecordingDetailView(recordingId: recordingId)
                    .frame(minWidth: 600, minHeight: 500)
            }
        }
    }

    // MARK: - Featured Recordings Carousel

    @ViewBuilder
    private func featuredRecordingsSection(_ recordings: [Recording]) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Featured Recordings")
                .font(JazzTheme.title2())
                .foregroundColor(JazzTheme.charcoal)

            Text("Important recordings for this song")
                .font(JazzTheme.subheadline())
                .foregroundColor(JazzTheme.smokeGray)

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(alignment: .top, spacing: 20) {
                    ForEach(recordings) { recording in
                        FeaturedRecordingCard(recording: recording)
                            .onTapGesture {
                                selectedRecordingId = recording.id
                            }
                    }
                }
                .padding(.horizontal, 4)
            }
        }
        .padding(16)
        .background(Color.white)
        .cornerRadius(12)
    }

    // MARK: - Transcriptions Section

    @ViewBuilder
    private var transcriptionsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "music.quarternote.3")
                    .foregroundColor(JazzTheme.teal)
                Text("Solo Transcriptions")
                    .font(JazzTheme.title2())
                    .foregroundColor(JazzTheme.charcoal)

                Spacer()

                Text("\(transcriptions.count)")
                    .font(JazzTheme.subheadline())
                    .foregroundColor(JazzTheme.smokeGray)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(JazzTheme.teal.opacity(0.1))
                    .cornerRadius(6)
            }

            ForEach(transcriptions) { transcription in
                TranscriptionRow(transcription: transcription)
            }
        }
        .padding(16)
        .background(JazzTheme.cardBackground)
        .cornerRadius(12)
    }

    // MARK: - Backing Tracks Section

    @ViewBuilder
    private var backingTracksSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "play.circle.fill")
                    .foregroundColor(JazzTheme.green)
                Text("Backing Tracks")
                    .font(JazzTheme.title2())
                    .foregroundColor(JazzTheme.charcoal)

                Spacer()

                Text("\(backingTracks.count)")
                    .font(JazzTheme.subheadline())
                    .foregroundColor(JazzTheme.smokeGray)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(JazzTheme.green.opacity(0.1))
                    .cornerRadius(6)
            }

            ForEach(backingTracks) { video in
                BackingTrackRow(video: video)
            }
        }
        .padding(16)
        .background(JazzTheme.cardBackground)
        .cornerRadius(12)
    }

    // MARK: - Data Loading

    private func loadSong() async {
        isLoading = true
        isRecordingsLoading = true

        // Phase 1: Load summary (fast) - includes song metadata, featured recordings, transcriptions
        let fetchedSong = await networkManager.fetchSongSummary(id: songId)
        song = fetchedSong
        transcriptions = fetchedSong?.transcriptions ?? []
        isLoading = false

        // Load backing tracks
        do {
            let videos = try await networkManager.fetchSongVideos(songId: songId, videoType: "backing_track")
            backingTracks = videos
        } catch {
            print("Error fetching backing tracks: \(error)")
        }

        // Phase 2: Load all recordings with full streaming data
        if let recordings = await networkManager.fetchSongRecordings(id: songId, sortBy: sortOrder) {
            song?.recordings = recordings
        }
        isRecordingsLoading = false
    }

    private func reloadRecordings() async {
        isRecordingsLoading = true
        if let recordings = await networkManager.fetchSongRecordings(id: songId, sortBy: sortOrder) {
            song?.recordings = recordings
        }
        isRecordingsLoading = false
    }
}

// MARK: - Recording Card

struct RecordingCard: View {
    let recording: Recording
    var showArtistName: Bool = true
    @State private var isHovering = false
    @State private var showingBackCover = false

    private let artworkSize: CGFloat = 160

    private var artistName: String {
        if let artistCredit = recording.artistCredit, !artistCredit.isEmpty {
            return artistCredit
        }
        if let performers = recording.performers {
            if let leader = performers.first(where: { $0.role?.lowercased() == "leader" }) {
                return leader.name
            }
            if let first = performers.first {
                return first.name
            }
        }
        return "Unknown Artist"
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
            // Album art with flip support and streaming button overlay
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
                                        .fill(JazzTheme.cardBackground)
                                        .overlay { ProgressView() }
                                case .success(let image):
                                    image
                                        .resizable()
                                        .aspectRatio(contentMode: .fill)
                                case .failure:
                                    Rectangle()
                                        .fill(JazzTheme.cardBackground)
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
                                .fill(JazzTheme.cardBackground)
                                .overlay {
                                    Image(systemName: "music.note")
                                        .font(.system(size: 40))
                                        .foregroundColor(JazzTheme.smokeGray)
                                }
                        }
                    }
                    .frame(width: artworkSize, height: artworkSize)
                    .clipShape(RoundedRectangle(cornerRadius: 10))
                    .opacity(showingBackCover ? 0 : 1)

                    // Back cover (pre-rotated so it appears correct after flip)
                    if let backUrl = backCoverUrl {
                        AsyncImage(url: URL(string: backUrl)) { phase in
                            switch phase {
                            case .empty:
                                Rectangle()
                                    .fill(JazzTheme.cardBackground)
                                    .overlay { ProgressView() }
                            case .success(let image):
                                image
                                    .resizable()
                                    .aspectRatio(contentMode: .fill)
                            case .failure:
                                Rectangle()
                                    .fill(JazzTheme.cardBackground)
                            @unknown default:
                                EmptyView()
                            }
                        }
                        .frame(width: artworkSize, height: artworkSize)
                        .clipShape(RoundedRectangle(cornerRadius: 10))
                        .rotation3DEffect(.degrees(180), axis: (x: 0, y: 1, z: 0))
                        .opacity(showingBackCover ? 1 : 0)
                    }
                }
                .rotation3DEffect(
                    .degrees(showingBackCover ? 180 : 0),
                    axis: (x: 0, y: 1, z: 0)
                )
                .shadow(color: .black.opacity(0.15), radius: 6, x: 0, y: 3)

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
                    .buttonStyle(.plain)
                    .padding(6)
                    .help(showingBackCover ? "Show front cover" : "Show back cover")
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

                // Streaming button overlay (bottom-right)
                VStack {
                    Spacer()
                    HStack {
                        Spacer()
                        StreamingButtons(recording: recording)
                    }
                }
                .padding(8)
            }
            .frame(width: artworkSize, height: artworkSize)

            // Recording info below artwork
            VStack(alignment: .leading, spacing: 4) {
                // Artist name
                if showArtistName {
                    Text(artistName)
                        .font(JazzTheme.subheadline(weight: .semibold))
                        .foregroundColor(JazzTheme.brass)
                        .lineLimit(1)
                }

                // Album title with optional canonical star
                HStack(spacing: 4) {
                    if recording.isCanonical == true {
                        Image(systemName: "star.fill")
                            .foregroundColor(JazzTheme.gold)
                            .font(JazzTheme.caption())
                    }

                    Text(recording.albumTitle ?? "Unknown Album")
                        .font(JazzTheme.body(weight: .medium))
                        .foregroundColor(JazzTheme.charcoal)
                        .lineLimit(2)
                }

                // Year
                if let year = recording.recordingYear {
                    Text(String(year))
                        .font(JazzTheme.caption())
                        .foregroundColor(JazzTheme.smokeGray)
                }
            }
            .frame(width: artworkSize, alignment: .leading)
        }
        .padding(12)
        .background(isHovering ? JazzTheme.backgroundLight : JazzTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(isHovering ? JazzTheme.burgundy.opacity(0.5) : Color.clear, lineWidth: 2)
        )
        .onHover { hovering in
            isHovering = hovering
        }
        .animation(.easeInOut(duration: 0.15), value: isHovering)
    }
}

// MARK: - Featured Recording Card

struct FeaturedRecordingCard: View {
    let recording: Recording
    @State private var isHovering = false
    @State private var showingBackCover = false

    private let artworkSize: CGFloat = 180

    private var artistName: String {
        if let artistCredit = recording.artistCredit, !artistCredit.isEmpty {
            return artistCredit
        }
        if let performers = recording.performers {
            if let leader = performers.first(where: { $0.role?.lowercased() == "leader" }) {
                return leader.name
            }
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
                                        .overlay { ProgressView() }
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
                                    .overlay { ProgressView() }
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
                    .buttonStyle(.plain)
                    .padding(6)
                    .help(showingBackCover ? "Show front cover" : "Show back cover")
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

            // Recording Info
            VStack(alignment: .leading, spacing: 4) {
                Text(artistName)
                    .font(JazzTheme.subheadline(weight: .semibold))
                    .foregroundColor(JazzTheme.brass)
                    .lineLimit(1)

                Text(recording.albumTitle ?? "Unknown Album")
                    .font(JazzTheme.body(weight: .medium))
                    .foregroundColor(JazzTheme.charcoal)
                    .lineLimit(2)

                if let year = recording.recordingYear {
                    Text(String(year))
                        .font(JazzTheme.caption())
                        .foregroundColor(JazzTheme.smokeGray)
                }
            }
            .frame(width: artworkSize, alignment: .leading)
        }
        .padding(12)
        .background(isHovering ? JazzTheme.backgroundLight : JazzTheme.cardBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(isHovering ? JazzTheme.burgundy.opacity(0.5) : Color.clear, lineWidth: 2)
        )
        .onHover { hovering in
            isHovering = hovering
        }
        .animation(.easeInOut(duration: 0.15), value: isHovering)
    }
}

// MARK: - Transcription Row

struct TranscriptionRow: View {
    let transcription: SoloTranscription
    @State private var isHovering = false
    @Environment(\.openURL) private var openURL

    var body: some View {
        Button(action: openYouTube) {
            HStack(spacing: 12) {
                // Play button thumbnail
                ZStack {
                    RoundedRectangle(cornerRadius: 8)
                        .fill(JazzTheme.teal.opacity(0.15))
                        .frame(width: 80, height: 45)

                    Image(systemName: "play.fill")
                        .font(.system(size: 20))
                        .foregroundColor(JazzTheme.teal)
                }

                // Transcription info
                VStack(alignment: .leading, spacing: 4) {
                    Text(transcription.albumTitle ?? "Solo Transcription")
                        .font(JazzTheme.headline())
                        .foregroundColor(JazzTheme.charcoal)
                        .lineLimit(2)

                    HStack(spacing: 12) {
                        if let year = transcription.recordingYear {
                            HStack(spacing: 4) {
                                Image(systemName: "calendar")
                                    .foregroundColor(JazzTheme.brass)
                                    .font(JazzTheme.caption())
                                Text(String(format: "%d", year))
                                    .font(JazzTheme.subheadline())
                                    .foregroundColor(JazzTheme.smokeGray)
                            }
                        }

                        if let label = transcription.label {
                            HStack(spacing: 4) {
                                Image(systemName: "opticaldisc")
                                    .foregroundColor(JazzTheme.brass)
                                    .font(JazzTheme.caption())
                                Text(label)
                                    .font(JazzTheme.subheadline())
                                    .foregroundColor(JazzTheme.smokeGray)
                                    .lineLimit(1)
                            }
                        }
                    }
                }

                Spacer()

                // YouTube icon indicator
                if transcription.youtubeUrl != nil {
                    Image(systemName: "play.rectangle.fill")
                        .font(.title2)
                        .foregroundColor(.red)
                }
            }
            .padding()
            .background(isHovering ? JazzTheme.backgroundLight : Color.white)
            .cornerRadius(10)
            .overlay(
                RoundedRectangle(cornerRadius: 10)
                    .stroke(isHovering ? JazzTheme.teal.opacity(0.5) : Color.clear, lineWidth: 2)
            )
        }
        .buttonStyle(.plain)
        .onHover { hovering in
            isHovering = hovering
        }
        .animation(.easeInOut(duration: 0.15), value: isHovering)
        .help(transcription.youtubeUrl != nil ? "Watch on YouTube" : "No video available")
    }

    private func openYouTube() {
        guard let urlString = transcription.youtubeUrl,
              let url = URL(string: urlString) else { return }
        openURL(url)
    }
}

// MARK: - Backing Track Row

struct BackingTrackRow: View {
    let video: Video
    @State private var isHovering = false
    @Environment(\.openURL) private var openURL

    var body: some View {
        Button(action: openYouTube) {
            HStack(spacing: 12) {
                // Play button thumbnail
                ZStack {
                    RoundedRectangle(cornerRadius: 8)
                        .fill(JazzTheme.green.opacity(0.15))
                        .frame(width: 80, height: 45)

                    Image(systemName: "play.fill")
                        .font(.system(size: 20))
                        .foregroundColor(JazzTheme.green)
                }

                // Video info
                VStack(alignment: .leading, spacing: 4) {
                    Text(video.title ?? "Backing Track")
                        .font(JazzTheme.headline())
                        .foregroundColor(JazzTheme.charcoal)
                        .lineLimit(2)

                    if let duration = video.durationSeconds {
                        HStack(spacing: 4) {
                            Image(systemName: "clock")
                                .foregroundColor(JazzTheme.brass)
                                .font(JazzTheme.caption())
                            Text(formatDuration(duration))
                                .font(JazzTheme.subheadline())
                                .foregroundColor(JazzTheme.smokeGray)
                        }
                    }
                }

                Spacer()

                // YouTube icon indicator
                if video.youtubeUrl != nil {
                    Image(systemName: "play.rectangle.fill")
                        .font(.title2)
                        .foregroundColor(.red)
                }
            }
            .padding()
            .background(isHovering ? JazzTheme.backgroundLight : Color.white)
            .cornerRadius(10)
            .overlay(
                RoundedRectangle(cornerRadius: 10)
                    .stroke(isHovering ? JazzTheme.green.opacity(0.5) : Color.clear, lineWidth: 2)
            )
        }
        .buttonStyle(.plain)
        .onHover { hovering in
            isHovering = hovering
        }
        .animation(.easeInOut(duration: 0.15), value: isHovering)
        .help(video.youtubeUrl != nil ? "Watch on YouTube" : "No video available")
    }

    private func openYouTube() {
        guard let urlString = video.youtubeUrl,
              let url = URL(string: urlString) else { return }
        openURL(url)
    }

    private func formatDuration(_ seconds: Int) -> String {
        let minutes = seconds / 60
        let remainingSeconds = seconds % 60
        return String(format: "%d:%02d", minutes, remainingSeconds)
    }
}

// MARK: - Streaming Buttons

struct StreamingButtons: View {
    let recording: Recording

    /// Get Spotify URL from streamingLinks or legacy field
    private var spotifyUrl: String? {
        if let link = recording.streamingLinks?["spotify"], let url = link.bestPlaybackUrl {
            return url
        }
        return recording.bestSpotifyUrl
    }

    /// Get Apple Music URL from streamingLinks or legacy field
    private var appleMusicUrl: String? {
        if let link = recording.streamingLinks?["apple_music"], let url = link.bestPlaybackUrl {
            return url
        }
        return recording.appleMusicUrl
    }

    /// Get YouTube URL from streamingLinks or legacy field
    private var youtubeUrl: String? {
        if let link = recording.streamingLinks?["youtube"], let url = link.bestPlaybackUrl {
            return url
        }
        return recording.youtubeUrl
    }

    var body: some View {
        HStack(spacing: 8) {
            if let urlString = spotifyUrl, let url = URL(string: urlString) {
                Link(destination: url) {
                    Image(systemName: "play.circle.fill")
                        .font(.title2)
                        .foregroundColor(.green)
                }
                .buttonStyle(.plain)
                .help("Open in Spotify")
            }

            if let urlString = appleMusicUrl, let url = URL(string: urlString) {
                Link(destination: url) {
                    Image(systemName: "music.note")
                        .font(.title2)
                        .foregroundColor(Color(red: 252/255, green: 60/255, blue: 68/255))
                }
                .buttonStyle(.plain)
                .help("Open in Apple Music")
            }

            if let urlString = youtubeUrl, let url = URL(string: urlString) {
                Link(destination: url) {
                    Image(systemName: "play.rectangle.fill")
                        .font(.title2)
                        .foregroundColor(.red)
                }
                .buttonStyle(.plain)
                .help("Open in YouTube")
            }
        }
    }
}

#Preview {
    SongDetailView(songId: "preview-id")
        .environmentObject(RepertoireManager())
        .environmentObject(AuthenticationManager())
}

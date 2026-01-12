//
//  RecordingsSection.swift
//  JazzReference
//
//  Collapsible section displaying filtered recordings with filter chips + sheet pattern
//  UPDATED: Replaced nested disclosure groups with filter chips and bottom sheet
//  UPDATED: Sort options changed from Authority/Year/Canonical to Name/Year
//  UPDATED: Grouping changes based on sort order (by year or by artist name)
//

import SwiftUI

// MARK: - Song Recording Filter Enum
enum SongRecordingFilter: String, CaseIterable {
    case all = "All"
    case playable = "Playable"
    case withSpotify = "With Spotify"
    case withAppleMusic = "With Apple Music"

    var displayName: String {
        rawValue
    }

    var subtitle: String {
        switch self {
        case .all: return "Show all recordings"
        case .playable: return "Any streaming service available"
        case .withSpotify: return "Recordings available on Spotify"
        case .withAppleMusic: return "Recordings available on Apple Music"
        }
    }

    var icon: String {
        switch self {
        case .all: return "music.note.list"
        case .playable: return "play.circle"
        case .withSpotify: return "music.note.list"
        case .withAppleMusic: return "music.note"
        }
    }

    var iconColor: Color {
        switch self {
        case .all: return JazzTheme.smokeGray
        case .playable: return JazzTheme.burgundy
        case .withSpotify: return StreamingService.spotify.brandColor
        case .withAppleMusic: return StreamingService.appleMusic.brandColor
        }
    }
}

// MARK: - Vocal Filter Enum
enum VocalFilter: String, CaseIterable {
    case all = "All"
    case instrumental = "Instrumental"
    case vocal = "Vocal"

    var displayName: String {
        rawValue
    }

    var subtitle: String {
        switch self {
        case .all: return "Show all recordings"
        case .instrumental: return "Instrumental performances only"
        case .vocal: return "Vocal performances only"
        }
    }

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

// MARK: - Recordings Section
struct RecordingsSection: View {
    let recordings: [Recording]

    // Binding for sort order (passed from parent)
    @Binding var recordingSortOrder: RecordingSortOrder

    // Loading state for sort order changes
    var isReloading: Bool = false

    // Callback when sort order changes (for parent to reload data)
    var onSortOrderChanged: ((RecordingSortOrder) -> Void)?

    // Callback when community data changes (for parent to reload recordings)
    var onCommunityDataChanged: (() -> Void)?

    @State private var selectedFilter: SongRecordingFilter = .playable
    @State private var selectedVocalFilter: VocalFilter = .all
    @State private var selectedInstrument: InstrumentFamily? = nil
    @State private var showFilterSheet: Bool = false
    @State private var isSectionExpanded: Bool = true

    var body: some View {
        // HStack with explicit spacers ensures DisclosureGroup chevron is properly inset
        HStack(spacing: 0) {
            Spacer().frame(width: 16)

            VStack(alignment: .leading, spacing: 0) {
                DisclosureGroup(
                    isExpanded: $isSectionExpanded,
                    content: {
                        VStack(alignment: .leading, spacing: 0) {

                            // MARK: - FILTER CHIPS BAR
                            if hasActiveFilters || !availableInstruments.isEmpty {
                                filterChipsBar
                                    .padding(.vertical, 8)
                                    .padding(.horizontal, 4)
                                    .background(JazzTheme.cardBackground)
                                    .cornerRadius(8)
                                    .padding(.horizontal)
                            }

                            // Recordings List (lazy-loaded for performance)
                            LazyVStack(alignment: .leading, spacing: 12) {
                                if !filteredRecordings.isEmpty {
                                    ForEach(groupedRecordings, id: \.groupKey) { group in
                                        VStack(alignment: .leading, spacing: 8) {
                                            Text("\(group.groupKey) (\(group.recordings.count))")
                                                .font(JazzTheme.headline())
                                                .foregroundColor(JazzTheme.burgundy)
                                                .padding(.horizontal)
                                                .padding(.top, 8)

                                            ScrollView(.horizontal, showsIndicators: false) {
                                                LazyHStack(alignment: .top, spacing: 0) {
                                                    ForEach(Array(group.recordings.enumerated()), id: \.element.id) { index, recording in
                                                        HStack(alignment: .top, spacing: 0) {
                                                            // Divider before item (except first)
                                                            if index > 0 {
                                                                Rectangle()
                                                                    .fill(JazzTheme.burgundy.opacity(0.4))
                                                                    .frame(width: 2, height: 150)
                                                                    .padding(.horizontal, 8)
                                                            }

                                                            NavigationLink(destination: RecordingDetailView(
                                                                recordingId: recording.id,
                                                                onCommunityDataChanged: onCommunityDataChanged
                                                            )) {
                                                                RecordingRowView(
                                                                    recording: recording,
                                                                    showArtistName: recordingSortOrder == .year || group.groupKey == "More Recordings"
                                                                )
                                                            }
                                                            .buttonStyle(.plain)
                                                        }
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
                                            .font(JazzTheme.subheadline())
                                            .foregroundColor(JazzTheme.smokeGray)
                                            .multilineTextAlignment(.center)
                                    }
                                    .frame(maxWidth: .infinity)
                                    .padding(.vertical, 40)
                                }
                            }
                            .padding(.top, 8)
                            .overlay(alignment: .top) {
                                if isReloading {
                                    HStack(spacing: 8) {
                                        ProgressView()
                                            .tint(JazzTheme.burgundy)
                                        Text("Reloading...")
                                            .font(JazzTheme.subheadline())
                                            .foregroundColor(JazzTheme.smokeGray)
                                    }
                                    .padding(.horizontal, 16)
                                    .padding(.vertical, 10)
                                    .background(.ultraThinMaterial)
                                    .cornerRadius(8)
                                    .shadow(color: .black.opacity(0.1), radius: 4, y: 2)
                                    .padding(.top, 40)
                                }
                            }
                            .opacity(isReloading ? 0.5 : 1.0)
                            .animation(.easeInOut(duration: 0.2), value: isReloading)
                        }
                    },
                    label: {
                        HStack(alignment: .center) {
                            Image(systemName: "music.note.list")
                                .foregroundColor(JazzTheme.burgundy)

                            Text("Recordings")
                                .font(JazzTheme.title2())
                                .bold()
                                .foregroundColor(JazzTheme.charcoal)

                            // Recording count in header
                            Text("(\(filteredRecordings.count))")
                                .font(JazzTheme.subheadline())
                                .foregroundColor(JazzTheme.smokeGray)

                            Spacer()

                            // Sort menu
                            Menu {
                                ForEach(RecordingSortOrder.allCases) { sortOrder in
                                    Button(action: {
                                        if recordingSortOrder != sortOrder {
                                            recordingSortOrder = sortOrder
                                            onSortOrderChanged?(sortOrder)
                                        }
                                    }) {
                                        HStack {
                                            Text(sortOrder.displayName)
                                            if recordingSortOrder == sortOrder {
                                                Image(systemName: "checkmark")
                                            }
                                        }
                                    }
                                }
                            } label: {
                                HStack(spacing: 3) {
                                    Text(recordingSortOrder.displayName)
                                        .font(JazzTheme.caption())
                                    Image(systemName: "chevron.down")
                                        .font(.caption2)
                                }
                                .foregroundColor(JazzTheme.burgundy)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 5)
                                .background(JazzTheme.burgundy.opacity(0.1))
                                .cornerRadius(6)
                            }
                        }
                        .padding(.vertical, 12)
                    }
                )
                .tint(JazzTheme.burgundy)
            }
            
            Spacer().frame(width: 16)
        }
        .background(JazzTheme.backgroundLight)
        .sheet(isPresented: $showFilterSheet) {
            RecordingFilterSheet(
                selectedFilter: $selectedFilter,
                selectedVocalFilter: $selectedVocalFilter,
                selectedInstrument: $selectedInstrument,
                availableInstruments: availableInstruments
            )
        }
    }

    // MARK: - Filter Chips Bar

    @ViewBuilder
    private var filterChipsBar: some View {
        HStack(spacing: 8) {
            // Active filter chips for streaming service
            if selectedFilter != .all {
                FilterChip(
                    label: selectedFilter.displayName,
                    icon: selectedFilter.icon,
                    iconColor: selectedFilter.iconColor,
                    onRemove: { selectedFilter = .all }
                )
            }

            // Active filter chip for vocal/instrumental
            if selectedVocalFilter != .all {
                FilterChip(
                    label: selectedVocalFilter.displayName,
                    icon: selectedVocalFilter.icon,
                    iconColor: selectedVocalFilter.iconColor,
                    onRemove: { selectedVocalFilter = .all }
                )
            }

            if let instrument = selectedInstrument {
                FilterChip(
                    label: instrument.rawValue,
                    icon: nil,
                    onRemove: { selectedInstrument = nil }
                )
            }

            // Add/Edit Filter button
            Button(action: { showFilterSheet = true }) {
                HStack(spacing: 4) {
                    Image(systemName: hasActiveFilters ? "slider.horizontal.3" : "plus")
                        .font(.caption.weight(.medium))
                    Text(hasActiveFilters ? "Edit" : "Filter")
                        .font(JazzTheme.subheadline())
                }
                .foregroundColor(JazzTheme.burgundy)
                .padding(.horizontal, 10)
                .padding(.vertical, 5)
                .background(JazzTheme.burgundy.opacity(0.15))
                .cornerRadius(14)
            }
            .buttonStyle(.plain)

            Spacer()
        }
    }

    private var hasActiveFilters: Bool {
        selectedFilter != .all || selectedVocalFilter != .all || selectedInstrument != nil
    }

    // MARK: - Computed Properties
    
    // Extract unique instrument families from recordings
    private var availableInstruments: [InstrumentFamily] {
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
    private var filteredRecordings: [Recording] {
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
        
        return result
    }
    
    // Group recordings based on sort order with smart consolidation
    // - Year sort: Group by decade (1960s, 1970s, etc.)
    // - Name sort: Featured artists (2+ recordings) + "More Recordings" (singles, alphabetical)
    private var groupedRecordings: [(groupKey: String, recordings: [Recording])] {
        switch recordingSortOrder {
        case .year:
            return groupByDecade()
        case .name:
            return groupByArtistWithConsolidation()
        }
    }

    // MARK: - Decade Grouping (for Year sort)
    private func groupByDecade() -> [(groupKey: String, recordings: [Recording])] {
        var decadeOrder: [String] = []
        var decades: [String: [Recording]] = [:]

        for recording in filteredRecordings {
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
            guard let recordings = decades[key] else { return nil }
            return (groupKey: key, recordings: recordings)
        }
    }

    // MARK: - Artist Grouping with Consolidation (for Name sort)
    // Artists with 2+ recordings get their own section
    // Artists with 1 recording are combined into "More Recordings", sorted alphabetically
    private func groupByArtistWithConsolidation() -> [(groupKey: String, recordings: [Recording])] {
        // First pass: count recordings per artist
        var artistCounts: [String: Int] = [:]
        for recording in filteredRecordings {
            let artist = recording.performers?.first { $0.role == "leader" }?.name ?? "Unknown"
            artistCounts[artist, default: 0] += 1
        }

        // Second pass: separate featured artists from singles
        var featuredOrder: [String] = []
        var featuredGroups: [String: [Recording]] = [:]
        var moreRecordings: [Recording] = []

        for recording in filteredRecordings {
            let artist = recording.performers?.first { $0.role == "leader" }?.name ?? "Unknown"

            if artistCounts[artist, default: 0] >= 2 {
                // Featured artist - gets own section
                if featuredGroups[artist] == nil {
                    featuredOrder.append(artist)
                }
                featuredGroups[artist, default: []].append(recording)
            } else {
                // Single recording - goes to "More Recordings"
                moreRecordings.append(recording)
            }
        }

        // Build result: featured artists first (in original order)
        var result: [(groupKey: String, recordings: [Recording])] = []

        for artist in featuredOrder {
            if let recordings = featuredGroups[artist] {
                result.append((groupKey: artist, recordings: recordings))
            }
        }

        // Add "More Recordings" section if there are any singles
        if !moreRecordings.isEmpty {
            // Sort alphabetically by artist sort_name (falling back to name)
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
}

// MARK: - Filter Chip Component

struct FilterChip: View {
    let label: String
    let icon: String?
    var iconColor: Color? = nil
    var backgroundColor: Color? = nil
    let onRemove: () -> Void

    var body: some View {
        HStack(spacing: 4) {
            if let icon = icon {
                Image(systemName: icon)
                    .font(JazzTheme.caption())
                    .foregroundColor(iconColor ?? .white)
            }

            Text(label)
                .font(JazzTheme.subheadline())

            Button(action: onRemove) {
                Image(systemName: "xmark")
                    .font(.caption2.weight(.semibold))
            }
            .buttonStyle(.plain)
        }
        .foregroundColor(.white)
        .padding(.horizontal, 10)
        .padding(.vertical, 6)
        .background(backgroundColor ?? JazzTheme.brass)
        .cornerRadius(16)
    }
}

// MARK: - Previews

#Preview("Recordings Section") {
    struct PreviewWrapper: View {
        @State private var sortOrder: RecordingSortOrder = .year

        var body: some View {
            NavigationStack {
                ScrollView {
                    RecordingsSection(
                        recordings: [.preview1, .preview2, .previewMinimal],
                        recordingSortOrder: $sortOrder
                    )
                }
            }
        }
    }
    return PreviewWrapper()
}

#Preview("Filter Chips") {
    VStack(spacing: 12) {
        FilterChip(label: "Playable", icon: "play.circle", iconColor: JazzTheme.burgundy) {}
        FilterChip(label: "Spotify", icon: "music.note.list", iconColor: .green) {}
        FilterChip(label: "Piano", icon: nil) {}
    }
    .padding()
}

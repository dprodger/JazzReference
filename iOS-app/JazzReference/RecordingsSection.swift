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

// MARK: - Recordings Section
struct RecordingsSection: View {
    let recordings: [Recording]

    // Bindings for sort functionality (passed from parent)
    @Binding var recordingSortOrder: RecordingSortOrder
    @Binding var showingSortOptions: Bool

    @State private var selectedFilter: SongRecordingFilter = .withSpotify
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

                            // Recordings List
                            VStack(alignment: .leading, spacing: 12) {
                                if !filteredRecordings.isEmpty {
                                    ForEach(groupedRecordings, id: \.groupKey) { group in
                                        VStack(alignment: .leading, spacing: 8) {
                                            Text("\(group.groupKey) (\(group.recordings.count))")
                                                .font(.headline)
                                                .foregroundColor(JazzTheme.burgundy)
                                                .padding(.horizontal)
                                                .padding(.top, 8)
                                            
                                            ScrollView(.horizontal, showsIndicators: false) {
                                                HStack(alignment: .top, spacing: 16) {
                                                    ForEach(group.recordings) { recording in
                                                        NavigationLink(destination: RecordingDetailView(recordingId: recording.id)) {
                                                            RecordingRowView(
                                                                recording: recording,
                                                                showArtistName: recordingSortOrder == .year
                                                            )
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
                            .padding(.top, 8)
                        }
                    },
                    label: {
                        HStack(alignment: .center) {
                            Image(systemName: "music.note.list")
                                .foregroundColor(JazzTheme.burgundy)

                            Text("Recordings")
                                .font(.title2)
                                .bold()
                                .foregroundColor(JazzTheme.charcoal)

                            // Recording count in header
                            Text("(\(filteredRecordings.count))")
                                .font(.subheadline)
                                .foregroundColor(JazzTheme.smokeGray)

                            Spacer()

                            // Sort button
                            Button(action: {
                                showingSortOptions = true
                            }) {
                                HStack(spacing: 4) {
                                    Image(systemName: recordingSortOrder.icon)
                                        .font(.caption)
                                    Text(recordingSortOrder.displayName)
                                        .font(.caption)
                                }
                                .foregroundColor(JazzTheme.burgundy)
                                .padding(.horizontal, 10)
                                .padding(.vertical, 5)
                                .background(JazzTheme.burgundy.opacity(0.1))
                                .cornerRadius(6)
                            }
                            .buttonStyle(.plain)
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
                selectedInstrument: $selectedInstrument,
                availableInstruments: availableInstruments
            )
        }
    }

    // MARK: - Filter Chips Bar

    @ViewBuilder
    private var filterChipsBar: some View {
        HStack(spacing: 8) {
            // Active filter chips
            if selectedFilter == .withSpotify {
                FilterChip(
                    label: "Spotify",
                    icon: "music.note",
                    onRemove: { selectedFilter = .all }
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
                        .font(.subheadline)
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
        selectedFilter == .withSpotify || selectedInstrument != nil
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
        
        // Then, apply Spotify filter
        switch selectedFilter {
        case .withSpotify:
            // Use bestSpotifyUrl which checks releases first, then falls back to recording URL
            result = result.filter { $0.bestSpotifyUrl != nil }
        case .all:
            break
        }
        
        return result
    }
    
    // Group recordings based on sort order, preserving backend sort order
    // - Year sort: Group by recording year
    // - Name sort: Group by leader/artist name
    private var groupedRecordings: [(groupKey: String, recordings: [Recording])] {
        var keyOrder: [String] = []
        var groups: [String: [Recording]] = [:]
        
        for recording in filteredRecordings {
            let groupKey: String
            
            switch recordingSortOrder {
            case .year:
                // Group by year
                if let year = recording.recordingYear {
                    groupKey = String(year)
                } else {
                    groupKey = "Unknown Year"
                }
            case .name:
                // Group by leader name
                groupKey = recording.performers?.first { $0.role == "leader" }?.name ?? "Unknown"
            }
            
            // Track first appearance order
            if groups[groupKey] == nil {
                keyOrder.append(groupKey)
            }
            
            groups[groupKey, default: []].append(recording)
        }
        
        // Return groups in the order they first appeared (preserves backend sort)
        return keyOrder.compactMap { key in
            guard let recordings = groups[key] else { return nil }
            return (groupKey: key, recordings: recordings)
        }
    }
}

// MARK: - Filter Chip Component

struct FilterChip: View {
    let label: String
    let icon: String?
    let onRemove: () -> Void

    var body: some View {
        HStack(spacing: 4) {
            if let icon = icon {
                Image(systemName: icon)
                    .font(.caption)
            }

            Text(label)
                .font(.subheadline)

            Button(action: onRemove) {
                Image(systemName: "xmark")
                    .font(.caption2.weight(.semibold))
            }
            .buttonStyle(.plain)
        }
        .foregroundColor(.white)
        .padding(.horizontal, 10)
        .padding(.vertical, 6)
        .background(JazzTheme.brass)
        .cornerRadius(16)
    }
}

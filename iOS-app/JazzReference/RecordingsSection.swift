//
//  RecordingsSection.swift
//  JazzReference
//
//  Collapsible section displaying filtered recordings with instrument and Spotify filtering
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
    @State private var isFiltersExpanded: Bool = false
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
                                        .padding(.vertical, 12)
                                        .padding(.horizontal)
                                    },
                                    label: {
                                        HStack {
                                            Image(systemName: isFiltersExpanded ? "line.3.horizontal.decrease.circle.fill" : "line.3.horizontal.decrease.circle")
                                                .foregroundColor(JazzTheme.brass)
                                            Text("Filters")
                                                .font(.subheadline)
                                                .fontWeight(.medium)
                                                .foregroundColor(JazzTheme.charcoal)
                                            
                                            Spacer(minLength: 12)
                                            
                                            // Active filter indicators
                                            if selectedFilter != .withSpotify || selectedInstrument != nil {
                                                HStack(spacing: 4) {
                                                    if selectedFilter != .withSpotify {
                                                        Text(selectedFilter.rawValue)
                                                            .font(.caption2)
                                                            .foregroundColor(.white)
                                                            .padding(.horizontal, 6)
                                                            .padding(.vertical, 2)
                                                            .background(JazzTheme.brass)
                                                            .cornerRadius(4)
                                                            .fixedSize(horizontal: true, vertical: false)
                                                    }
                                                    
                                                    if let instrument = selectedInstrument {
                                                        Text(instrument.rawValue)
                                                            .font(.caption2)
                                                            .foregroundColor(.white)
                                                            .padding(.horizontal, 6)
                                                            .padding(.vertical, 2)
                                                            .background(JazzTheme.brass)
                                                            .cornerRadius(4)
                                                            .fixedSize(horizontal: true, vertical: false)
                                                    }
                                                }
                                            }
                                            
                                            Spacer(minLength: 8)
                                            
                                            // Recording count on same line
                                            Text("\(filteredRecordings.count) Recording\(filteredRecordings.count == 1 ? "" : "s")")
                                                .font(.subheadline)
                                                .foregroundColor(JazzTheme.smokeGray)
                                                .fixedSize(horizontal: true, vertical: false)
                                        }
                                        .padding(.vertical, 8)
                                    }
                                )
                                .tint(JazzTheme.brass)
                                .padding(.vertical, 8)
                            }
                            .background(JazzTheme.cardBackground)
                            .cornerRadius(10)
                            .padding(.horizontal)
                            .padding(.top, 8)
                            
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
                            .padding(.top)
                        }
                        .padding(.top, 8)
                    },
                    label: {
                        // MODIFIED: Added sort button to the label
                        HStack {
                            Image(systemName: "music.note.list")
                                .foregroundColor(JazzTheme.burgundy)
                            Text("Recordings")
                                .font(.title2)
                                .bold()
                                .foregroundColor(JazzTheme.charcoal)
                            
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
                                .padding(.horizontal, 12)
                                .padding(.vertical, 6)
                                .background(JazzTheme.burgundy.opacity(0.1))
                                .cornerRadius(8)
                            }
                            .buttonStyle(.plain) // Prevent disclosure group from toggling
                        }
                        .padding(.vertical, 12)
                    }
                )
                .tint(JazzTheme.burgundy)
            }
            
            Spacer().frame(width: 16)
        }
        .background(JazzTheme.backgroundLight)
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

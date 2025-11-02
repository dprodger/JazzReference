//
//  SongDetailView.swift
//  JazzReference
//
//  Updated with instrument filtering capability
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
    @State private var song: Song?
    @State private var isLoading = true
    @State private var selectedFilter: SongRecordingFilter = .withSpotify
    
    // Instrument filter states
    @State private var selectedInstrument: InstrumentFamily? = nil
    @State private var isInstrumentFilterExpanded: Bool = false
    
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
                    
                    // MARK: - NEW INSTRUMENT FILTER
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
                    
                    // MARK: - EXISTING SPOTIFY FILTER
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
        .navigationBarTitleDisplayMode(.inline)
        .toolbarBackground(JazzTheme.burgundy, for: .navigationBar)
        .toolbarBackground(.visible, for: .navigationBar)
        .toolbarColorScheme(.dark, for: .navigationBar)
        .task {
            #if DEBUG
            if ProcessInfo.processInfo.environment["XCODE_RUNNING_FOR_PREVIEWS"] == "1" {
                let networkManager = NetworkManager()
                song = networkManager.fetchSongDetailSync(id: songId)
                isLoading = false
                return
            }
            #endif
            
            let networkManager = NetworkManager()
            song = await networkManager.fetchSongDetail(id: songId)
            isLoading = false
        }
    }
}

// MARK: - Previews
#Preview("Song Detail - Full") {
    NavigationStack {
        SongDetailView(songId: "preview-song-1")
    }
}

#Preview("Song Detail - Minimal") {
    NavigationStack {
        SongDetailView(songId: "preview-song-2")
    }
}

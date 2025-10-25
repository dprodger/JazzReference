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

// MARK: - Song Detail View
struct SongDetailView: View {
    let songId: String
    @State private var song: Song?
    @State private var isLoading = true
    @State private var selectedFilter: SongRecordingFilter = .withSpotify
    
    // Instrument filter states
    @State private var selectedInstrument: String? = nil
    @State private var isInstrumentFilterExpanded: Bool = false
    
    // Extract unique instruments from recordings
    var availableInstruments: [String] {
        guard let recordings = song?.recordings else { return [] }
        
        var instruments = Set<String>()
        for recording in recordings {
            if let performers = recording.performers {
                for performer in performers {
                    if let instrument = performer.instrument {
                        instruments.insert(instrument)
                    }
                }
            }
        }
        
        return instruments.sorted()
    }
    
    // Apply filters in order: first instrument, then Spotify
    var filteredRecordings: [Recording] {
        guard let recordings = song?.recordings else { return [] }
        
        // First, apply instrument filter if selected
        var result = recordings
        if let instrument = selectedInstrument {
            result = result.filter { recording in
                guard let performers = recording.performers else { return false }
                return performers.contains { performer in
                    performer.instrument == instrument
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
                                        ForEach(availableInstruments, id: \.self) { instrument in
                                            Button(action: {
                                                if selectedInstrument == instrument {
                                                    selectedInstrument = nil
                                                } else {
                                                    selectedInstrument = instrument
                                                }
                                            }) {
                                                HStack {
                                                    Image(systemName: selectedInstrument == instrument ? "checkmark.circle.fill" : "circle")
                                                        .foregroundColor(selectedInstrument == instrument ? JazzTheme.brass : JazzTheme.smokeGray)
                                                    Text(instrument)
                                                        .foregroundColor(JazzTheme.charcoal)
                                                    Spacer()
                                                }
                                                .padding(.vertical, 8)
                                                .padding(.horizontal, 12)
                                                .background(
                                                    selectedInstrument == instrument
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
                                        
                                        if let instrument = selectedInstrument {
                                            Spacer()
                                            Text(instrument)
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
                            ForEach(filteredRecordings) { recording in
                                NavigationLink(destination: RecordingDetailView(recordingId: recording.id)) {
                                    RecordingRowView(recording: recording)
                                }
                                .buttonStyle(.plain)
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

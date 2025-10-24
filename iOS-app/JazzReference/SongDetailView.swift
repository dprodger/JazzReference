//
//  SongDetailView.swift
//  JazzReference
//
//  Updated with Spotify filtering, icons, external references panel, and toolbar styling
//

import SwiftUI
import Combine

// MARK: - Recording Filter Enum
enum SongRecordingFilter: String, CaseIterable {
    case withSpotify = "With Spotify"
    case all = "All"
}

// MARK: - External References Panel View
struct ExternalReferencesPanel: View {
    let externalReferences: [String: String]?
    let musicbrainzId: String?
    
    var wikipediaURL: String? {
        externalReferences?["wikipedia"]
    }
    
    var jazzStandardsURL: String? {
        externalReferences?["jazzstandards"]
    }
    
    var musicbrainzURL: String? {
        guard let mbId = musicbrainzId else { return nil }
        return "https://musicbrainz.org/work/\(mbId)"
    }
    
    var body: some View {
        if wikipediaURL != nil || jazzStandardsURL != nil || musicbrainzURL != nil {
            VStack(alignment: .leading, spacing: 12) {
                Text("External References")
                    .font(.headline)
                    .foregroundColor(JazzTheme.charcoal)
                
                HStack(spacing: 16) {
                    if let wikipediaURL = wikipediaURL, let url = URL(string: wikipediaURL) {
                        Link(destination: url) {
                            VStack(spacing: 4) {
                                Image(systemName: "book.circle.fill")
                                    .font(.title2)
                                    .foregroundColor(JazzTheme.brass)
                                Text("Wikipedia")
                                    .font(.caption)
                                    .foregroundColor(JazzTheme.smokeGray)
                            }
                        }
                    }
                    
                    if let jazzStandardsURL = jazzStandardsURL, let url = URL(string: jazzStandardsURL) {
                        Link(destination: url) {
                            VStack(spacing: 4) {
                                Image(systemName: "music.note.list")
                                    .font(.title2)
                                    .foregroundColor(JazzTheme.brass)
                                Text("Jazz Standards")
                                    .font(.caption)
                                    .foregroundColor(JazzTheme.smokeGray)
                            }
                        }
                    }
                    
                    if let musicbrainzURL = musicbrainzURL, let url = URL(string: musicbrainzURL) {
                        Link(destination: url) {
                            VStack(spacing: 4) {
                                Image(systemName: "music.mic.circle.fill")
                                    .font(.title2)
                                    .foregroundColor(JazzTheme.brass)
                                Text("MusicBrainz")
                                    .font(.caption)
                                    .foregroundColor(JazzTheme.smokeGray)
                            }
                        }
                    }
                }
                .padding(.top, 4)
            }
            .padding()
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(JazzTheme.cardBackground)
            .cornerRadius(10)
            .padding(.horizontal)
        }
    }
}

// MARK: - Song Detail View
struct SongDetailView: View {
    let songId: String
    @State private var song: Song?
    @State private var isLoading = true
    @State private var selectedFilter: SongRecordingFilter = .withSpotify
    
    var filteredRecordings: [Recording] {
        guard let recordings = song?.recordings else { return [] }
        
        switch selectedFilter {
        case .withSpotify:
            return recordings.filter { $0.spotifyUrl != nil }
        case .all:
            return recordings
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
                            musicbrainzId: song.musicbrainzId
                        )
                        
                    }
                    .padding()
                    
                    Divider()
                        .padding(.horizontal)
                    
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
                    VStack(spacing: 8) {
                        if !filteredRecordings.isEmpty {
                            ForEach(filteredRecordings) { recording in
                                NavigationLink(destination: RecordingDetailView(recordingId: recording.id)) {
                                    RecordingRowView(recording: recording)
                                }
                                .buttonStyle(PlainButtonStyle())
                            }
                        } else {
                            Text(selectedFilter == .withSpotify ?
                                 "No recordings with Spotify available" :
                                 "No recordings available")
                                .foregroundColor(JazzTheme.smokeGray)
                                .padding()
                        }
                    }
                }
            } else {
                VStack {
                    Spacer()
                    Text("Song not found")
                        .foregroundColor(JazzTheme.smokeGray)
                    Spacer()
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
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

#Preview("Song with Recordings") {
    NavigationStack {
        SongDetailView(songId: "preview-song-1")
    }
}

#Preview("Song - Loading State") {
    NavigationStack {
        SongDetailView(songId: "loading-test")
    }
}

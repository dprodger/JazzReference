//
//  SongDetailView.swift
//  JazzReference
//
//  Updated with Spotify filtering and icons
//

import SwiftUI
import Combine

// MARK: - Recording Filter Enum
enum SongRecordingFilter: String, CaseIterable {
    case withSpotify = "With Spotify"
    case all = "All"
}

struct SongDetailView: View {
    let songId: String
    @State private var song: Song?
    @State private var isLoading = true
    @State private var selectedFilter: SongRecordingFilter = .withSpotify // Default to Spotify-only
    
    private var filteredRecordings: [Recording] {
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
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(JazzTheme.backgroundLight)
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
                        // Song Information
                        VStack(alignment: .leading, spacing: 12) {
                            Text(song.title)
                                .font(.largeTitle)
                                .bold()
                                .foregroundColor(JazzTheme.charcoal)
                            
                            if let composer = song.composer {
                                Label {
                                    Text(composer)
                                        .font(.title3)
                                        .foregroundColor(JazzTheme.smokeGray)
                                } icon: {
                                    Image(systemName: "music.note.list")
                                        .foregroundColor(JazzTheme.brass)
                                }
                            }
                            
                            // Song Reference section
                            if let songReference = song.songReference {
                                VStack(alignment: .leading, spacing: 8) {
                                    Text("Information")
                                        .font(.headline)
                                        .foregroundColor(JazzTheme.charcoal)
                                    Text(songReference)
                                        .font(.body)
                                        .foregroundColor(JazzTheme.smokeGray)
                                }
                                .padding()
                                .background(JazzTheme.cardBackground)
                                .cornerRadius(10)
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
                                .background(JazzTheme.cardBackground)
                                .cornerRadius(10)
                            }
                        }
                        .padding()
                        
                        Divider()
                        
                        // Recordings Section with Filter
                        VStack(alignment: .leading, spacing: 12) {
                            Text("Recordings (\(filteredRecordings.count))")
                                .font(.title2)
                                .bold()
                                .foregroundColor(JazzTheme.charcoal)
                                .padding(.horizontal)
                            
                            // Filter Picker
                            Picker("Filter", selection: $selectedFilter) {
                                ForEach(SongRecordingFilter.allCases, id: \.self) { filter in
                                    Text(filter.rawValue).tag(filter)
                                }
                            }
                            .pickerStyle(.segmented)
                            .padding(.horizontal)
                            .tint(JazzTheme.burgundy)
                            
                            if !filteredRecordings.isEmpty {
                                ForEach(filteredRecordings) { recording in
                                    NavigationLink(destination: RecordingDetailView(recordingId: recording.id)) {
                                        RecordingRowView(recording: recording)
                                    }
                                    .buttonStyle(.plain)
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

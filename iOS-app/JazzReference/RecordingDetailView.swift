//
//  RecordingDetailView.swift
//  JazzReference
//
//  Updated with JazzTheme color palette
//

import SwiftUI
import Combine

struct RecordingDetailView: View {
    let recordingId: String
    @State private var recording: Recording?
    @State private var isLoading = true
    
    var body: some View {
        ScrollView {
            if isLoading {
                VStack {
                    Spacer()
                    ProgressView("Loading...")
                        .tint(JazzTheme.brass)
                    Spacer()
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(JazzTheme.backgroundLight)
            } else if let recording = recording {
                VStack(alignment: .leading, spacing: 0) {
                    // Styled Header with Jazz Theme
                    HStack {
                        Image(systemName: "opticaldisc")
                            .font(.title2)
                            .foregroundColor(JazzTheme.cream)
                        Text("RECORDING")
                            .font(.headline)
                            .fontWeight(.semibold)
                            .foregroundColor(JazzTheme.cream)
                        Spacer()
                    }
                    .padding()
                    .background(JazzTheme.brassGradient)
                    
                    VStack(alignment: .leading, spacing: 20) {
                        // Album Information
                        VStack(alignment: .leading, spacing: 12) {
                            HStack {
                                if recording.isCanonical == true {
                                    Image(systemName: "star.fill")
                                        .foregroundColor(JazzTheme.gold)
                                        .font(.title2)
                                }
                                Text(recording.albumTitle ?? "Unknown Album")
                                    .font(.largeTitle)
                                    .bold()
                                    .foregroundColor(JazzTheme.charcoal)
                            }
                            
                            if let songTitle = recording.songTitle {
                                Text(songTitle)
                                    .font(.title2)
                                    .foregroundColor(JazzTheme.smokeGray)
                            }
                            
                            if let composer = recording.composer {
                                Text("Composed by \(composer)")
                                    .font(.subheadline)
                                    .foregroundColor(JazzTheme.smokeGray)
                            }
                        }
                        .padding()
                        
                        // Recording Details
                        VStack(alignment: .leading, spacing: 12) {
                            if let year = recording.recordingYear {
                                DetailRow(
                                    icon: "calendar",
                                    label: "Year",
                                    value: "\(year)"
                                )
                            }
                            
                            if let date = recording.recordingDate {
                                DetailRow(
                                    icon: "calendar.badge.clock",
                                    label: "Recorded",
                                    value: date
                                )
                            }
                            
                            if let label = recording.label {
                                DetailRow(
                                    icon: "music.note.house",
                                    label: "Label",
                                    value: label
                                )
                            }
                        }
                        .padding()
                        .background(JazzTheme.cardBackground)
                        .cornerRadius(10)
                        .padding(.horizontal)
                        
                        // Streaming Links
                        if recording.spotifyUrl != nil || recording.youtubeUrl != nil || recording.appleMusicUrl != nil {
                            VStack(alignment: .leading, spacing: 12) {
                                Text("Listen")
                                    .font(.headline)
                                    .foregroundColor(JazzTheme.charcoal)
                                    .padding(.horizontal)
                                
                                HStack(spacing: 16) {
                                    if let spotifyUrl = recording.spotifyUrl {
                                        Link(destination: URL(string: spotifyUrl)!) {
                                            StreamingButton(
                                                icon: "music.note",
                                                color: JazzTheme.teal,
                                                label: "Spotify"
                                            )
                                        }
                                    }
                                    
                                    if let youtubeUrl = recording.youtubeUrl {
                                        Link(destination: URL(string: youtubeUrl)!) {
                                            StreamingButton(
                                                icon: "play.rectangle.fill",
                                                color: JazzTheme.burgundy,
                                                label: "YouTube"
                                            )
                                        }
                                    }
                                    
                                    if let appleMusicUrl = recording.appleMusicUrl {
                                        Link(destination: URL(string: appleMusicUrl)!) {
                                            StreamingButton(
                                                icon: "applelogo",
                                                color: JazzTheme.amber,
                                                label: "Apple"
                                            )
                                        }
                                    }
                                }
                                .padding(.horizontal)
                            }
                        }
                        
                        if let notes = recording.notes {
                            VStack(alignment: .leading, spacing: 8) {
                                Text("Notes")
                                    .font(.headline)
                                    .foregroundColor(JazzTheme.charcoal)
                                Text(notes)
                                    .font(.body)
                                    .foregroundColor(JazzTheme.smokeGray)
                            }
                            .padding()
                            .background(JazzTheme.cardBackground)
                            .cornerRadius(10)
                            .padding(.horizontal)
                        }
                        
                        // External References Panel
                        if recording.musicbrainzId != nil {
                            ExternalReferencesPanel(
                                musicbrainzId: recording.musicbrainzId,
                                recordingId: recordingId,
                                albumTitle: recording.albumTitle ?? "Unknown Album"
                            )
                        }
                        
                        Divider()
                            .padding(.horizontal)
                        
                        // Performers Section
                        VStack(alignment: .leading, spacing: 12) {
                            Text("Performers")
                                .font(.title2)
                                .bold()
                                .foregroundColor(JazzTheme.charcoal)
                                .padding(.horizontal)
                            
                            if let performers = recording.performers, !performers.isEmpty {
                                ForEach(performers) { performer in
                                    NavigationLink(destination: PerformerDetailView(performerId: performer.id)) {
                                        PerformerRowView(performer: performer)
                                    }
                                    .buttonStyle(.plain)
                                }
                            } else {
                                Text("No performer information available")
                                    .foregroundColor(JazzTheme.smokeGray)
                                    .padding()
                            }
                        }
                    }
                    .padding(.vertical)
                }
            } else {
                VStack {
                    Spacer()
                    Text("Recording not found")
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
                recording = networkManager.fetchRecordingDetailSync(id: recordingId)
                isLoading = false
                return
            }
            #endif
            
            let networkManager = NetworkManager()
            recording = await networkManager.fetchRecordingDetail(id: recordingId)
            isLoading = false
        }
    }
}

#Preview("Recording Detail - Full") {
    NavigationStack {
        RecordingDetailView(recordingId: "preview-recording-1")
    }
}
#Preview("Recording Detail - Minimal") {
    NavigationStack {
        RecordingDetailView(recordingId: "preview-recording-3")
    }
}

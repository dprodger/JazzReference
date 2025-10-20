//
//  RecordingDetailView.swift
//  JazzReference
//
//  Created by Dave Rodger on 10/8/25.
//

import SwiftUI
import Combine

// MARK: - Recording Detail View

struct RecordingDetailView: View {
    let recordingId: String
    @State private var recording: Recording?
    @State private var isLoading = true
    
    var body: some View {
        ScrollView {
            if isLoading {
                ProgressView("Loading...")
                    .padding()
            } else if let recording = recording {
                VStack(alignment: .leading, spacing: 0) {
                    // Styled Header
                    HStack {
                        Image(systemName: "opticaldisc")
                            .font(.title2)
                            .foregroundColor(.white)
                        Text("RECORDING")
                            .font(.headline)
                            .fontWeight(.semibold)
                            .foregroundColor(.white)
                        Spacer()
                    }
                    .padding()
                    .background(
                        LinearGradient(
                            gradient: Gradient(colors: [Color.purple, Color.purple.opacity(0.8)]),
                            startPoint: .leading,
                            endPoint: .trailing
                        )
                    )
                    
                    VStack(alignment: .leading, spacing: 20) {
                        // Album Information
                        VStack(alignment: .leading, spacing: 12) {
                            HStack {
                                if recording.isCanonical == true {
                                    Image(systemName: "star.fill")
                                        .foregroundColor(.yellow)
                                        .font(.title2)
                                }
                                Text(recording.albumTitle ?? "Unknown Album")
                                    .font(.largeTitle)
                                    .bold()
                            }
                            
                            if let songTitle = recording.songTitle {
                                Text(songTitle)
                                    .font(.title2)
                                    .foregroundColor(.secondary)
                            }
                            
                            if let composer = recording.composer {
                                Text("Composed by \(composer)")
                                    .font(.subheadline)
                                    .foregroundColor(.secondary)
                            }
                        }
                        .padding()
                        
                        // Recording Details
                        VStack(alignment: .leading, spacing: 12) {
                            if let year = recording.recordingYear {
                                DetailRow(icon: "calendar", label: "Year", value: "\(year)")
                            }
                            
                            if let date = recording.recordingDate {
                                DetailRow(icon: "calendar.badge.clock", label: "Recorded", value: date)
                            }
                            
                            if let label = recording.label {
                                DetailRow(icon: "music.note.house", label: "Label", value: label)
                            }
                        }
                        .padding()
                        .background(Color(.systemGray6))
                        .cornerRadius(10)
                        .padding(.horizontal)
                        
                        // Streaming Links
                        if recording.spotifyUrl != nil || recording.youtubeUrl != nil || recording.appleMusicUrl != nil {
                            VStack(alignment: .leading, spacing: 12) {
                                Text("Listen")
                                    .font(.headline)
                                    .padding(.horizontal)
                                
                                HStack(spacing: 16) {
                                    if let spotifyUrl = recording.spotifyUrl {
                                        Link(destination: URL(string: spotifyUrl)!) {
                                            StreamingButton(icon: "music.note", color: .green, label: "Spotify")
                                        }
                                    }
                                    
                                    if let youtubeUrl = recording.youtubeUrl {
                                        Link(destination: URL(string: youtubeUrl)!) {
                                            StreamingButton(icon: "play.rectangle.fill", color: .red, label: "YouTube")
                                        }
                                    }
                                    
                                    if let appleMusicUrl = recording.appleMusicUrl {
                                        Link(destination: URL(string: appleMusicUrl)!) {
                                            StreamingButton(icon: "applelogo", color: .pink, label: "Apple")
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
                                Text(notes)
                                    .font(.body)
                                    .foregroundColor(.secondary)
                            }
                            .padding()
                            .background(Color(.systemGray6))
                            .cornerRadius(10)
                            .padding(.horizontal)
                        }
                        
                        Divider()
                            .padding(.horizontal)
                        
                        // Performers Section
                        VStack(alignment: .leading, spacing: 12) {
                            Text("Performers")
                                .font(.title2)
                                .bold()
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
                                    .foregroundColor(.secondary)
                                    .padding()
                            }
                        }
                    }
                    .padding(.vertical)
                }
            } else {
                Text("Recording not found")
                    .foregroundColor(.secondary)
                    .padding()
            }
        }
        .navigationBarTitleDisplayMode(.inline)
        .task {
            #if DEBUG
            if ProcessInfo.processInfo.environment["XCODE_RUNNING_FOR_PREVIEWS"] == "1" {
                // Use mock data for previews
                let networkManager = NetworkManager()
                recording = networkManager.fetchRecordingDetailSync(id: recordingId)
                isLoading = false
                return
            }
            #endif
            
            // Real network call for production
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

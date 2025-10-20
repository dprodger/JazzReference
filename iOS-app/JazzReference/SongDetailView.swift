//
//  SongDetailView.swift
//  JazzReference
//
//  Created by Dave Rodger on 10/8/25.
//

import SwiftUI
import Combine

// MARK: - Song Detail View

struct SongDetailView: View {
    let songId: String
    @State private var song: Song?
    @State private var isLoading = true
    
    var body: some View {
        ScrollView {
            if isLoading {
                ProgressView("Loading...")
                    .padding()
            } else if let song = song {
                VStack(alignment: .leading, spacing: 20) {
                    // Song Information
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Song: " + song.title)
                            .font(.largeTitle)
                            .bold()
                        
                        if let composer = song.composer {
                            Label {
                                Text(composer)
                                    .font(.title3)
                            } icon: {
                                Image(systemName: "music.note.list")
                            }
                            .foregroundColor(.secondary)
                        }
                        
                        // Song Reference section - appears before Structure
                        if let songReference = song.songReference {
                            VStack(alignment: .leading, spacing: 8) {
                                Text("Information")
                                    .font(.headline)
                                Text(songReference)
                                    .font(.body)
                                    .foregroundColor(.secondary)
                            }
                            .padding()
                            .background(Color(.systemGray6))
                            .cornerRadius(10)
                        }
                        
                        if let structure = song.structure {
                            VStack(alignment: .leading, spacing: 8) {
                                Text("Structure")
                                    .font(.headline)
                                Text(structure)
                                    .font(.body)
                                    .foregroundColor(.secondary)
                            }
                            .padding()
                            .background(Color(.systemGray6))
                            .cornerRadius(10)
                        }
                    }
                    .padding()
                    
                    Divider()
                    
                    // Recordings Section
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Recordings (\(song.recordings?.count ?? 0))")
                            .font(.title2)
                            .bold()
                            .padding(.horizontal)
                        
                        if let recordings = song.recordings, !recordings.isEmpty {
                            ForEach(recordings) { recording in
                                NavigationLink(destination: RecordingDetailView(recordingId: recording.id)) {
                                    RecordingRowView(recording: recording)
                                }
                                .buttonStyle(.plain)
                            }
                        } else {
                            Text("No recordings available")
                                .foregroundColor(.secondary)
                                .padding()
                        }
                    }
                }
            } else {
                Text("Song not found")
                    .foregroundColor(.secondary)
                    .padding()
            }
        }
        .navigationBarTitleDisplayMode(.inline)
        .task {
            let networkManager = NetworkManager()
            song = await networkManager.fetchSongDetail(id: songId)
            isLoading = false
        }
    }
}

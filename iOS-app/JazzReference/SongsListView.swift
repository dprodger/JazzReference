//
//  SongsListView.swift
//  JazzReference
//
//  Created by Dave Rodger on 10/19/25.
//

import SwiftUI

struct SongsListView: View {
    @StateObject private var networkManager = NetworkManager()
    @State private var searchText = ""
    @State private var searchTask: Task<Void, Never>?
    
    var body: some View {
        NavigationStack {
            VStack {
                if networkManager.isLoading {
                    ProgressView("Loading songs...")
                        .padding()
                } else if let error = networkManager.errorMessage {
                    VStack(spacing: 16) {
                        Image(systemName: "exclamationmark.triangle")
                            .font(.system(size: 50))
                            .foregroundColor(.orange)
                        Text("Error")
                            .font(.headline)
                        Text(error)
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal)
                        Button("Retry") {
                            Task {
                                await networkManager.fetchSongs()
                            }
                        }
                        .buttonStyle(.borderedProminent)
                    }
                    .padding()
                } else {
                    List(networkManager.songs) { song in
                        NavigationLink(destination: SongDetailView(songId: song.id)) {
                            VStack(alignment: .leading, spacing: 4) {
                                Text(song.title)
                                    .font(.headline)
                                if let composer = song.composer {
                                    Text(composer)
                                        .font(.subheadline)
                                        .foregroundColor(.secondary)
                                }
                            }
                            .padding(.vertical, 4)
                        }
                    }
                    .listStyle(.insetGrouped)
                }
            }
            .navigationTitle("Jazz Standards")
            .searchable(text: $searchText, prompt: "Search songs")
            .onChange(of: searchText) { oldValue, newValue in
                searchTask?.cancel()
                searchTask = Task {
                    try? await Task.sleep(nanoseconds: 300_000_000)
                    if !Task.isCancelled {
                        await networkManager.fetchSongs(searchQuery: newValue)
                    }
                }
            }
            .task {
                await networkManager.fetchSongs()
            }
        }
    }
}

#Preview {
    SongsListView()
}

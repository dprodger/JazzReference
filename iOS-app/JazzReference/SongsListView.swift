//
//  SongsListView.swift
//  JazzReference
//
//  Updated with JazzTheme color palette
//

import SwiftUI

struct SongsListView: View {
    @StateObject private var networkManager = NetworkManager()
    @State private var searchText = ""
    @State private var searchTask: Task<Void, Never>?
    
    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                if networkManager.isLoading {
                    VStack {
                        Spacer()
                        ProgressView("Loading songs...")
                            .tint(JazzTheme.burgundy)
                        Spacer()
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .background(JazzTheme.backgroundLight)
                } else if let error = networkManager.errorMessage {
                    VStack(spacing: 16) {
                        Image(systemName: "exclamationmark.triangle")
                            .font(.system(size: 50))
                            .foregroundColor(JazzTheme.amber)
                        Text("Error")
                            .font(.headline)
                            .foregroundColor(JazzTheme.charcoal)
                        Text(error)
                            .font(.subheadline)
                            .foregroundColor(JazzTheme.smokeGray)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal)
                        Button("Retry") {
                            Task {
                                await networkManager.fetchSongs()
                            }
                        }
                        .buttonStyle(.borderedProminent)
                        .tint(JazzTheme.burgundy)
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .background(JazzTheme.backgroundLight)
                } else {
                    List(networkManager.songs) { song in
                        NavigationLink(destination: SongDetailView(songId: song.id)) {
                            VStack(alignment: .leading, spacing: 4) {
                                Text(song.title)
                                    .font(.headline)
                                    .foregroundColor(JazzTheme.charcoal)
                                if let composer = song.composer {
                                    Text(composer)
                                        .font(.subheadline)
                                        .foregroundColor(JazzTheme.smokeGray)
                                }
                            }
                            .padding(.vertical, 4)
                        }
                        .listRowBackground(JazzTheme.cardBackground)
                    }
                    .listStyle(.insetGrouped)
                    .scrollContentBackground(.hidden)
                    .background(JazzTheme.backgroundLight)
                }
            }
            .background(JazzTheme.backgroundLight)
            .navigationTitle("Songs")
            .toolbarBackground(JazzTheme.burgundy, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
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
        .tint(JazzTheme.burgundy)
    }
}

#Preview {
    SongsListView()
}

//
//  SongsListView.swift
//  JazzReferenceMac
//
//  macOS-specific songs list view with master-detail layout
//

import SwiftUI

struct SongsListView: View {
    @StateObject private var networkManager = NetworkManager()
    @EnvironmentObject var repertoireManager: RepertoireManager
    @EnvironmentObject var authManager: AuthenticationManager
    @State private var searchText = ""
    @State private var searchTask: Task<Void, Never>?
    @State private var selectedSongId: String?

    var body: some View {
        HSplitView {
            // Song list (left pane)
            VStack(spacing: 0) {
                // Repertoire selector
                HStack {
                    Image(systemName: "music.note.list")
                        .foregroundColor(JazzTheme.burgundy)
                    Text(repertoireManager.currentRepertoireDisplayName)
                        .font(.subheadline)
                        .fontWeight(.medium)
                    Spacer()
                    Menu("Change") {
                        ForEach(repertoireManager.repertoires) { repertoire in
                            Button(repertoire.name) {
                                repertoireManager.selectRepertoire(repertoire)
                            }
                        }
                    }
                    .menuStyle(.borderlessButton)
                    .foregroundColor(JazzTheme.burgundy)
                }
                .padding(.horizontal)
                .padding(.vertical, 8)
                .background(JazzTheme.amber.opacity(0.15))

                // Song list
                List(selection: $selectedSongId) {
                    ForEach(groupedSongs, id: \.0) { letter, songs in
                        Section(header: Text(letter).font(.headline).foregroundColor(JazzTheme.burgundy)) {
                            ForEach(songs) { song in
                                SongRowView(song: song)
                                    .tag(song.id)
                            }
                        }
                    }
                }
                .listStyle(.inset(alternatesRowBackgrounds: true))
            }
            .frame(minWidth: 300, idealWidth: 350)

            // Song detail (right pane)
            if let songId = selectedSongId {
                SongDetailView(songId: songId)
                    .frame(minWidth: 400)
            } else {
                VStack {
                    Image(systemName: "music.note")
                        .font(.system(size: 60))
                        .foregroundColor(JazzTheme.smokeGray.opacity(0.5))
                    Text("Select a song")
                        .font(.title2)
                        .foregroundColor(JazzTheme.smokeGray)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(JazzTheme.backgroundLight)
            }
        }
        .searchable(text: $searchText, prompt: "Search songs")
        .onChange(of: searchText) { _, newValue in
            searchTask?.cancel()
            searchTask = Task {
                try? await Task.sleep(nanoseconds: 300_000_000)
                if !Task.isCancelled {
                    await loadSongs()
                }
            }
        }
        .onChange(of: repertoireManager.selectedRepertoire) { _, _ in
            Task {
                await loadSongs()
            }
        }
        .task {
            await repertoireManager.loadRepertoires()
            await loadSongs()
        }
        .navigationTitle("Songs (\(networkManager.songs.count.formatted()))")
    }

    // MARK: - Helper Methods

    private var groupedSongs: [(String, [Song])] {
        let grouped = Dictionary(grouping: networkManager.songs) { song in
            let firstChar = song.title.prefix(1).uppercased()
            return firstChar.rangeOfCharacter(from: .letters) != nil ? firstChar : "#"
        }

        return grouped.sorted { lhs, rhs in
            if lhs.key == "#" { return false }
            if rhs.key == "#" { return true }
            return lhs.key < rhs.key
        }
    }

    private func loadSongs() async {
        if repertoireManager.selectedRepertoire.id != "all",
           let token = authManager.getAccessToken() {
            await networkManager.fetchSongsInRepertoire(
                repertoireId: repertoireManager.selectedRepertoire.id,
                searchQuery: searchText,
                authToken: token
            )
        } else {
            await networkManager.fetchSongsInRepertoire(
                repertoireId: repertoireManager.selectedRepertoire.id,
                searchQuery: searchText
            )
        }
    }
}

// MARK: - Song Row View

struct SongRowView: View {
    let song: Song

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
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
}

#Preview {
    SongsListView()
        .environmentObject(RepertoireManager())
        .environmentObject(AuthenticationManager())
}

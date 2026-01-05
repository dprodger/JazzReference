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
    @State private var showCreateRepertoire = false
    @State private var showLoginSheet = false

    var body: some View {
        HSplitView {
            // Song list (left pane)
            VStack(spacing: 0) {
                // Repertoire selector
                Group {
                    if authManager.isAuthenticated {
                        Menu {
                            ForEach(repertoireManager.repertoires) { repertoire in
                                Button(action: { repertoireManager.selectRepertoire(repertoire) }) {
                                    HStack {
                                        Text(repertoire.name)
                                        if repertoire.id == repertoireManager.selectedRepertoire.id {
                                            Image(systemName: "checkmark")
                                        }
                                    }
                                }
                            }

                            Divider()

                            Button(action: { showCreateRepertoire = true }) {
                                Label("Create New Repertoire", systemImage: "plus.circle")
                            }
                        } label: {
                            HStack(spacing: 6) {
                                Image(systemName: "music.note.list")
                                    .foregroundColor(JazzTheme.burgundy)
                                    .frame(width: 16)

                                Text(repertoireManager.currentRepertoireDisplayName)
                                    .font(JazzTheme.subheadline(weight: .medium))
                                    .foregroundColor(JazzTheme.charcoal)
                                    .lineLimit(1)

                                Spacer()

                                Image(systemName: "chevron.down")
                                    .font(.system(size: 10, weight: .bold))
                                    .foregroundColor(JazzTheme.charcoal)
                            }
                        }
                        .menuStyle(.borderlessButton)
                        .menuIndicator(.hidden)
                    } else {
                        HStack(spacing: 6) {
                            Image(systemName: "music.note.list")
                                .foregroundColor(JazzTheme.burgundy)
                                .frame(width: 16)

                            Text(repertoireManager.currentRepertoireDisplayName)
                                .font(JazzTheme.subheadline(weight: .medium))
                                .foregroundColor(JazzTheme.charcoal)
                                .lineLimit(1)

                            Spacer()

                            Button("Sign In") {
                                showLoginSheet = true
                            }
                            .font(JazzTheme.caption())
                            .buttonStyle(.plain)
                            .foregroundColor(JazzTheme.burgundy)
                        }
                    }
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 8)
                .background(JazzTheme.amber.opacity(0.3))

                // Search bar
                HStack {
                    Image(systemName: "magnifyingglass")
                        .foregroundColor(JazzTheme.smokeGray)
                    TextField("Search songs...", text: $searchText)
                        .textFieldStyle(.plain)
                        .font(JazzTheme.body())
                        .foregroundColor(JazzTheme.charcoal)
                    if !searchText.isEmpty {
                        Button(action: { searchText = "" }) {
                            Image(systemName: "xmark.circle.fill")
                                .foregroundColor(JazzTheme.smokeGray)
                        }
                        .buttonStyle(.plain)
                    }
                }
                .padding(8)
                .background(Color.white)
                .cornerRadius(8)
                .overlay(
                    RoundedRectangle(cornerRadius: 8)
                        .stroke(JazzTheme.smokeGray.opacity(0.3), lineWidth: 1)
                )
                .padding()
                .background(JazzTheme.cardBackground)

                // Song list
                List(selection: $selectedSongId) {
                    ForEach(groupedSongs, id: \.0) { letter, songs in
                        Section(header:
                            Text(letter)
                                .font(JazzTheme.headline())
                                .foregroundColor(JazzTheme.burgundy)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 4)
                                .background(JazzTheme.amber.opacity(0.3))
                                .cornerRadius(4)
                                .listRowInsets(EdgeInsets())
                        ) {
                            ForEach(songs) { song in
                                SongRowView(song: song, isSelected: selectedSongId == song.id)
                                    .tag(song.id)
                                    .listRowBackground(
                                        selectedSongId == song.id
                                            ? JazzTheme.burgundy
                                            : JazzTheme.backgroundLight
                                    )
                            }
                        }
                    }
                }
                .listStyle(.plain)
                .scrollContentBackground(.hidden)
                .background(JazzTheme.backgroundLight)
            }
            .frame(minWidth: 200, idealWidth: 250, maxWidth: 300)
            .background(JazzTheme.backgroundLight)

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
                        .font(JazzTheme.title2())
                        .foregroundColor(JazzTheme.smokeGray)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(JazzTheme.backgroundLight)
            }
        }
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
        .sheet(isPresented: $showCreateRepertoire) {
            MacCreateRepertoireView(repertoireManager: repertoireManager)
        }
        .sheet(isPresented: $showLoginSheet) {
            MacLoginView()
                .environmentObject(authManager)
        }
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
    var isSelected: Bool = false

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(song.title)
                .font(JazzTheme.headline())
                .foregroundStyle(isSelected ? Color.white : JazzTheme.charcoal)
            if let composer = song.composer {
                Text(composer)
                    .font(JazzTheme.subheadline())
                    .foregroundStyle(isSelected ? Color.white.opacity(0.85) : JazzTheme.smokeGray)
            }
        }
        .padding(.vertical, 4)
        .padding(.horizontal, 8)
    }
}

#Preview {
    SongsListView()
        .environmentObject(RepertoireManager())
        .environmentObject(AuthenticationManager())
}

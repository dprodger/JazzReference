//
//  SongsListView.swift
//  JazzReference
//
//  Enhanced with custom scrollable alphabet index (iOS Contacts-style)
//

import SwiftUI

struct SongsListView: View {
    @StateObject private var networkManager = NetworkManager()
    @State private var searchText = ""
    @State private var searchTask: Task<Void, Never>?
    
    // Computed property to group songs by first letter
    private var groupedSongs: [(String, [Song])] {
        let filtered = networkManager.songs
        
        // Group songs by first letter
        let grouped = Dictionary(grouping: filtered) { song in
            let firstChar = song.title.prefix(1).uppercased()
            return firstChar.rangeOfCharacter(from: .letters) != nil ? firstChar : "#"
        }
        
        return grouped.sorted { lhs, rhs in
            if lhs.key == "#" { return false }
            if rhs.key == "#" { return true }
            return lhs.key < rhs.key
        }
    }
    
    // Get all section letters for the index
    private var sectionLetters: [String] {
        groupedSongs.map { $0.0 }
    }
    
    var body: some View {
        NavigationStack {
            contentView
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
                    await networkManager.fetchSongs(searchQuery: searchText)
                }
        }
        .tint(JazzTheme.burgundy)
    }
    
    // Break up the body into separate views for compiler
    @ViewBuilder
    private var contentView: some View {
        VStack(spacing: 0) {
            if networkManager.isLoading {
                loadingView
            } else if let error = networkManager.errorMessage {
                errorView(error: error)
            } else {
                songsListView
            }
        }
    }
    
    private var loadingView: some View {
        VStack {
            Spacer()
            ProgressView("Loading songs...")
                .tint(JazzTheme.burgundy)
            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(JazzTheme.backgroundLight)
    }
    
    private func errorView(error: String) -> some View {
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
    }
    
    private var songsListView: some View {
        ScrollViewReader { proxy in
            List {
                ForEach(groupedSongs, id: \.0) { letter, songs in
                    Section(header: SectionHeaderView(letter: letter)) {
                        ForEach(songs) { song in
                            NavigationLink(destination: SongDetailView(songId: song.id)) {
                                songRowView(song: song)
                            }
                            .listRowBackground(JazzTheme.cardBackground)
                        }
                    }
                    .id(letter) // Anchor for scrolling
                }
            }
            .listStyle(.plain)
            .scrollContentBackground(.hidden)
            .background(JazzTheme.backgroundLight)
            .overlay(alignment: .trailing) {
                // Custom alphabet index overlay
                AlphabetIndexView(
                    letters: sectionLetters,
                    accentColor: JazzTheme.burgundy,
                    onTap: { letter in
                        withAnimation(.easeOut(duration: 0.2)) {
                            proxy.scrollTo(letter, anchor: .top)
                        }
                    }
                )
                .padding(.trailing, 4)
            }
        }
    }
    
    private func songRowView(song: Song) -> some View {
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
}

// Custom section header view
struct SectionHeaderView: View {
    let letter: String
    
    var body: some View {
        Text(letter)
            .font(.headline)
            .fontWeight(.bold)
            .foregroundColor(JazzTheme.burgundy)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.vertical, 8)
            .padding(.horizontal)
            .background(JazzTheme.backgroundLight.opacity(0.8))
    }
}

// Reusable custom alphabet index view - ONLY DEFINED HERE, NOT IN ArtistsListView
struct AlphabetIndexView: View {
    let letters: [String]
    var accentColor: Color = JazzTheme.burgundy
    let onTap: (String) -> Void
    
    var body: some View {
        VStack(spacing: 2) {
            ForEach(letters, id: \.self) { letter in
                Text(letter)
                    .font(.system(size: 11, weight: .medium))
                    .foregroundColor(accentColor)
                    .frame(width: 20, height: 16)
                    .background(
                        RoundedRectangle(cornerRadius: 4)
                            .fill(Color.white.opacity(0.7))
                    )
                    .onTapGesture {
                        onTap(letter)
                        // Haptic feedback
                        let generator = UIImpactFeedbackGenerator(style: .light)
                        generator.impactOccurred()
                    }
            }
        }
        .padding(.vertical, 8)
        .background(
            RoundedRectangle(cornerRadius: 8)
                .fill(JazzTheme.backgroundLight.opacity(0.95))
                .shadow(color: .black.opacity(0.1), radius: 2, x: -1, y: 0)
        )
    }
}

#Preview {
    SongsListView()
}

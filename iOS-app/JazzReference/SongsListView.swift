//
//  SongsListView.swift
//  JazzReference
//
//  Enhanced with repertoire filtering support
//

import SwiftUI

struct SongsListView: View {
    @StateObject private var networkManager = NetworkManager()
    @StateObject private var repertoireManager = RepertoireManager()
    @State private var searchText = ""
    @State private var searchTask: Task<Void, Never>?
    @State private var showRepertoirePicker = false
    
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
                .toolbar {
                    ToolbarItem(placement: .navigationBarTrailing) {
                        repertoireButton
                    }
                }
                .searchable(text: $searchText, prompt: "Search songs")
                .onChange(of: searchText) { oldValue, newValue in
                    searchTask?.cancel()
                    searchTask = Task {
                        try? await Task.sleep(nanoseconds: 300_000_000)
                        if !Task.isCancelled {
                            await loadSongs()
                        }
                    }
                }
                .onChange(of: repertoireManager.selectedRepertoire) { oldValue, newValue in
                    // Reload songs when repertoire changes
                    Task {
                        await loadSongs()
                    }
                }
                .task {
                    // Load repertoires first
                    await repertoireManager.loadRepertoires()
                    // Then load songs for the selected repertoire
                    await loadSongs()
                }
                .sheet(isPresented: $showRepertoirePicker) {
                    RepertoirePickerSheet(
                        repertoireManager: repertoireManager,
                        isPresented: $showRepertoirePicker
                    )
                }
        }
        .tint(JazzTheme.burgundy)
    }
    
    // MARK: - Repertoire Button
    
    private var repertoireButton: some View {
        Button(action: {
            showRepertoirePicker = true
        }) {
            HStack(spacing: 4) {
                Image(systemName: "music.note.list")
                    .font(.system(size: 16))
                if !repertoireManager.isShowingAllSongs {
                    Text(repertoireManager.selectedRepertoire.name)
                        .font(.system(size: 14, weight: .medium))
                        .lineLimit(1)
                }
            }
            .foregroundColor(.white)
            .padding(.horizontal, 8)
            .padding(.vertical, 6)
            .background(
                Capsule()
                    .fill(repertoireManager.isShowingAllSongs ?
                          Color.white.opacity(0.2) :
                          JazzTheme.amber)
            )
        }
    }
    
    // MARK: - Helper Methods
    
    private func loadSongs() async {
        await networkManager.fetchSongsInRepertoire(
            repertoireId: repertoireManager.selectedRepertoire.id,
            searchQuery: searchText
        )
    }
    
    // MARK: - Content Views
    
    @ViewBuilder
    private var contentView: some View {
        VStack(spacing: 0) {
            // Show current repertoire at top
            if !repertoireManager.isShowingAllSongs {
                currentRepertoireBanner
            }
            
            if networkManager.isLoading {
                loadingView
            } else if let error = networkManager.errorMessage {
                errorView(error: error)
            } else {
                songsListView
            }
        }
    }
    
    private var currentRepertoireBanner: some View {
        HStack {
            Image(systemName: "music.note.list")
                .foregroundColor(JazzTheme.burgundy)
            Text(repertoireManager.currentRepertoireDisplayName)
                .font(.subheadline)
                .fontWeight(.medium)
                .foregroundColor(JazzTheme.charcoal)
            Spacer()
            Button(action: {
                showRepertoirePicker = true
            }) {
                Text("Change")
                    .font(.subheadline)
                    .foregroundColor(JazzTheme.burgundy)
            }
        }
        .padding(.horizontal)
        .padding(.vertical, 8)
        .background(JazzTheme.amber.opacity(0.15))
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
                    await loadSongs()
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

// MARK: - Repertoire Picker Sheet

struct RepertoirePickerSheet: View {
    @ObservedObject var repertoireManager: RepertoireManager
    @Binding var isPresented: Bool
    
    var body: some View {
        NavigationStack {
            List {
                ForEach(repertoireManager.repertoires) { repertoire in
                    Button(action: {
                        repertoireManager.selectRepertoire(repertoire)
                        isPresented = false
                    }) {
                        HStack {
                            VStack(alignment: .leading, spacing: 4) {
                                Text(repertoire.name)
                                    .font(.headline)
                                    .foregroundColor(JazzTheme.charcoal)
                                
                                if let description = repertoire.description {
                                    Text(description)
                                        .font(.subheadline)
                                        .foregroundColor(JazzTheme.smokeGray)
                                        .lineLimit(2)
                                }
                                
                                if repertoire.id != "all" {
                                    Text("\(repertoire.songCount) songs")
                                        .font(.caption)
                                        .foregroundColor(JazzTheme.burgundy)
                                }
                            }
                            
                            Spacer()
                            
                            if repertoire.id == repertoireManager.selectedRepertoire.id {
                                Image(systemName: "checkmark.circle.fill")
                                    .foregroundColor(JazzTheme.burgundy)
                                    .font(.title3)
                            }
                        }
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    .listRowBackground(JazzTheme.cardBackground)
                }
            }
            .listStyle(.plain)
            .scrollContentBackground(.hidden)
            .background(JazzTheme.backgroundLight)
            .navigationTitle("Select Repertoire")
            .navigationBarTitleDisplayMode(.inline)
            .toolbarBackground(JazzTheme.burgundy, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") {
                        isPresented = false
                    }
                    .foregroundColor(.white)
                }
            }
        }
    }
}

// MARK: - Supporting Views

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

//
//  SongsListView.swift
//  JazzReference
//
//  Enhanced with repertoire filtering support
//

import SwiftUI

struct SongsListView: View {
    @StateObject private var networkManager = NetworkManager()
    @EnvironmentObject var repertoireManager: RepertoireManager
    @EnvironmentObject var authManager: AuthenticationManager
    @State private var searchText = ""
    @State private var searchTask: Task<Void, Never>?
    @State private var showRepertoirePicker = false
    @State private var showLoginPrompt = false
    
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
                .jazzNavigationBar(title: "Songs (\(networkManager.songs.count.formatted()))")
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
                .onChange(of: authManager.isAuthenticated) { wasAuthenticated, isAuthenticated in
                    // Dismiss login prompt when user successfully authenticates
                    if isAuthenticated && showLoginPrompt {
                        showLoginPrompt = false
                        // After dismissing login, show the repertoire picker
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                            showRepertoirePicker = true
                        }
                    }
                }
        }
        .tint(JazzTheme.burgundy)
    }
    
    // MARK: - Helper Methods
    
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
    
    // MARK: - Content Views
    
    @ViewBuilder
    private var contentView: some View {
        VStack(spacing: 0) {
            // Always show current repertoire header
            currentRepertoireBanner
            
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
                .font(JazzTheme.subheadline())
                .fontWeight(.medium)
                .foregroundColor(JazzTheme.charcoal)
            Spacer()
            Button(action: {
                if authManager.isAuthenticated {
                    showRepertoirePicker = true
                } else {
                    showLoginPrompt = true
                }
            }) {
                Text("Change")
                    .font(JazzTheme.subheadline())
                    .foregroundColor(JazzTheme.burgundy)
            }
            .sheet(isPresented: $showRepertoirePicker) {
                RepertoirePickerSheet(
                    repertoireManager: repertoireManager,
                    isPresented: $showRepertoirePicker
                )
                .presentationDetents([.medium, .large])
                .presentationDragIndicator(.visible)
            }
            .sheet(isPresented: $showLoginPrompt) {
                RepertoireLoginPromptView()
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
                .font(JazzTheme.headline())
                .foregroundColor(JazzTheme.charcoal)
            Text(error)
                .font(JazzTheme.subheadline())
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
                            NavigationLink(destination: SongDetailView(
                                                songId: song.id,
                                                allSongs: networkManager.songs,
                                                repertoireId: repertoireManager.selectedRepertoire.id
                                            )
                                                .environmentObject(repertoireManager)) {
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
                .font(JazzTheme.headline())
                .foregroundColor(JazzTheme.charcoal)
            if let composer = song.composer {
                Text(composer)
                    .font(JazzTheme.subheadline())
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
    @EnvironmentObject var authManager: AuthenticationManager
    @State private var showCreateRepertoire = false
    
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 0) {
                    ForEach(repertoireManager.repertoires) { repertoire in
                        Button(action: {
                            repertoireManager.selectRepertoire(repertoire)
                            isPresented = false
                        }) {
                            HStack {
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(repertoire.name)
                                        .font(JazzTheme.headline())
                                        .foregroundColor(JazzTheme.charcoal)
                                    
                                    if let description = repertoire.description {
                                        Text(description)
                                            .font(JazzTheme.subheadline())
                                            .foregroundColor(JazzTheme.smokeGray)
                                            .lineLimit(2)
                                    }
                                    
                                    if repertoire.id != "all" {
                                        Text("\(repertoire.songCount) songs")
                                            .font(JazzTheme.caption())
                                            .foregroundColor(JazzTheme.burgundy)
                                    }
                                }
                                
                                Spacer()
                                
                                if repertoire.id == repertoireManager.selectedRepertoire.id {
                                    Image(systemName: "checkmark.circle.fill")
                                        .foregroundColor(JazzTheme.burgundy)
                                        .font(JazzTheme.title3())
                                }
                            }
                            .contentShape(Rectangle())
                            .padding(.horizontal, 16)
                            .padding(.vertical, 12)
                            .frame(maxWidth: .infinity)
                            .background(
                                repertoire.id == repertoireManager.selectedRepertoire.id ?
                                    JazzTheme.burgundy.opacity(0.1) :
                                    JazzTheme.cardBackground
                            )
                        }
                        .buttonStyle(.plain)
                        
                        if repertoire.id != repertoireManager.repertoires.last?.id {
                            Divider()
                                .background(JazzTheme.smokeGray.opacity(0.3))
                        }
                    }
                    
                    // Add "Create New Repertoire" button for authenticated users
                    if authManager.isAuthenticated {
                        Divider()
                            .background(JazzTheme.smokeGray.opacity(0.3))
                        
                        Button(action: {
                            showCreateRepertoire = true
                        }) {
                            HStack {
                                Image(systemName: "plus.circle.fill")
                                    .foregroundColor(JazzTheme.burgundy)
                                    .font(JazzTheme.title3())
                                
                                Text("Create New Repertoire")
                                    .font(JazzTheme.headline())
                                    .foregroundColor(JazzTheme.burgundy)
                                
                                Spacer()
                            }
                            .contentShape(Rectangle())
                            .padding(.horizontal, 16)
                            .padding(.vertical, 12)
                            .frame(maxWidth: .infinity)
                            .background(JazzTheme.cardBackground)
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
            .background(JazzTheme.backgroundLight)
            .navigationTitle("Select Repertoire")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") {
                        isPresented = false
                    }
                    .foregroundColor(JazzTheme.burgundy)
                }
            }
            .sheet(isPresented: $showCreateRepertoire) {
                CreateRepertoireView(repertoireManager: repertoireManager)
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
            .font(JazzTheme.headline())
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
        .environmentObject(RepertoireManager())
        .environmentObject(AuthenticationManager())
}

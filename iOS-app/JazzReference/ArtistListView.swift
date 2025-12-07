//
//  ArtistsListView.swift
//  JazzReference
//
//  Enhanced with custom scrollable alphabet index (iOS Contacts-style)
//  Updated to handle non-Latin characters better
//

import SwiftUI

struct ArtistsListView: View {
    @StateObject private var networkManager = NetworkManager()
    @State private var searchText = ""
    @State private var searchTask: Task<Void, Never>?
    
    // Computed property to group artists by first letter
    private var groupedArtists: [(String, [Performer])] {
        let filtered = networkManager.performers
        
        let grouped = Dictionary(grouping: filtered) { performer in
            let name = performer.name
            let firstChar: String
            
            if let commaIndex = name.firstIndex(of: ",") {
                // "Last, First" format - use first letter of last name
                let lastName = name[..<commaIndex]
                firstChar = String(lastName.prefix(1)).uppercased()
            } else {
                // Single name - use first letter
                firstChar = String(name.prefix(1)).uppercased()
            }
            
            // Check if it's a Latin letter (A-Z)
            if firstChar.rangeOfCharacter(from: CharacterSet(charactersIn: "ABCDEFGHIJKLMNOPQRSTUVWXYZ")) != nil {
                return firstChar
            } else if firstChar.rangeOfCharacter(from: .letters) != nil {
                return "•" // Non-Latin letters (Cyrillic, Asian scripts, etc.)
            } else {
                return "#" // Numbers and symbols
            }
        }
        
        return grouped.sorted { lhs, rhs in
            // "#" always last
            if lhs.key == "#" { return false }
            if rhs.key == "#" { return true }
            // "•" second to last
            if lhs.key == "•" { return false }
            if rhs.key == "•" { return true }
            // Rest alphabetically
            return lhs.key < rhs.key
        }.map { (key, value) in
            (key, value.sorted { $0.name < $1.name })
        }
    }
    
    // Get all section letters for the index
    private var sectionLetters: [String] {
        groupedArtists.map { $0.0 }
    }
    
    var body: some View {
        NavigationStack {
            contentView
                .background(JazzTheme.backgroundLight)
                .navigationTitle("Artists (\(networkManager.performers.count))")
                .toolbarBackground(JazzTheme.amber, for: .navigationBar)
                .toolbarBackground(.visible, for: .navigationBar)
                .toolbarColorScheme(.dark, for: .navigationBar)
                .searchable(text: $searchText, prompt: "Search artists")
                .onChange(of: searchText) { oldValue, newValue in
                    searchTask?.cancel()
                    searchTask = Task {
                        try? await Task.sleep(nanoseconds: 300_000_000)
                        if !Task.isCancelled {
                            await networkManager.fetchPerformers(searchQuery: newValue)
                        }
                    }
                }
                .task {
                    await networkManager.fetchPerformers(searchQuery: searchText)
                }
        }
        .tint(JazzTheme.amber)
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
                artistsListView
            }
        }
    }
    
    private var loadingView: some View {
        VStack {
            Spacer()
            ProgressView("Loading artists...")
                .tint(JazzTheme.amber)
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
                    await networkManager.fetchPerformers()
                }
            }
            .buttonStyle(.borderedProminent)
            .tint(JazzTheme.amber)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(JazzTheme.backgroundLight)
    }
    
    private var artistsListView: some View {
        ScrollViewReader { proxy in
            List {
                ForEach(groupedArtists, id: \.0) { letter, artists in
                    Section(header: ArtistSectionHeaderView(letter: letter)) {
                        ForEach(artists) { performer in
                            NavigationLink(destination: PerformerDetailView(performerId: performer.id)) {
                                artistRowView(performer: performer)
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
                    accentColor: JazzTheme.amber,
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
    
    private func artistRowView(performer: Performer) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(performer.name)
                .font(.headline)
                .foregroundColor(JazzTheme.charcoal)
            
            if let instrument = performer.instrument {
                Text(instrument)
                    .font(.subheadline)
                    .foregroundColor(JazzTheme.smokeGray)
            }
        }
        .padding(.vertical, 4)
    }
}

// Custom section header view for artists
struct ArtistSectionHeaderView: View {
    let letter: String
    
    var body: some View {
        Text(letter)
            .font(.headline)
            .fontWeight(.bold)
            .foregroundColor(JazzTheme.amber)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.vertical, 8)
            .padding(.horizontal)
            .background(JazzTheme.backgroundLight.opacity(0.8))
    }
}

#Preview {
    ArtistsListView()
}

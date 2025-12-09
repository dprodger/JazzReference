//
//  RecordingsListView.swift
//  JazzReference
//
//  Created by Dave Rodger on 11/29/25.
//  Recording list view with search by artist, recording name, or album/release name
//

import SwiftUI

struct RecordingsListView: View {
    @StateObject private var networkManager = NetworkManager()
    @State private var searchText = ""
    @State private var searchTask: Task<Void, Never>?
    
    // Group recordings by album title for display
    private var groupedRecordings: [(String, [Recording])] {
        let filtered = networkManager.recordings
        
        let grouped = Dictionary(grouping: filtered) { recording in
            let albumTitle = recording.albumTitle ?? "Unknown Album"
            let firstChar = albumTitle.prefix(1).uppercased()
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
        groupedRecordings.map { $0.0 }
    }
    
    var body: some View {
        NavigationStack {
            contentView
                .background(JazzTheme.backgroundLight)
                .jazzNavigationBar(title: "Recordings (\(networkManager.recordingsCount))", color: JazzTheme.brass)
                .searchable(text: $searchText, prompt: "Artist, album, or song")
                .onChange(of: searchText) { oldValue, newValue in
                    searchTask?.cancel()
                    searchTask = Task {
                        try? await Task.sleep(nanoseconds: 300_000_000)
                        if !Task.isCancelled {
                            await networkManager.fetchRecordings(searchQuery: newValue)
                        }
                    }
                }
                .task {
                    await networkManager.fetchRecordingsCount()
                    await networkManager.fetchRecordings(searchQuery: searchText)
                }
        }
        .tint(JazzTheme.brass)
    }
    
    // MARK: - Content Views
    
    @ViewBuilder
    private var contentView: some View {
        VStack(spacing: 0) {
            // Search hint banner
            searchHintBanner
            
            if networkManager.isLoading {
                loadingView
            } else if let error = networkManager.errorMessage {
                errorView(error: error)
            } else if networkManager.recordings.isEmpty {
                emptyStateView
            } else {
                recordingsListView
            }
        }
    }
    
    private var searchHintBanner: some View {
        HStack(spacing: 8) {
            Image(systemName: "magnifyingglass")
                .foregroundColor(JazzTheme.brass)
                .font(JazzTheme.caption())
            Text("Search by artist, album name, or song title")
                .font(JazzTheme.caption())
                .foregroundColor(JazzTheme.smokeGray)
            Spacer()
        }
        .padding(.horizontal)
        .padding(.vertical, 8)
        .background(JazzTheme.brass.opacity(0.1))
    }
    
    private var loadingView: some View {
        VStack {
            Spacer()
            ProgressView("Loading recordings...")
                .tint(JazzTheme.brass)
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
                    await networkManager.fetchRecordings(searchQuery: searchText)
                }
            }
            .buttonStyle(.borderedProminent)
            .tint(JazzTheme.brass)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(JazzTheme.backgroundLight)
    }
    
    private var emptyStateView: some View {
        VStack(spacing: 16) {
            Image(systemName: searchText.isEmpty ? "magnifyingglass" : "opticaldisc")
                .font(.system(size: 60))
                .foregroundColor(JazzTheme.smokeGray.opacity(0.5))

            if searchText.isEmpty {
                Text("Search to Browse")
                    .font(JazzTheme.headline())
                    .foregroundColor(JazzTheme.charcoal)
                Text("Enter an artist, album, or song title to find recordings")
                    .font(JazzTheme.subheadline())
                    .foregroundColor(JazzTheme.smokeGray)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 32)
            } else {
                Text("No Results")
                    .font(JazzTheme.headline())
                    .foregroundColor(JazzTheme.charcoal)
                Text("No recordings match \"\(searchText)\"")
                    .font(JazzTheme.subheadline())
                    .foregroundColor(JazzTheme.smokeGray)
                    .multilineTextAlignment(.center)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(JazzTheme.backgroundLight)
    }
    
    private var recordingsListView: some View {
        ScrollViewReader { proxy in
            List {
                ForEach(groupedRecordings, id: \.0) { letter, recordings in
                    Section(header: RecordingSectionHeaderView(letter: letter)) {
                        ForEach(recordings) { recording in
                            NavigationLink(destination: RecordingDetailView(recordingId: recording.id)) {
                                recordingRowView(recording: recording)
                            }
                            .listRowBackground(JazzTheme.cardBackground)
                        }
                    }
                    .id(letter)
                }
            }
            .listStyle(.plain)
            .scrollContentBackground(.hidden)
            .background(JazzTheme.backgroundLight)
            .overlay(alignment: .trailing) {
                if sectionLetters.count > 5 {
                    AlphabetIndexView(
                        letters: sectionLetters,
                        accentColor: JazzTheme.brass,
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
    }
    
    private func recordingRowView(recording: Recording) -> some View {
        HStack(spacing: 12) {
            // Album artwork thumbnail
            if let albumArtUrl = recording.bestAlbumArtSmall ?? recording.bestAlbumArtMedium {
                AsyncImage(url: URL(string: albumArtUrl)) { phase in
                    switch phase {
                    case .empty:
                        ProgressView()
                            .frame(width: 50, height: 50)
                    case .success(let image):
                        image
                            .resizable()
                            .aspectRatio(contentMode: .fill)
                            .frame(width: 50, height: 50)
                            .clipped()
                            .cornerRadius(6)
                    case .failure:
                        albumPlaceholder
                    @unknown default:
                        albumPlaceholder
                    }
                }
            } else {
                albumPlaceholder
            }
            
            // Recording info
            VStack(alignment: .leading, spacing: 4) {
                Text(recording.albumTitle ?? "Unknown Album")
                    .font(JazzTheme.headline())
                    .foregroundColor(JazzTheme.charcoal)
                    .lineLimit(1)
                
                if let songTitle = recording.songTitle {
                    Text(songTitle)
                        .font(JazzTheme.subheadline())
                        .foregroundColor(JazzTheme.smokeGray)
                        .lineLimit(1)
                }
                
                // Show lead performer if available
                if let performers = recording.performers,
                   let leader = performers.first(where: { $0.role?.lowercased() == "leader" }) ?? performers.first {
                    Text(leader.name)
                        .font(JazzTheme.caption())
                        .foregroundColor(JazzTheme.brass)
                        .lineLimit(1)
                }
            }
            
            Spacer()
            
            // Year and canonical indicator
            VStack(alignment: .trailing, spacing: 4) {
                if let year = recording.recordingYear {
                    Text(String(year))
                        .font(JazzTheme.caption())
                        .foregroundColor(JazzTheme.smokeGray)
                }
                
                if recording.isCanonical == true {
                    Image(systemName: "star.fill")
                        .font(JazzTheme.caption())
                        .foregroundColor(JazzTheme.gold)
                }
            }
        }
        .padding(.vertical, 4)
    }
    
    private var albumPlaceholder: some View {
        Image(systemName: "opticaldisc")
            .font(JazzTheme.title2())
            .foregroundColor(JazzTheme.smokeGray.opacity(0.5))
            .frame(width: 50, height: 50)
            .background(JazzTheme.cardBackground)
            .cornerRadius(6)
    }
}

// MARK: - Section Header

struct RecordingSectionHeaderView: View {
    let letter: String
    
    var body: some View {
        Text(letter)
            .font(JazzTheme.headline())
            .fontWeight(.bold)
            .foregroundColor(JazzTheme.brass)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.vertical, 8)
            .padding(.horizontal)
            .background(JazzTheme.backgroundLight.opacity(0.8))
    }
}

#Preview {
    RecordingsListView()
}

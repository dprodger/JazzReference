//
//  MusicBrainzSearchSheet.swift
//  JazzReferenceMac
//
//  Search MusicBrainz for songs and import them into the database (macOS version)
//

import SwiftUI

struct MusicBrainzSearchSheet: View {
    let searchQuery: String
    let onSongImported: () -> Void

    @Environment(\.dismiss) private var dismiss
    @StateObject private var networkManager = NetworkManager()

    @State private var searchResults: [MusicBrainzWork] = []
    @State private var isSearching = false
    @State private var selectedWork: MusicBrainzWork?
    @State private var isImporting = false
    @State private var importError: String?
    @State private var importSuccess = false
    @State private var showImportConfirmation = false

    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Text("MusicBrainz Search")
                    .font(JazzTheme.title2())
                    .foregroundColor(JazzTheme.charcoal)
                Spacer()
                Button("Cancel") {
                    dismiss()
                }
                .keyboardShortcut(.escape)
            }
            .padding()
            .background(JazzTheme.backgroundLight)

            Divider()

            // Content
            if isSearching {
                loadingView
            } else if searchResults.isEmpty {
                emptyView
            } else {
                resultsList
            }
        }
        .frame(width: 500, height: 450)
        .background(JazzTheme.backgroundLight)
        .task {
            await performSearch()
        }
        .alert("Import Error", isPresented: .constant(importError != nil)) {
            Button("OK") {
                importError = nil
            }
        } message: {
            if let error = importError {
                Text(error)
            }
        }
        .alert("Song Imported", isPresented: $importSuccess) {
            Button("OK") {
                onSongImported()
                dismiss()
            }
        } message: {
            Text("The song has been added and is being enriched with recordings in the background.")
        }
        .alert("Import Song", isPresented: $showImportConfirmation) {
            Button("Import") {
                if let work = selectedWork {
                    Task {
                        await importSong(work)
                    }
                }
            }
            Button("Cancel", role: .cancel) {
                selectedWork = nil
            }
        } message: {
            if let work = selectedWork {
                Text("Import \"\(work.title)\" by \(work.composerDisplay)?")
            }
        }
    }

    // MARK: - Views

    private var loadingView: some View {
        VStack {
            Spacer()
            ProgressView("Searching MusicBrainz...")
                .progressViewStyle(.circular)
            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var emptyView: some View {
        VStack(spacing: 16) {
            Image(systemName: "magnifyingglass")
                .font(.system(size: 50))
                .foregroundColor(JazzTheme.smokeGray.opacity(0.5))

            Text("No Results Found")
                .font(JazzTheme.headline())
                .foregroundColor(JazzTheme.charcoal)

            Text("No works matching \"\(searchQuery)\" were found on MusicBrainz.")
                .font(JazzTheme.subheadline())
                .foregroundColor(JazzTheme.smokeGray)
                .multilineTextAlignment(.center)

            if let url = URL(string: "https://musicbrainz.org/search?query=\(searchQuery.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? searchQuery)&type=work") {
                Link(destination: url) {
                    HStack {
                        Image(systemName: "safari")
                        Text("Search on MusicBrainz.org")
                    }
                }
                .buttonStyle(.bordered)
                .padding(.top, 8)
            }
        }
        .padding()
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var resultsList: some View {
        VStack(spacing: 0) {
            // Results header
            HStack {
                Text("Results for \"\(searchQuery)\"")
                    .font(JazzTheme.subheadline())
                    .foregroundColor(JazzTheme.smokeGray)
                Spacer()
            }
            .padding(.horizontal)
            .padding(.vertical, 8)
            .background(JazzTheme.cream.opacity(0.5))

            // Results list
            List(searchResults) { work in
                workRowView(work: work)
                    .listRowBackground(
                        selectedWork?.id == work.id
                            ? JazzTheme.burgundy.opacity(0.15)
                            : Color.clear
                    )
                    .contentShape(Rectangle())
                    .onTapGesture {
                        selectedWork = work
                    }
            }
            .listStyle(.plain)
            .scrollContentBackground(.hidden)

            Divider()

            // Action bar
            HStack {
                if let work = selectedWork {
                    if let url = URL(string: work.musicbrainzUrl) {
                        Link(destination: url) {
                            HStack(spacing: 4) {
                                Image(systemName: "arrow.up.right.square")
                                Text("View on MusicBrainz")
                            }
                            .font(JazzTheme.subheadline())
                        }
                    }
                }

                Spacer()

                Button("Import Selected") {
                    showImportConfirmation = true
                }
                .buttonStyle(.borderedProminent)
                .tint(JazzTheme.burgundy)
                .disabled(selectedWork == nil || isImporting)
            }
            .padding()
            .background(JazzTheme.backgroundLight)
        }
    }

    private func workRowView(work: MusicBrainzWork) -> some View {
        HStack(alignment: .top, spacing: 12) {
            // Score indicator
            scoreIndicator(score: work.score)

            VStack(alignment: .leading, spacing: 2) {
                Text(work.title)
                    .font(JazzTheme.headline())
                    .foregroundColor(JazzTheme.charcoal)

                Text(work.composerDisplay)
                    .font(JazzTheme.subheadline())
                    .foregroundColor(JazzTheme.smokeGray)

                if let type = work.type {
                    Text(type)
                        .font(JazzTheme.caption())
                        .foregroundColor(JazzTheme.burgundy)
                }
            }

            Spacer()
        }
        .padding(.vertical, 4)
    }

    private func scoreIndicator(score: Int?) -> some View {
        let scoreValue = score ?? 0
        let color: Color = {
            if scoreValue >= 90 { return .green }
            if scoreValue >= 70 { return JazzTheme.amber }
            return JazzTheme.smokeGray
        }()

        return VStack(spacing: 2) {
            Circle()
                .fill(color)
                .frame(width: 8, height: 8)
            Text("\(scoreValue)")
                .font(.system(size: 10, weight: .medium))
                .foregroundColor(color)
        }
        .frame(width: 24)
    }

    // MARK: - Actions

    private func performSearch() async {
        isSearching = true
        searchResults = await networkManager.searchMusicBrainzWorks(query: searchQuery)
        isSearching = false
    }

    private func importSong(_ work: MusicBrainzWork) async {
        isImporting = true
        selectedWork = nil

        if let response = await networkManager.importSongFromMusicBrainz(work: work) {
            if response.success {
                importSuccess = true
            } else {
                importError = response.message
            }
        } else {
            importError = "Failed to import song. Please try again."
        }

        isImporting = false
    }
}

#Preview {
    MusicBrainzSearchSheet(
        searchQuery: "Autumn Leaves",
        onSongImported: {}
    )
}

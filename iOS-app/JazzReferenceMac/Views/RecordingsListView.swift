//
//  RecordingsListView.swift
//  JazzReferenceMac
//
//  macOS-specific recordings list view with master-detail layout
//

import SwiftUI

struct RecordingsListView: View {
    @StateObject private var networkManager = NetworkManager()
    @State private var searchText = ""
    @State private var searchTask: Task<Void, Never>?
    @State private var selectedRecordingId: String?

    var body: some View {
        HSplitView {
            // Recording list (left pane)
            VStack(spacing: 0) {
                // Info banner
                if networkManager.recordings.isEmpty && searchText.isEmpty {
                    HStack {
                        Image(systemName: "info.circle")
                            .foregroundColor(JazzTheme.burgundy)
                        Text("Search to browse \(networkManager.recordingsCount > 0 ? "\(networkManager.recordingsCount) " : "")recordings")
                            .font(.subheadline)
                        Spacer()
                    }
                    .padding()
                    .background(JazzTheme.amber.opacity(0.15))
                }

                
                
                List(selection: $selectedRecordingId) {
                    ForEach(networkManager.recordings) { recording in
                        RecordingRowView(recording: recording)
                            .tag(recording.id)
                    }
                }
                .listStyle(.inset(alternatesRowBackgrounds: true))
            }
            .frame(minWidth: 350, idealWidth: 400)

            // Recording detail (right pane)
            if let recordingId = selectedRecordingId {
                RecordingDetailView(recordingId: recordingId)
                    .frame(minWidth: 400)
            } else {
                VStack {
                    Image(systemName: "opticaldisc")
                        .font(.system(size: 60))
                        .foregroundColor(JazzTheme.smokeGray.opacity(0.5))
                    Text("Select a recording")
                        .font(.title2)
                        .foregroundColor(JazzTheme.smokeGray)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(JazzTheme.backgroundLight)
            }
        }
        .searchable(text: $searchText, prompt: "Search by artist, album, or song")
        .onChange(of: searchText) { _, newValue in
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
        }
        .navigationTitle("Recordings (\(networkManager.recordingsCount.formatted()))")
    }
}

// MARK: - Recording Row View

struct RecordingRowView: View {
    let recording: Recording

    var body: some View {
        HStack(spacing: 12) {
            // Album art
            AsyncImage(url: URL(string: recording.bestAlbumArtSmall ?? "")) { image in
                image
                    .resizable()
                    .aspectRatio(contentMode: .fill)
            } placeholder: {
                Rectangle()
                    .fill(JazzTheme.cardBackground)
                    .overlay {
                        Image(systemName: "music.note")
                            .foregroundColor(JazzTheme.smokeGray)
                    }
            }
            .frame(width: 50, height: 50)
            .cornerRadius(4)

            VStack(alignment: .leading, spacing: 2) {
                Text(recording.albumTitle ?? "Unknown Album")
                    .font(.headline)
                    .foregroundColor(JazzTheme.charcoal)
                    .lineLimit(1)

                if let songTitle = recording.songTitle {
                    Text(songTitle)
                        .font(.subheadline)
                        .foregroundColor(JazzTheme.smokeGray)
                        .lineLimit(1)
                }

                HStack(spacing: 4) {
                    if let year = recording.recordingYear {
                        Text("\(year)")
                            .font(.caption)
                            .foregroundColor(JazzTheme.smokeGray)
                    }

                    if let label = recording.label {
                        Text("•")
                            .font(.caption)
                            .foregroundColor(JazzTheme.smokeGray)
                        Text(label)
                            .font(.caption)
                            .foregroundColor(JazzTheme.smokeGray)
                            .lineLimit(1)
                    }
                }
            }

            Spacer()

            // Authority badge
            if recording.hasAuthority, let badgeText = recording.authorityBadgeText {
                AuthorityBadge(text: badgeText, source: recording.primaryAuthoritySource)
            }
        }
        .padding(.vertical, 4)
    }
}

#Preview {
    RecordingsListView()
}

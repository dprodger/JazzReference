//
//  RecordingsListView.swift
//  JazzReferenceMac
//
//  macOS-specific recordings list view with master-detail layout and advanced filtering
//

import SwiftUI

// MARK: - Search Scope

enum RecordingSearchScope: String, CaseIterable, Identifiable {
    case all = "All"
    case artist = "Artist"
    case album = "Album"
    case song = "Song"

    var id: String { rawValue }
}

// MARK: - Availability Filter

enum RecordingAvailabilityFilter: String, CaseIterable, Identifiable {
    case all = "All"
    case playable = "Playable"
    case spotify = "Spotify"
    case appleMusic = "Apple Music"

    var id: String { rawValue }

    var icon: String {
        switch self {
        case .all: return "music.note.list"
        case .playable: return "play.circle"
        case .spotify: return "play.circle.fill"
        case .appleMusic: return "play.circle.fill"
        }
    }

    var iconColor: Color {
        switch self {
        case .all: return JazzTheme.smokeGray
        case .playable: return JazzTheme.burgundy
        case .spotify: return .green
        case .appleMusic: return .pink
        }
    }
}

// MARK: - Main View

struct RecordingsListView: View {
    @StateObject private var networkManager = NetworkManager()
    @State private var searchText = ""
    @State private var searchTask: Task<Void, Never>?
    @State private var selectedRecordingId: String?

    // Filter state
    @State private var searchScope: RecordingSearchScope = .all
    @State private var availabilityFilter: RecordingAvailabilityFilter = .all

    // Filtered recordings based on scope and availability
    private var filteredRecordings: [Recording] {
        var results = networkManager.recordings

        // Apply search scope filter (client-side refinement)
        if !searchText.isEmpty && searchScope != .all {
            switch searchScope {
            case .all:
                break
            case .artist:
                results = results.filter { recording in
                    let artistNames = recording.performers?.map { $0.name.lowercased() } ?? []
                    return artistNames.contains { $0.contains(searchText.lowercased()) }
                }
            case .album:
                results = results.filter { recording in
                    recording.albumTitle?.lowercased().contains(searchText.lowercased()) ?? false
                }
            case .song:
                results = results.filter { recording in
                    recording.songTitle?.lowercased().contains(searchText.lowercased()) ?? false
                }
            }
        }

        // Apply availability filter
        switch availabilityFilter {
        case .all:
            break
        case .playable:
            results = results.filter { $0.isPlayable }
        case .spotify:
            results = results.filter { $0.hasSpotifyAvailable }
        case .appleMusic:
            results = results.filter { $0.hasAppleMusicAvailable }
        }

        return results
    }

    private var hasActiveFilters: Bool {
        searchScope != .all || availabilityFilter != .all
    }

    var body: some View {
        HSplitView {
            // Recording list (left pane)
            VStack(spacing: 0) {
                // Filter toolbar
                filterToolbar

                // Results count when filtered
                if !networkManager.recordings.isEmpty && hasActiveFilters {
                    HStack {
                        Text("\(filteredRecordings.count) of \(networkManager.recordings.count) recordings")
                            .font(JazzTheme.caption())
                            .foregroundColor(JazzTheme.smokeGray)
                        Spacer()
                        Button("Clear Filters") {
                            clearFilters()
                        }
                        .font(JazzTheme.caption())
                        .foregroundColor(JazzTheme.burgundy)
                        .buttonStyle(.plain)
                    }
                    .padding(.horizontal)
                    .padding(.vertical, 8)
                    .background(JazzTheme.cardBackground)
                }

                // No results message
                if !searchText.isEmpty && filteredRecordings.isEmpty && !networkManager.isLoading {
                    VStack(spacing: 12) {
                        Image(systemName: "magnifyingglass")
                            .font(.system(size: 32))
                            .foregroundColor(JazzTheme.smokeGray.opacity(0.5))
                        Text("No recordings match your filters")
                            .font(JazzTheme.subheadline())
                            .foregroundColor(JazzTheme.smokeGray)
                        if hasActiveFilters {
                            Button("Clear Filters") {
                                clearFilters()
                            }
                            .buttonStyle(.link)
                        }
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .background(JazzTheme.backgroundLight)
                } else {
                    ScrollView {
                        LazyVStack(spacing: 0) {
                            ForEach(filteredRecordings) { recording in
                                RecordingRowView(recording: recording)
                                    .padding(.horizontal, 12)
                                    .padding(.vertical, 6)
                                    .background(selectedRecordingId == recording.id ? JazzTheme.burgundy.opacity(0.15) : Color.clear)
                                    .contentShape(Rectangle())
                                    .onTapGesture {
                                        selectedRecordingId = recording.id
                                    }
                                Divider()
                                    .padding(.leading, 74)
                            }
                        }
                    }
                    .background(Color.white)
                }
            }
            .frame(minWidth: 200, idealWidth: 250, maxWidth: 300)
            .background(JazzTheme.backgroundLight)
            .environment(\.colorScheme, .light)

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
                    await networkManager.fetchRecordings(searchQuery: newValue)
                }
            }
        }
    }

    // MARK: - Filter Toolbar

    @ViewBuilder
    private var filterToolbar: some View {
        VStack(spacing: 8) {
            MacSearchBar(
                text: $searchText,
                placeholder: "Search recordings...",
                backgroundColor: JazzTheme.brass
            )

            // Availability row
            HStack(spacing: 12) {
                Text("Availability:")
                    .font(JazzTheme.subheadline())
                    .foregroundColor(.white)

                // Availability filter menu
                Menu {
                    ForEach(RecordingAvailabilityFilter.allCases) { filter in
                        Button(action: { availabilityFilter = filter }) {
                            HStack {
                                Image(systemName: filter.icon)
                                    .foregroundColor(filter.iconColor)
                                Text(filter.rawValue)
                                if availabilityFilter == filter {
                                    Spacer()
                                    Image(systemName: "checkmark")
                                }
                            }
                        }
                    }
                } label: {
                    HStack(spacing: 4) {
                        Image(systemName: availabilityFilter.icon)
                            .foregroundColor(availabilityFilter == .all ? JazzTheme.charcoal : availabilityFilter.iconColor)
                        Text(availabilityFilter.rawValue)
                            .font(JazzTheme.subheadline())
                            .foregroundColor(JazzTheme.charcoal)
                        Image(systemName: "chevron.down")
                            .font(JazzTheme.caption2())
                            .foregroundColor(JazzTheme.charcoal)
                    }
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
                    .background(Color.white)
                    .cornerRadius(8)
                    .overlay(
                        RoundedRectangle(cornerRadius: 8)
                            .stroke(JazzTheme.smokeGray.opacity(0.3), lineWidth: 1)
                    )
                }
                .menuStyle(.borderlessButton)

                // Clear button when availability filter is active
                if availabilityFilter != .all {
                    Button(action: { availabilityFilter = .all }) {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundColor(.white)
                            .font(.system(size: 16))
                    }
                    .buttonStyle(.plain)
                    .help("Clear availability filter")
                }

                Spacer()
            }
            .padding(.horizontal)

            // Search scope picker
            HStack(spacing: 12) {
                Text("Search in:")
                    .font(JazzTheme.subheadline())
                    .foregroundColor(.white)

                Picker("", selection: $searchScope) {
                    ForEach(RecordingSearchScope.allCases) { scope in
                        Text(scope.rawValue).tag(scope)
                    }
                }
                .pickerStyle(.segmented)
                .labelsHidden()

                Spacer()
            }
            .padding(.horizontal)
            .padding(.bottom, 8)
        }
        .background(JazzTheme.brass)
        .environment(\.colorScheme, .light)
    }

    // MARK: - Helpers

    private func clearFilters() {
        searchScope = .all
        availabilityFilter = .all
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
                    .font(JazzTheme.headline())
                    .foregroundColor(JazzTheme.charcoal)
                    .lineLimit(1)

                if let songTitle = recording.songTitle {
                    Text(songTitle)
                        .font(JazzTheme.subheadline())
                        .foregroundColor(JazzTheme.smokeGray)
                        .lineLimit(1)
                }

                HStack(spacing: 4) {
                    if let year = recording.recordingYear {
                        Text("\(year)")
                            .font(JazzTheme.caption())
                            .foregroundColor(JazzTheme.smokeGray)
                    }

                    if let label = recording.label {
                        Text("•")
                            .font(JazzTheme.caption())
                            .foregroundColor(JazzTheme.smokeGray)
                        Text(label)
                            .font(JazzTheme.caption())
                            .foregroundColor(JazzTheme.smokeGray)
                            .lineLimit(1)
                    }
                }
            }

            Spacer()

            // Streaming indicators
            HStack(spacing: 4) {
                if recording.hasSpotifyAvailable {
                    Image(systemName: "play.circle.fill")
                        .foregroundColor(.green)
                        .font(JazzTheme.caption())
                }
                if recording.hasAppleMusicAvailable {
                    Image(systemName: "play.circle.fill")
                        .foregroundColor(.pink)
                        .font(JazzTheme.caption())
                }
            }

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

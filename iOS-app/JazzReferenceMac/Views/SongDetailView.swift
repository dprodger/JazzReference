//
//  SongDetailView.swift
//  JazzReferenceMac
//
//  macOS-specific song detail view
//

import SwiftUI

// MARK: - Recording Filter Enum
enum SongRecordingFilter: String, CaseIterable, Identifiable {
    case all = "All"
    case playable = "Playable"
    case withSpotify = "Spotify"
    case withAppleMusic = "Apple Music"

    var id: String { rawValue }

    var displayName: String { rawValue }

    var icon: String {
        switch self {
        case .all: return "music.note.list"
        case .playable: return "play.circle"
        case .withSpotify: return "play.circle.fill"
        case .withAppleMusic: return "play.circle.fill"
        }
    }

    var iconColor: Color {
        switch self {
        case .all: return JazzTheme.smokeGray
        case .playable: return JazzTheme.burgundy
        case .withSpotify: return .green
        case .withAppleMusic: return .pink
        }
    }
}

struct SongDetailView: View {
    let songId: String
    @State private var song: Song?
    @State private var isLoading = true
    @State private var isRecordingsLoading = true
    @State private var sortOrder: RecordingSortOrder = .year
    @State private var selectedRecordingId: String?
    @State private var selectedFilter: SongRecordingFilter = .all
    @EnvironmentObject var repertoireManager: RepertoireManager

    @StateObject private var networkManager = NetworkManager()

    var body: some View {
        ScrollView {
            if isLoading {
                ThemedProgressView(message: "Loading...")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .padding(.top, 100)
            } else if let song = song {
                VStack(alignment: .leading, spacing: 24) {
                    // Header
                    songHeader(song)

                    Divider()

                    // Song info
                    songInfo(song)

                    // External references
                    if !song.externalReferencesList.isEmpty {
                        externalReferencesSection(song)
                    }

                    // Recordings
                    if let recordings = song.recordings, !recordings.isEmpty {
                        recordingsSection(recordings)
                    }
                }
                .padding()
            } else {
                Text("Song not found")
                    .foregroundColor(.secondary)
                    .padding(.top, 100)
            }
        }
        .background(JazzTheme.backgroundLight)
        .task(id: songId) {
            await loadSong()
        }
        .onChange(of: sortOrder) { _, _ in
            Task {
                await reloadRecordings()
            }
        }
    }

    // MARK: - View Components

    @ViewBuilder
    private func songHeader(_ song: Song) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(song.title)
                .font(.largeTitle)
                .fontWeight(.bold)
                .foregroundColor(JazzTheme.charcoal)

            if let composer = song.composer {
                Text("by \(composer)")
                    .font(.title3)
                    .foregroundColor(JazzTheme.smokeGray)
            }
        }
    }

    @ViewBuilder
    private func songInfo(_ song: Song) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            if let structure = song.structure {
                DetailRow(icon: "doc.text", label: "Structure", value: structure)
            }

            if let recordingCount = song.recordingCount {
                DetailRow(icon: "opticaldisc", label: "Recordings", value: "\(recordingCount)")
            }
        }
    }

    @ViewBuilder
    private func externalReferencesSection(_ song: Song) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("External References")
                .font(.headline)
                .foregroundColor(JazzTheme.charcoal)

            ForEach(song.externalReferencesList) { reference in
                Link(destination: URL(string: reference.url)!) {
                    HStack {
                        Image(systemName: reference.iconName)
                            .foregroundColor(JazzTheme.burgundy)
                            .frame(width: 24)
                        Text(reference.displayName)
                            .foregroundColor(JazzTheme.charcoal)
                        Spacer()
                        Image(systemName: "arrow.up.right.square")
                            .foregroundColor(JazzTheme.smokeGray)
                            .font(.caption)
                    }
                    .padding(.vertical, 8)
                    .padding(.horizontal, 12)
                    .background(JazzTheme.cardBackground)
                    .cornerRadius(8)
                }
                .buttonStyle(.plain)
            }
        }
    }

    // MARK: - Filtered Recordings
    private func filteredRecordings(_ recordings: [Recording]) -> [Recording] {
        switch selectedFilter {
        case .all:
            return recordings
        case .playable:
            return recordings.filter { $0.isPlayable }
        case .withSpotify:
            return recordings.filter { $0.hasSpotifyAvailable }
        case .withAppleMusic:
            return recordings.filter { $0.hasAppleMusicAvailable }
        }
    }

    @ViewBuilder
    private func recordingsSection(_ recordings: [Recording]) -> some View {
        let filtered = filteredRecordings(recordings)

        VStack(alignment: .leading, spacing: 12) {
            // Header with count, filter, and sort
            HStack {
                Text("Recordings")
                    .font(.headline)
                    .foregroundColor(JazzTheme.charcoal)

                Text("(\(filtered.count))")
                    .font(.subheadline)
                    .foregroundColor(JazzTheme.smokeGray)

                Spacer()

                // Filter menu
                Menu {
                    ForEach(SongRecordingFilter.allCases) { filter in
                        Button(action: { selectedFilter = filter }) {
                            HStack {
                                Image(systemName: filter.icon)
                                    .foregroundColor(filter.iconColor)
                                Text(filter.displayName)
                                if selectedFilter == filter {
                                    Spacer()
                                    Image(systemName: "checkmark")
                                }
                            }
                        }
                    }
                } label: {
                    HStack(spacing: 4) {
                        Image(systemName: selectedFilter.icon)
                            .foregroundColor(selectedFilter.iconColor)
                        Text(selectedFilter.displayName)
                            .font(.subheadline)
                        Image(systemName: "chevron.down")
                            .font(.caption2)
                    }
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
                    .background(selectedFilter == .all ? JazzTheme.cardBackground : selectedFilter.iconColor.opacity(0.15))
                    .cornerRadius(8)
                }
                .menuStyle(.borderlessButton)

                // Sort picker
                Picker("Sort by", selection: $sortOrder) {
                    ForEach(RecordingSortOrder.allCases) { order in
                        Text(order.displayName).tag(order)
                    }
                }
                .pickerStyle(.segmented)
                .frame(width: 150)
            }

            // Recordings list
            if isRecordingsLoading {
                VStack(spacing: 12) {
                    ProgressView()
                        .scaleEffect(1.2)
                    Text("Loading recordings...")
                        .font(.subheadline)
                        .foregroundColor(JazzTheme.smokeGray)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 40)
            } else if filtered.isEmpty {
                VStack(spacing: 12) {
                    Image(systemName: "music.note.slash")
                        .font(.system(size: 40))
                        .foregroundColor(JazzTheme.smokeGray.opacity(0.5))
                    Text("No recordings match the current filter")
                        .font(.subheadline)
                        .foregroundColor(JazzTheme.smokeGray)
                    Button("Clear Filter") {
                        selectedFilter = .all
                    }
                    .buttonStyle(.link)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 40)
            } else {
                ForEach(filtered) { recording in
                    RecordingCard(recording: recording)
                        .contentShape(Rectangle())
                        .onTapGesture {
                            selectedRecordingId = recording.id
                        }
                }
            }
        }
        .sheet(isPresented: Binding(
            get: { selectedRecordingId != nil },
            set: { if !$0 { selectedRecordingId = nil } }
        )) {
            if let recordingId = selectedRecordingId {
                RecordingDetailView(recordingId: recordingId)
                    .frame(minWidth: 600, minHeight: 500)
            }
        }
    }

    // MARK: - Data Loading

    private func loadSong() async {
        isLoading = true
        isRecordingsLoading = true

        // Phase 1: Load summary (fast) - includes song metadata, featured recordings
        let fetchedSong = await networkManager.fetchSongSummary(id: songId)
        song = fetchedSong
        isLoading = false

        // Phase 2: Load all recordings with full streaming data
        if let recordings = await networkManager.fetchSongRecordings(id: songId, sortBy: sortOrder) {
            song?.recordings = recordings
        }
        isRecordingsLoading = false
    }

    private func reloadRecordings() async {
        isRecordingsLoading = true
        if let recordings = await networkManager.fetchSongRecordings(id: songId, sortBy: sortOrder) {
            song?.recordings = recordings
        }
        isRecordingsLoading = false
    }
}

// MARK: - Recording Card

struct RecordingCard: View {
    let recording: Recording
    @State private var isHovering = false

    var body: some View {
        HStack(spacing: 16) {
            // Album art
            AsyncImage(url: URL(string: recording.bestAlbumArtMedium ?? "")) { image in
                image
                    .resizable()
                    .aspectRatio(contentMode: .fill)
            } placeholder: {
                Rectangle()
                    .fill(JazzTheme.cardBackground)
                    .overlay {
                        Image(systemName: "music.note")
                            .font(.title)
                            .foregroundColor(JazzTheme.smokeGray)
                    }
            }
            .frame(width: 80, height: 80)
            .cornerRadius(8)

            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    if recording.isCanonical == true {
                        Image(systemName: "star.fill")
                            .foregroundColor(JazzTheme.gold)
                            .font(.caption)
                    }

                    Text(recording.albumTitle ?? "Unknown Album")
                        .font(.headline)
                        .foregroundColor(JazzTheme.charcoal)
                }

                // Performers
                if let performers = recording.performers {
                    let leaderNames = performers
                        .filter { $0.role == "leader" }
                        .map { $0.name }
                        .joined(separator: ", ")

                    if !leaderNames.isEmpty {
                        Text(leaderNames)
                            .font(.subheadline)
                            .foregroundColor(JazzTheme.smokeGray)
                    }
                }

                HStack(spacing: 8) {
                    if let year = recording.recordingYear {
                        Text("\(year)")
                            .font(.caption)
                            .foregroundColor(JazzTheme.smokeGray)
                    }

                    if let label = recording.label {
                        Text("•")
                            .foregroundColor(JazzTheme.smokeGray)
                        Text(label)
                            .font(.caption)
                            .foregroundColor(JazzTheme.smokeGray)
                    }
                }
            }

            Spacer()

            // Streaming buttons
            HStack(spacing: 8) {
                if let spotifyUrl = recording.bestSpotifyUrl,
                   let url = URL(string: spotifyUrl) {
                    Link(destination: url) {
                        Image(systemName: "play.circle.fill")
                            .font(.title2)
                            .foregroundColor(.green)
                    }
                    .buttonStyle(.plain)
                    .help("Open in Spotify")
                }

                if let youtubeUrl = recording.youtubeUrl,
                   let url = URL(string: youtubeUrl) {
                    Link(destination: url) {
                        Image(systemName: "play.rectangle.fill")
                            .font(.title2)
                            .foregroundColor(.red)
                    }
                    .buttonStyle(.plain)
                    .help("Watch on YouTube")
                }
            }
        }
        .padding()
        .background(isHovering ? JazzTheme.cardBackground.opacity(0.7) : JazzTheme.cardBackground)
        .cornerRadius(10)
        .overlay(
            RoundedRectangle(cornerRadius: 10)
                .stroke(isHovering ? JazzTheme.burgundy.opacity(0.5) : Color.clear, lineWidth: 2)
        )
        .onHover { hovering in
            isHovering = hovering
        }
        .animation(.easeInOut(duration: 0.15), value: isHovering)
    }
}

#Preview {
    SongDetailView(songId: "preview-id")
        .environmentObject(RepertoireManager())
}

//
//  SongDetailView.swift
//  JazzReferenceMac
//
//  macOS-specific song detail view
//

import SwiftUI

struct SongDetailView: View {
    let songId: String
    @State private var song: Song?
    @State private var isLoading = true
    @State private var sortOrder: RecordingSortOrder = .year
    @EnvironmentObject var repertoireManager: RepertoireManager

    private let networkManager = NetworkManager()

    var body: some View {
        ScrollView {
            if isLoading {
                ProgressView("Loading...")
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
        .task {
            await loadSong()
        }
        .onChange(of: sortOrder) { _, _ in
            Task {
                await loadSong()
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

    @ViewBuilder
    private func recordingsSection(_ recordings: [Recording]) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Recordings (\(recordings.count.formatted()))")
                    .font(.headline)
                    .foregroundColor(JazzTheme.charcoal)

                Spacer()

                Picker("Sort by", selection: $sortOrder) {
                    ForEach(RecordingSortOrder.allCases) { order in
                        Text(order.displayName).tag(order)
                    }
                }
                .pickerStyle(.segmented)
                .frame(width: 150)
            }

            ForEach(recordings) { recording in
                RecordingCard(recording: recording)
            }
        }
    }

    // MARK: - Data Loading

    private func loadSong() async {
        isLoading = true
        song = await networkManager.fetchSongDetail(id: songId, sortBy: sortOrder)
        isLoading = false
    }
}

// MARK: - Recording Card

struct RecordingCard: View {
    let recording: Recording

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
        .background(JazzTheme.cardBackground)
        .cornerRadius(10)
    }
}

#Preview {
    SongDetailView(songId: "preview-id")
        .environmentObject(RepertoireManager())
}

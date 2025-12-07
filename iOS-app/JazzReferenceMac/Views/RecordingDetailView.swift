//
//  RecordingDetailView.swift
//  JazzReferenceMac
//
//  macOS-specific recording detail view
//

import SwiftUI

struct RecordingDetailView: View {
    let recordingId: String
    @State private var recording: Recording?
    @State private var isLoading = true

    private let networkManager = NetworkManager()

    var body: some View {
        ScrollView {
            if isLoading {
                ProgressView("Loading...")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .padding(.top, 100)
            } else if let recording = recording {
                VStack(alignment: .leading, spacing: 24) {
                    // Header with album art
                    recordingHeader(recording)

                    Divider()

                    // Recording info
                    recordingInfo(recording)

                    // Streaming links
                    streamingSection(recording)

                    // Performers
                    if let performers = recording.performers, !performers.isEmpty {
                        performersSection(performers)
                    }

                    // Releases
                    if let releases = recording.releases, !releases.isEmpty {
                        releasesSection(releases)
                    }
                }
                .padding()
            } else {
                Text("Recording not found")
                    .foregroundColor(.secondary)
                    .padding(.top, 100)
            }
        }
        .background(JazzTheme.backgroundLight)
        .task {
            await loadRecording()
        }
    }

    // MARK: - View Components

    @ViewBuilder
    private func recordingHeader(_ recording: Recording) -> some View {
        HStack(alignment: .top, spacing: 24) {
            // Album art
            AsyncImage(url: URL(string: recording.bestAlbumArtLarge ?? recording.bestAlbumArtMedium ?? "")) { image in
                image
                    .resizable()
                    .aspectRatio(contentMode: .fill)
            } placeholder: {
                Rectangle()
                    .fill(JazzTheme.cardBackground)
                    .overlay {
                        Image(systemName: "music.note")
                            .font(.system(size: 50))
                            .foregroundColor(JazzTheme.smokeGray)
                    }
            }
            .frame(width: 200, height: 200)
            .cornerRadius(12)
            .shadow(radius: 4)

            VStack(alignment: .leading, spacing: 8) {
                // Song title
                if let songTitle = recording.songTitle {
                    Text(songTitle)
                        .font(.largeTitle)
                        .fontWeight(.bold)
                        .foregroundColor(JazzTheme.charcoal)
                }

                // Album title
                HStack {
                    if recording.isCanonical == true {
                        Image(systemName: "star.fill")
                            .foregroundColor(JazzTheme.gold)
                    }
                    Text(recording.albumTitle ?? "Unknown Album")
                        .font(.title2)
                        .foregroundColor(JazzTheme.smokeGray)
                }

                // Leader names
                if let performers = recording.performers {
                    let leaders = performers.filter { $0.role == "leader" }
                    if !leaders.isEmpty {
                        Text(leaders.map { $0.name }.joined(separator: ", "))
                            .font(.title3)
                            .foregroundColor(JazzTheme.brass)
                    }
                }

                // Year and label
                HStack(spacing: 12) {
                    if let year = recording.recordingYear {
                        Label("\(year)", systemImage: "calendar")
                            .font(.subheadline)
                            .foregroundColor(JazzTheme.smokeGray)
                    }

                    if let label = recording.label {
                        Label(label, systemImage: "building.2")
                            .font(.subheadline)
                            .foregroundColor(JazzTheme.smokeGray)
                    }
                }
                .padding(.top, 4)

                // Authority badge
                if recording.hasAuthority, let badgeText = recording.authorityBadgeText {
                    AuthorityBadge(text: badgeText, source: recording.primaryAuthoritySource)
                        .padding(.top, 8)
                }
            }

            Spacer()
        }
    }

    @ViewBuilder
    private func recordingInfo(_ recording: Recording) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            if let notes = recording.notes, !notes.isEmpty {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Notes")
                        .font(.headline)
                        .foregroundColor(JazzTheme.charcoal)
                    Text(notes)
                        .font(.body)
                        .foregroundColor(JazzTheme.charcoal)
                }
            }

            if let date = recording.recordingDate {
                DetailRow(icon: "calendar", label: "Recording Date", value: date)
            }
        }
    }

    @ViewBuilder
    private func streamingSection(_ recording: Recording) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Listen")
                .font(.headline)
                .foregroundColor(JazzTheme.charcoal)

            HStack(spacing: 16) {
                if let spotifyUrl = recording.bestSpotifyUrl,
                   let url = URL(string: spotifyUrl) {
                    Link(destination: url) {
                        HStack {
                            Image(systemName: "play.circle.fill")
                                .font(.title2)
                            Text("Spotify")
                        }
                        .padding(.horizontal, 16)
                        .padding(.vertical, 10)
                        .background(Color.green)
                        .foregroundColor(.white)
                        .cornerRadius(8)
                    }
                    .buttonStyle(.plain)
                }

                if let youtubeUrl = recording.youtubeUrl,
                   let url = URL(string: youtubeUrl) {
                    Link(destination: url) {
                        HStack {
                            Image(systemName: "play.rectangle.fill")
                                .font(.title2)
                            Text("YouTube")
                        }
                        .padding(.horizontal, 16)
                        .padding(.vertical, 10)
                        .background(Color.red)
                        .foregroundColor(.white)
                        .cornerRadius(8)
                    }
                    .buttonStyle(.plain)
                }

                if let appleMusicUrl = recording.appleMusicUrl,
                   let url = URL(string: appleMusicUrl) {
                    Link(destination: url) {
                        HStack {
                            Image(systemName: "applelogo")
                                .font(.title2)
                            Text("Apple Music")
                        }
                        .padding(.horizontal, 16)
                        .padding(.vertical, 10)
                        .background(Color.pink)
                        .foregroundColor(.white)
                        .cornerRadius(8)
                    }
                    .buttonStyle(.plain)
                }
            }
        }
    }

    @ViewBuilder
    private func performersSection(_ performers: [Performer]) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Personnel (\(performers.count))")
                .font(.headline)
                .foregroundColor(JazzTheme.charcoal)

            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                ForEach(performers) { performer in
                    HStack {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(performer.name)
                                .font(.subheadline)
                                .fontWeight(.medium)
                                .foregroundColor(JazzTheme.charcoal)

                            if let instrument = performer.instrument {
                                Text(instrument)
                                    .font(.caption)
                                    .foregroundColor(JazzTheme.smokeGray)
                            }
                        }

                        Spacer()

                        if let role = performer.role {
                            Text(role.capitalized)
                                .font(.caption2)
                                .padding(.horizontal, 6)
                                .padding(.vertical, 2)
                                .background(role == "leader" ? JazzTheme.burgundy : JazzTheme.brass.opacity(0.3))
                                .foregroundColor(role == "leader" ? .white : JazzTheme.charcoal)
                                .cornerRadius(4)
                        }
                    }
                    .padding(10)
                    .background(JazzTheme.cardBackground)
                    .cornerRadius(8)
                }
            }
        }
    }

    @ViewBuilder
    private func releasesSection(_ releases: [Release]) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Releases (\(releases.count))")
                .font(.headline)
                .foregroundColor(JazzTheme.charcoal)

            ForEach(releases) { release in
                HStack(spacing: 12) {
                    // Release cover art
                    AsyncImage(url: URL(string: release.coverArtSmall ?? "")) { image in
                        image
                            .resizable()
                            .aspectRatio(contentMode: .fill)
                    } placeholder: {
                        Rectangle()
                            .fill(JazzTheme.cardBackground)
                            .overlay {
                                Image(systemName: "opticaldisc")
                                    .foregroundColor(JazzTheme.smokeGray)
                            }
                    }
                    .frame(width: 50, height: 50)
                    .cornerRadius(4)

                    VStack(alignment: .leading, spacing: 2) {
                        Text(release.title)
                            .font(.subheadline)
                            .fontWeight(.medium)
                            .foregroundColor(JazzTheme.charcoal)
                            .lineLimit(1)

                        HStack(spacing: 8) {
                            Text(release.yearDisplay)
                                .font(.caption)
                                .foregroundColor(JazzTheme.smokeGray)

                            if let format = release.formatName {
                                Text("•")
                                    .foregroundColor(JazzTheme.smokeGray)
                                Text(format)
                                    .font(.caption)
                                    .foregroundColor(JazzTheme.smokeGray)
                            }

                            if let label = release.label {
                                Text("•")
                                    .foregroundColor(JazzTheme.smokeGray)
                                Text(label)
                                    .font(.caption)
                                    .foregroundColor(JazzTheme.smokeGray)
                                    .lineLimit(1)
                            }
                        }
                    }

                    Spacer()

                    // Spotify indicator
                    if release.hasSpotify {
                        Image(systemName: "checkmark.circle.fill")
                            .foregroundColor(.green)
                            .help("Available on Spotify")
                    }
                }
                .padding(10)
                .background(JazzTheme.cardBackground)
                .cornerRadius(8)
            }
        }
    }

    // MARK: - Data Loading

    private func loadRecording() async {
        isLoading = true
        recording = await networkManager.fetchRecordingDetail(id: recordingId)
        isLoading = false
    }
}

#Preview {
    RecordingDetailView(recordingId: "preview-id")
}

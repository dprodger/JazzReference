//
//  BackingTracksSection.swift
//  Approach Note
//
//  Collapsible section displaying backing track videos
//  Uses a single shared YouTube player presented in a sheet for better performance
//

import SwiftUI
import YouTubePlayerKit

// MARK: - Backing Tracks Section

struct BackingTracksSection: View {
    let videos: [Video]

    @State private var isSectionExpanded: Bool = true
    @State private var selectedVideo: Video?

    var body: some View {
        if !videos.isEmpty {
            Divider()
                .padding(.horizontal)
                .padding(.top, 16)

            HStack(spacing: 0) {
                Spacer().frame(width: 16)

                VStack(alignment: .leading, spacing: 0) {
                    DisclosureGroup(
                        isExpanded: $isSectionExpanded,
                    content: {
                        VStack(alignment: .leading, spacing: 12) {
                            ForEach(videos) { video in
                                VideoRowView(video: video) {
                                    selectedVideo = video
                                }
                            }
                        }
                        .padding(.top, 12)
                    },
                    label: {
                        HStack {
                            Image(systemName: "play.circle.fill")
                                .foregroundColor(ApproachNoteTheme.green)
                            Text("Backing Tracks")
                                .font(ApproachNoteTheme.title2())
                                .bold()
                                .foregroundColor(ApproachNoteTheme.charcoal)

                            Spacer()

                            Text("\(videos.count)")
                                .font(ApproachNoteTheme.subheadline())
                                .foregroundColor(ApproachNoteTheme.smokeGray)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 4)
                                .background(ApproachNoteTheme.green.opacity(0.1))
                                .cornerRadius(6)
                        }
                        .padding(.vertical, 12)
                    }
                )
                .tint(ApproachNoteTheme.green)
            }

            Spacer().frame(width: 16)
            }
            .background(ApproachNoteTheme.backgroundLight)
            .sheet(item: $selectedVideo) { video in
                VideoPlayerSheet(video: video)
            }
        }
    }
}

// MARK: - Video Row View

struct VideoRowView: View {
    let video: Video
    let onTap: () -> Void

    var body: some View {
        Button(action: onTap) {
            HStack(spacing: 12) {
                // Play button thumbnail
                ZStack {
                    RoundedRectangle(cornerRadius: 8)
                        .fill(ApproachNoteTheme.green.opacity(0.15))
                        .frame(width: 80, height: 45)

                    Image(systemName: "play.fill")
                        .font(.system(size: 20))
                        .foregroundColor(ApproachNoteTheme.green)
                }

                // Video info
                VStack(alignment: .leading, spacing: 4) {
                    // Video title
                    Text(video.title ?? "Backing Track")
                        .font(ApproachNoteTheme.headline())
                        .foregroundColor(ApproachNoteTheme.charcoal)
                        .lineLimit(2)
                        .multilineTextAlignment(.leading)

                    // Metadata badges
                    HStack(spacing: 8) {
                        if let duration = video.durationSeconds {
                            HStack(spacing: 4) {
                                Image(systemName: "clock")
                                    .foregroundColor(ApproachNoteTheme.brass)
                                    .font(ApproachNoteTheme.caption())
                                Text(formatDuration(duration))
                                    .font(ApproachNoteTheme.subheadline())
                                    .foregroundColor(ApproachNoteTheme.smokeGray)
                            }
                        }

                        if let tempo = video.tempo {
                            HStack(spacing: 4) {
                                Image(systemName: "metronome")
                                    .foregroundColor(ApproachNoteTheme.brass)
                                    .font(ApproachNoteTheme.caption())
                                Text("\(tempo) BPM")
                                    .font(ApproachNoteTheme.subheadline())
                                    .foregroundColor(ApproachNoteTheme.smokeGray)
                            }
                        }

                        if let key = video.keySignature {
                            HStack(spacing: 4) {
                                Image(systemName: "music.note")
                                    .foregroundColor(ApproachNoteTheme.brass)
                                    .font(ApproachNoteTheme.caption())
                                Text(key)
                                    .font(ApproachNoteTheme.subheadline())
                                    .foregroundColor(ApproachNoteTheme.smokeGray)
                            }
                        }
                    }
                }

                Spacer()

                // Chevron indicator
                Image(systemName: "chevron.right")
                    .font(ApproachNoteTheme.subheadline())
                    .foregroundColor(ApproachNoteTheme.smokeGray)
            }
            .padding()
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(ApproachNoteTheme.cardBackground)
            .cornerRadius(10)
            .padding(.horizontal)
        }
        .buttonStyle(.plain)
    }

    private func formatDuration(_ seconds: Int) -> String {
        let minutes = seconds / 60
        let remainingSeconds = seconds % 60
        return String(format: "%d:%02d", minutes, remainingSeconds)
    }
}

// MARK: - Video Player Sheet

struct VideoPlayerSheet: View {
    let video: Video
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // YouTube Player
                if let youtubeUrl = video.youtubeUrl {
                    YouTubePlayerView(.init(stringLiteral: youtubeUrl)) { state in
                        switch state {
                        case .idle:
                            ZStack {
                                Rectangle()
                                    .fill(Color.black)
                                ProgressView()
                                    .tint(.white)
                            }
                        case .ready:
                            EmptyView()
                        case .error(let error):
                            ContentUnavailableView(
                                "Error",
                                systemImage: "exclamationmark.triangle.fill",
                                description: Text(verbatim: "YouTube player couldn't be loaded: \(error)")
                            )
                        }
                    }
                    .aspectRatio(16/9, contentMode: .fit)
                } else {
                    ContentUnavailableView(
                        "No Video",
                        systemImage: "video.slash",
                        description: Text("This backing track has no video URL")
                    )
                    .frame(height: 200)
                }

                // Video details
                VStack(alignment: .leading, spacing: 12) {
                    if let description = video.description, !description.isEmpty {
                        Text(description)
                            .font(ApproachNoteTheme.body())
                            .foregroundColor(ApproachNoteTheme.smokeGray)
                    }

                    if let duration = video.durationSeconds {
                        HStack(spacing: 4) {
                            Image(systemName: "clock")
                                .foregroundColor(ApproachNoteTheme.brass)
                            Text("Duration: \(formatDuration(duration))")
                                .font(ApproachNoteTheme.subheadline())
                                .foregroundColor(ApproachNoteTheme.smokeGray)
                        }
                    }

                    if let tempo = video.tempo {
                        HStack(spacing: 4) {
                            Image(systemName: "metronome")
                                .foregroundColor(ApproachNoteTheme.brass)
                            Text("Tempo: \(tempo) BPM")
                                .font(ApproachNoteTheme.subheadline())
                                .foregroundColor(ApproachNoteTheme.smokeGray)
                        }
                    }

                    if let key = video.keySignature {
                        HStack(spacing: 4) {
                            Image(systemName: "music.note")
                                .foregroundColor(ApproachNoteTheme.brass)
                            Text("Key: \(key)")
                                .font(ApproachNoteTheme.subheadline())
                                .foregroundColor(ApproachNoteTheme.smokeGray)
                        }
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding()

                Spacer()
            }
            .background(ApproachNoteTheme.backgroundLight)
            .navigationTitle(video.title ?? "Backing Track")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") {
                        dismiss()
                    }
                }
            }
        }
    }

    private func formatDuration(_ seconds: Int) -> String {
        let minutes = seconds / 60
        let remainingSeconds = seconds % 60
        return String(format: "%d:%02d", minutes, remainingSeconds)
    }
}

// MARK: - Preview

#Preview {
    ScrollView {
        BackingTracksSection(videos: [
            Video(
                id: "preview-1",
                songId: "song-1",
                recordingId: nil,
                youtubeUrl: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                title: "All of Me - Backing Track in C",
                description: "Professional backing track for practice",
                videoType: "backing_track",
                durationSeconds: 300,
                tempo: 130,
                keySignature: "C Major",
                createdAt: nil,
                updatedAt: nil
            ),
            Video(
                id: "preview-2",
                songId: "song-1",
                recordingId: nil,
                youtubeUrl: "https://www.youtube.com/watch?v=abc123",
                title: "All of Me - Slow Tempo",
                description: nil,
                videoType: "backing_track",
                durationSeconds: 360,
                tempo: 100,
                keySignature: nil,
                createdAt: nil,
                updatedAt: nil
            )
        ])
    }
}

//
//  BackingTracksSection.swift
//  JazzReference
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
                                .foregroundColor(JazzTheme.green)
                            Text("Backing Tracks")
                                .font(JazzTheme.title2())
                                .bold()
                                .foregroundColor(JazzTheme.charcoal)

                            Spacer()

                            Text("\(videos.count)")
                                .font(JazzTheme.subheadline())
                                .foregroundColor(JazzTheme.smokeGray)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 4)
                                .background(JazzTheme.green.opacity(0.1))
                                .cornerRadius(6)
                        }
                        .padding(.vertical, 12)
                    }
                )
                .tint(JazzTheme.green)
            }

            Spacer().frame(width: 16)
            }
            .background(JazzTheme.backgroundLight)
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
                        .fill(JazzTheme.green.opacity(0.15))
                        .frame(width: 80, height: 45)

                    Image(systemName: "play.fill")
                        .font(.system(size: 20))
                        .foregroundColor(JazzTheme.green)
                }

                // Video info
                VStack(alignment: .leading, spacing: 4) {
                    // Video title
                    Text(video.title ?? "Backing Track")
                        .font(JazzTheme.headline())
                        .foregroundColor(JazzTheme.charcoal)
                        .lineLimit(2)
                        .multilineTextAlignment(.leading)

                    // Duration if available
                    if let duration = video.durationSeconds {
                        HStack(spacing: 4) {
                            Image(systemName: "clock")
                                .foregroundColor(JazzTheme.brass)
                                .font(JazzTheme.caption())
                            Text(formatDuration(duration))
                                .font(JazzTheme.subheadline())
                                .foregroundColor(JazzTheme.smokeGray)
                        }
                    }
                }

                Spacer()

                // Chevron indicator
                Image(systemName: "chevron.right")
                    .font(JazzTheme.subheadline())
                    .foregroundColor(JazzTheme.smokeGray)
            }
            .padding()
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(JazzTheme.cardBackground)
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
                                description: Text("YouTube player couldn't be loaded: \(error)")
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
                            .font(JazzTheme.body())
                            .foregroundColor(JazzTheme.smokeGray)
                    }

                    if let duration = video.durationSeconds {
                        HStack(spacing: 4) {
                            Image(systemName: "clock")
                                .foregroundColor(JazzTheme.brass)
                            Text("Duration: \(formatDuration(duration))")
                                .font(JazzTheme.subheadline())
                                .foregroundColor(JazzTheme.smokeGray)
                        }
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding()

                Spacer()
            }
            .background(JazzTheme.backgroundLight)
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
                createdAt: nil,
                updatedAt: nil
            )
        ])
    }
}

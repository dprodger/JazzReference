//
//  YouTubeViews.swift
//  MusicBrainzImporter
//
//  Views for importing YouTube videos as transcriptions or backing tracks
//

import SwiftUI

// MARK: - YouTube Type Selection View

struct YouTubeTypeSelectionView: View {
    let youtubeData: YouTubeData
    let onSelectType: (YouTubeVideoType) -> Void
    let onCancel: () -> Void

    var body: some View {
        VStack(spacing: 20) {
            // Header
            VStack(spacing: 12) {
                Image(systemName: "play.rectangle.fill")
                    .font(.system(size: 50))
                    .foregroundColor(.red)

                Text("Import YouTube Video")
                    .font(.title2)
                    .bold()

                Text("What type of video is this?")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            }
            .padding(.top, 40)

            // Video Info Card
            VStack(alignment: .leading, spacing: 8) {
                Text(youtubeData.title)
                    .font(.headline)
                    .lineLimit(2)

                if let channelName = youtubeData.channelName {
                    HStack(spacing: 4) {
                        Image(systemName: "person.circle")
                            .foregroundColor(.secondary)
                            .font(.caption)
                        Text(channelName)
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                    }
                }
            }
            .padding()
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color(.systemGray6))
            .cornerRadius(12)
            .padding(.horizontal)

            // Type Selection Buttons
            VStack(spacing: 16) {
                Text("Select video type:")
                    .font(.subheadline)
                    .foregroundColor(.secondary)

                // Transcription Option
                Button(action: { onSelectType(.transcription) }) {
                    HStack(spacing: 16) {
                        Image(systemName: YouTubeVideoType.transcription.iconName)
                            .font(.title2)
                            .foregroundColor(.blue)
                            .frame(width: 40)

                        VStack(alignment: .leading, spacing: 4) {
                            Text(YouTubeVideoType.transcription.displayName)
                                .font(.headline)
                                .foregroundColor(.primary)

                            Text(YouTubeVideoType.transcription.description)
                                .font(.caption)
                                .foregroundColor(.secondary)
                                .lineLimit(2)
                        }

                        Spacer()

                        Image(systemName: "chevron.right")
                            .foregroundColor(.secondary)
                    }
                    .padding()
                    .background(Color(.systemGray6))
                    .cornerRadius(12)
                }

                // Backing Track Option
                Button(action: { onSelectType(.backingTrack) }) {
                    HStack(spacing: 16) {
                        Image(systemName: YouTubeVideoType.backingTrack.iconName)
                            .font(.title2)
                            .foregroundColor(.green)
                            .frame(width: 40)

                        VStack(alignment: .leading, spacing: 4) {
                            Text(YouTubeVideoType.backingTrack.displayName)
                                .font(.headline)
                                .foregroundColor(.primary)

                            Text(YouTubeVideoType.backingTrack.description)
                                .font(.caption)
                                .foregroundColor(.secondary)
                                .lineLimit(2)
                        }

                        Spacer()

                        Image(systemName: "chevron.right")
                            .foregroundColor(.secondary)
                    }
                    .padding()
                    .background(Color(.systemGray6))
                    .cornerRadius(12)
                }
            }
            .padding(.horizontal)

            Spacer()

            // Cancel Button
            Button(action: onCancel) {
                Text("Cancel")
                    .font(.headline)
                    .foregroundColor(.blue)
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(Color(.systemGray6))
                    .cornerRadius(12)
            }
            .padding(.horizontal)
            .padding(.bottom, 20)
        }
        .background(Color.white)
    }
}

#Preview {
    YouTubeTypeSelectionView(
        youtubeData: YouTubeData(
            videoId: "abc123",
            title: "Chet Baker - Born to be Blue (Solo Transcription)",
            url: "https://www.youtube.com/watch?v=abc123",
            channelName: "Jazz Transcriptions",
            description: "A transcription of Chet Baker's solo on Born to be Blue",
            videoType: nil,
            songId: nil,
            recordingId: nil
        ),
        onSelectType: { type in print("Selected: \(type)") },
        onCancel: { print("Cancelled") }
    )
}

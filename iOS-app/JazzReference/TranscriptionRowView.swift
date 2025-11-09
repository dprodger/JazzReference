// TranscriptionRowView.swift
// Standalone component for displaying solo transcriptions
// Add this to your project if you prefer a separate file

import SwiftUI

// MARK: - Transcription Row View
struct TranscriptionRowView: View {
    let transcription: SoloTranscription
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            // Album/Recording title
            if let albumTitle = transcription.albumTitle {
                Text(albumTitle)
                    .font(.headline)
                    .foregroundColor(JazzTheme.charcoal)
            } else {
                Text("Solo Transcription")
                    .font(.headline)
                    .foregroundColor(JazzTheme.charcoal)
            }
            
            // Recording details
            HStack(spacing: 12) {
                if let year = transcription.recordingYear {
                    HStack(spacing: 4) {
                        Image(systemName: "calendar")
                            .foregroundColor(JazzTheme.brass)
                            .font(.caption)
                        Text(String(format: "%d", year))
                            .font(.subheadline)
                            .foregroundColor(JazzTheme.smokeGray)
                    }
                }
                
                if let label = transcription.label {
                    HStack(spacing: 4) {
                        Image(systemName: "opticaldisc")
                            .foregroundColor(JazzTheme.brass)
                            .font(.caption)
                        Text(label)
                            .font(.subheadline)
                            .foregroundColor(JazzTheme.smokeGray)
                    }
                }
            }
            
            // YouTube link button
            if let youtubeUrl = transcription.youtubeUrl,
               let url = URL(string: youtubeUrl) {
                Link(destination: url) {
                    HStack {
                        Image(systemName: "play.rectangle.fill")
                            .foregroundColor(.white)
                        Text("Watch Transcription on YouTube")
                            .font(.subheadline)
                            .foregroundColor(.white)
                    }
                    .padding(.vertical, 8)
                    .padding(.horizontal, 12)
                    .background(Color.red)
                    .cornerRadius(8)
                }
                .padding(.top, 4)
            }
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(JazzTheme.cardBackground)
        .cornerRadius(10)
        .padding(.horizontal)
    }
}

// MARK: - Preview
#Preview {
    VStack {
        TranscriptionRowView(
            transcription: SoloTranscription(
                id: "preview-1",
                songId: "song-1",
                recordingId: "rec-1",
                youtubeUrl: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                createdAt: nil,
                updatedAt: nil,
                songTitle: "Autumn Leaves",
                albumTitle: "Kind of Blue",
                recordingYear: 1959,
                composer: "Joseph Kosma",
                label: "Columbia"
            )
        )
        
        TranscriptionRowView(
            transcription: SoloTranscription(
                id: "preview-2",
                songId: "song-1",
                recordingId: "rec-2",
                youtubeUrl: "https://www.youtube.com/watch?v=abc123",
                createdAt: nil,
                updatedAt: nil,
                songTitle: "Blue in Green",
                albumTitle: nil,
                recordingYear: nil,
                composer: nil,
                label: nil
            )
        )
    }
}

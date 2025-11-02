//
//  RecordingRowView.swift
//  JazzReference
//
//  Updated with album artwork support
//

import SwiftUI

struct RecordingRowView: View {
    let recording: Recording
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            // Album artwork
            ZStack(alignment: .topTrailing) {
                if let albumArtUrl = recording.albumArtMedium ?? recording.albumArtSmall {
                    AsyncImage(url: URL(string: albumArtUrl)) { phase in
                        switch phase {
                        case .empty:
                            ProgressView()
                                .frame(width: 150, height: 150)
                        case .success(let image):
                            image
                                .resizable()
                                .aspectRatio(contentMode: .fill)
                                .frame(width: 150, height: 150)
                                .clipped()
                        case .failure:
                            Image(systemName: "music.note")
                                .font(.largeTitle)
                                .foregroundColor(.secondary)
                                .frame(width: 150, height: 150)
                                .background(Color(.systemGray5))
                        @unknown default:
                            EmptyView()
                        }
                    }
                } else {
                    Image(systemName: "opticaldisc")
                        .font(.largeTitle)
                        .foregroundColor(.secondary)
                        .frame(width: 150, height: 150)
                        .background(Color(.systemGray5))
                }
                
                if recording.isCanonical == true {
                    Image(systemName: "star.fill")
                        .foregroundColor(.yellow)
                        .font(.caption)
                        .padding(6)
                        .background(Color.black.opacity(0.6))
                        .clipShape(Circle())
                        .padding(6)
                }
            }
            .cornerRadius(8)
            .frame(width: 150)
            
            // Album title
            Text(recording.albumTitle ?? "Unknown Album")
                .font(.subheadline)
                .fontWeight(.medium)
                .lineLimit(2)
                .frame(width: 150, alignment: .leading)
            
            // Year
            if let year = recording.recordingYear {
                Text(String(format: "%d", year))
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .frame(width: 150, alignment: .leading)
            }
        }
        .frame(width: 150)
    }
}

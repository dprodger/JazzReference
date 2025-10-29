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
        HStack(spacing: 12) {
            // Album artwork thumbnail
            if let albumArtUrl = recording.albumArtMedium ?? recording.albumArtSmall {
                AsyncImage(url: URL(string: albumArtUrl)) { phase in
                    switch phase {
                    case .empty:
                        ProgressView()
                            .frame(width: 60, height: 60)
                    case .success(let image):
                        image
                            .resizable()
                            .aspectRatio(contentMode: .fill)
                            .frame(width: 60, height: 60)
                            .cornerRadius(6)
                    case .failure:
                        Image(systemName: "music.note")
                            .font(.title2)
                            .foregroundColor(.secondary)
                            .frame(width: 60, height: 60)
                            .background(Color(.systemGray5))
                            .cornerRadius(6)
                    @unknown default:
                        EmptyView()
                    }
                }
                .frame(width: 60, height: 60)
            } else {
                // Placeholder when no artwork available
                Image(systemName: "opticaldisc")
                    .font(.title2)
                    .foregroundColor(.secondary)
                    .frame(width: 60, height: 60)
                    .background(Color(.systemGray5))
                    .cornerRadius(6)
            }
            
            // Recording info
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    if recording.isCanonical == true {
                        Image(systemName: "star.fill")
                            .foregroundColor(.yellow)
                            .font(.caption)
                    }
                    
                    Text(recording.albumTitle ?? "Unknown Album")
                        .font(.headline)
                }
                
                if let year = recording.recordingYear {
                    Text("\(year)")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
                
                if let label = recording.label {
                    Text(label)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
            
            Spacer()
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(10)
        .padding(.horizontal)
    }
}

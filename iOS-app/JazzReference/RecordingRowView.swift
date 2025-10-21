//
//  RecordingRowView.swift
//  JazzReference
//
//  Updated with Spotify icon indicator
//

import SwiftUI
import Combine

struct RecordingRowView: View {
    let recording: Recording
    
    private var leadArtists: String {
        guard let performers = recording.performers else { return "Unknown Artist" }
        let leaders = performers.filter { $0.role == "leader" }
        if leaders.isEmpty {
            return performers.first?.name ?? "Unknown Artist"
        }
        return leaders.map { $0.name }.joined(separator: ", ")
    }
    
    var body: some View {
        HStack(spacing: 12) {
            // Canonical indicator
            if recording.isCanonical == true {
                Image(systemName: "star.fill")
                    .foregroundColor(JazzTheme.gold)
                    .font(.subheadline)
                    .frame(width: 20)
            } else {
                Spacer()
                    .frame(width: 20)
            }
            
            // Recording info
            VStack(alignment: .leading, spacing: 4) {
                // Album name with Spotify indicator inline
                HStack(spacing: 6) {
                    Text(recording.albumTitle ?? "Unknown Album")
                        .font(.headline)
                        .foregroundColor(JazzTheme.charcoal)
                        .lineLimit(1)
                    
                    // Spotify indicator (if available)
                    if recording.spotifyUrl != nil {
                        Image(systemName: "play.circle.fill")
                            .foregroundColor(.green)
                            .font(.subheadline)
                    }
                }
                
                // Lead artists
                Text(leadArtists)
                    .font(.subheadline)
                    .foregroundColor(JazzTheme.smokeGray)
                    .lineLimit(1)
            }
            
            Spacer()
            
            // Year - always reserve space for consistent alignment
            Text(recording.recordingYear != nil ? String(recording.recordingYear!) : "")
                .font(.subheadline)
                .foregroundColor(JazzTheme.smokeGray)
                .frame(minWidth: 45, alignment: .trailing)
        }
        .padding(.vertical, 12)
        .padding(.horizontal, 16)
        .background(JazzTheme.cardBackground)
        .cornerRadius(8)
        .padding(.horizontal)
    }
}

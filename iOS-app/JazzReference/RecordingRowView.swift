//
//  RecordingRowView.swift
//  JazzReference
//
//  Created by Dave Rodger on 10/8/25.
//

import SwiftUI
import Combine


// MARK: - Recording Row View

struct RecordingRowView: View {
    let recording: Recording
    
    var body: some View {
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
                Text(String(year))
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            }
            
            if let label = recording.label {
                Text(label)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(10)
        .padding(.horizontal)
    }
}



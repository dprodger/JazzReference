//
//  TranscriptionsSection.swift
//  JazzReference
//
//  Created by Dave Rodger on 11/12/25.
//
//  Collapsible section displaying solo transcriptions
//

import SwiftUI

struct TranscriptionsSection: View {
    let transcriptions: [SoloTranscription]
    
    @State private var isSectionExpanded: Bool = true
    
    var body: some View {
        if !transcriptions.isEmpty {
            Divider()
                .padding(.horizontal)
                .padding(.top, 16)
            
            VStack(alignment: .leading, spacing: 0) {
                DisclosureGroup(
                    isExpanded: $isSectionExpanded,
                    content: {
                        VStack(alignment: .leading, spacing: 12) {
                            ForEach(transcriptions) { transcription in
                                TranscriptionRowView(transcription: transcription)
                            }
                        }
                        .padding(.top, 12)
                    },
                    label: {
                        HStack {
                            Image(systemName: "music.quarternote.3")
                                .foregroundColor(JazzTheme.teal)
                            Text("Solo Transcriptions")
                                .font(.title2)
                                .bold()
                                .foregroundColor(JazzTheme.charcoal)
                            
                            Spacer()
                            
                            Text("\(transcriptions.count)")
                                .font(.subheadline)
                                .foregroundColor(JazzTheme.smokeGray)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 4)
                                .background(JazzTheme.teal.opacity(0.1))
                                .cornerRadius(6)
                        }
                        .padding(.horizontal)
                        .padding(.vertical, 12)
                    }
                )
                .tint(JazzTheme.teal)
            }
            .background(JazzTheme.backgroundLight)
        }
    }
}

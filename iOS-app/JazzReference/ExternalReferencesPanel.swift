//
//  ExternalReferencesPanel.swift
//  JazzReference
//
//  Reusable panel for displaying external references (Wikipedia, Jazz Standards, MusicBrainz)
//

import SwiftUI

struct ExternalReferencesPanel: View {
    let externalReferences: [String: String]?
    let musicbrainzId: String?
    
    var wikipediaURL: String? {
        externalReferences?["wikipedia"]
    }
    
    var jazzStandardsURL: String? {
        externalReferences?["jazzstandards"]
    }
    
    var musicbrainzURL: String? {
        guard let mbId = musicbrainzId else { return nil }
        return "https://musicbrainz.org/work/\(mbId)"
    }
    
    var body: some View {
        if wikipediaURL != nil || jazzStandardsURL != nil || musicbrainzURL != nil {
            VStack(alignment: .leading, spacing: 12) {
                Text("External References")
                    .font(.headline)
                    .foregroundColor(JazzTheme.charcoal)
                
                HStack(spacing: 16) {
                    if let wikipediaURL = wikipediaURL, let url = URL(string: wikipediaURL) {
                        Link(destination: url) {
                            VStack(spacing: 4) {
                                Image(systemName: "book.circle.fill")
                                    .font(.title2)
                                    .foregroundColor(JazzTheme.brass)
                                Text("Wikipedia")
                                    .font(.caption)
                                    .foregroundColor(JazzTheme.smokeGray)
                            }
                        }
                    }
                    
                    if let jazzStandardsURL = jazzStandardsURL, let url = URL(string: jazzStandardsURL) {
                        Link(destination: url) {
                            VStack(spacing: 4) {
                                Image(systemName: "music.note.list")
                                    .font(.title2)
                                    .foregroundColor(JazzTheme.brass)
                                Text("Jazz Standards")
                                    .font(.caption)
                                    .foregroundColor(JazzTheme.smokeGray)
                            }
                        }
                    }
                    
                    if let musicbrainzURL = musicbrainzURL, let url = URL(string: musicbrainzURL) {
                        Link(destination: url) {
                            VStack(spacing: 4) {
                                Image(systemName: "music.mic.circle.fill")
                                    .font(.title2)
                                    .foregroundColor(JazzTheme.brass)
                                Text("MusicBrainz")
                                    .font(.caption)
                                    .foregroundColor(JazzTheme.smokeGray)
                            }
                        }
                    }
                }
                .padding(.top, 4)
            }
            .padding()
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(JazzTheme.cardBackground)
            .cornerRadius(10)
            .padding(.horizontal)
        }
    }
}

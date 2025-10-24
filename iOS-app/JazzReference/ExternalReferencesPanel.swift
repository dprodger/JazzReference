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
    let musicbrainzType: MusicBrainzType
    
    enum MusicBrainzType {
        case work   // For songs
        case artist // For performers
    }
    
    // Convenience initializer for songs (with separate musicbrainzId field)
    init(externalReferences: [String: String]?, musicbrainzId: String?) {
        self.externalReferences = externalReferences
        self.musicbrainzId = musicbrainzId
        self.musicbrainzType = .work
    }
    
    // Convenience initializer for artists (musicbrainz in externalLinks)
    init(externalLinks: [String: String]?) {
        self.externalReferences = externalLinks
        self.musicbrainzId = externalLinks?["musicbrainz"]
        self.musicbrainzType = .artist
    }
    
    var wikipediaURL: String? {
        externalReferences?["wikipedia"]
    }
    
    var jazzStandardsURL: String? {
        externalReferences?["jazzstandards"]
    }
    
    var musicbrainzURL: String? {
        guard let mbId = musicbrainzId else { return nil }
        switch musicbrainzType {
        case .work:
            return "https://musicbrainz.org/work/\(mbId)"
        case .artist:
            return "https://musicbrainz.org/artist/\(mbId)"
        }
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

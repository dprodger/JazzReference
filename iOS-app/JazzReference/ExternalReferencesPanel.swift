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
    let entityType: String
    let entityId: String
    let entityName: String
    
    @State private var reportingInfo: ReportingInfo?
    @State private var longPressOccurred = false
    @Environment(\.openURL) var openURL
    
    struct ReportingInfo: Identifiable {
        let id = UUID()
        let source: String
        let url: String
    }
    
    enum MusicBrainzType {
        case work   // For songs
        case artist // For performers
    }
    
    // NEW: Initializer for artists with dedicated wikipedia and musicbrainz fields
    init(wikipediaUrl: String?, musicbrainzId: String?, externalLinks: [String: String]?,
         entityId: String, entityName: String) {
        // Use dedicated fields first, fall back to external_links if needed
        var references = externalLinks ?? [:]
        if let wikipedia = wikipediaUrl {
            references["wikipedia"] = wikipedia
        }
        if let musicbrainz = musicbrainzId {
            references["musicbrainz"] = musicbrainz
        }
        
        self.externalReferences = references
        self.musicbrainzId = musicbrainzId
        self.musicbrainzType = .artist
        self.entityType = "Artist"
        self.entityId = entityId
        self.entityName = entityName
    }

    // Convenience initializer for songs (with separate musicbrainzId field)
    init(externalReferences: [String: String]?, musicbrainzId: String?, entityId: String, entityName: String) {
        self.externalReferences = externalReferences
        self.musicbrainzId = musicbrainzId
        self.musicbrainzType = .work
        self.entityType = "Song"
        self.entityId = entityId
        self.entityName = entityName
    }
    
    // Convenience initializer for artists (musicbrainz in externalLinks)
    init(externalLinks: [String: String]?, entityId: String, entityName: String) {
        self.externalReferences = externalLinks
        self.musicbrainzId = externalLinks?["musicbrainz"]
        self.musicbrainzType = .artist
        self.entityType = "Artist"
        self.entityId = entityId
        self.entityName = entityName
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
                Text("Learn More")
                    .font(.headline)
                    .foregroundColor(JazzTheme.charcoal)
                
                HStack(spacing: 16) {
                    if let wikipediaURL = wikipediaURL, let url = URL(string: wikipediaURL) {
                        let urlString = wikipediaURL  // Capture explicitly
                        Button {
                            if !longPressOccurred {
                                openURL(url)
                            }
                            longPressOccurred = false
                        } label: {
                            VStack(spacing: 4) {
                                Image(systemName: "book.circle.fill")
                                    .font(.title2)
                                    .foregroundColor(JazzTheme.brass)
                                Text("Wikipedia")
                                    .font(.caption)
                                    .foregroundColor(JazzTheme.smokeGray)
                            }
                        }
                        .simultaneousGesture(
                            LongPressGesture(minimumDuration: 0.5)
                                .onEnded { _ in
                                    longPressOccurred = true
                                    reportingInfo = ReportingInfo(source: "Wikipedia", url: urlString)
                                }
                        )
                    }
                    
                    if let jazzStandardsURL = jazzStandardsURL, let url = URL(string: jazzStandardsURL) {
                        let urlString = jazzStandardsURL  // Capture explicitly
                        Button {
                            if !longPressOccurred {
                                openURL(url)
                            }
                            longPressOccurred = false
                        } label: {
                            VStack(spacing: 4) {
                                Image(systemName: "music.note.list")
                                    .font(.title2)
                                    .foregroundColor(JazzTheme.brass)
                                Text("Jazz Standards")
                                    .font(.caption)
                                    .foregroundColor(JazzTheme.smokeGray)
                            }
                        }
                        .simultaneousGesture(
                            LongPressGesture(minimumDuration: 0.5)
                                .onEnded { _ in
                                    longPressOccurred = true
                                    reportingInfo = ReportingInfo(source: "Jazz Standards", url: urlString)
                                }
                        )
                    }
                    
                    if let musicbrainzURL = musicbrainzURL, let url = URL(string: musicbrainzURL) {
                        let urlString = musicbrainzURL  // Capture explicitly
                        Button {
                            if !longPressOccurred {
                                openURL(url)
                            }
                            longPressOccurred = false
                        } label: {
                            VStack(spacing: 4) {
                                Image(systemName: "music.mic.circle.fill")
                                    .font(.title2)
                                    .foregroundColor(JazzTheme.brass)
                                Text("MusicBrainz")
                                    .font(.caption)
                                    .foregroundColor(JazzTheme.smokeGray)
                            }
                        }
                        .simultaneousGesture(
                            LongPressGesture(minimumDuration: 0.5)
                                .onEnded { _ in
                                    longPressOccurred = true
                                    reportingInfo = ReportingInfo(source: "MusicBrainz", url: urlString)
                                }
                        )
                    }
                }
                .padding(.top, 4)
            }
            .padding()
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(JazzTheme.cardBackground)
            .cornerRadius(10)
            .padding(.horizontal)
            .sheet(item: $reportingInfo) { info in
                ReportLinkIssueView(
                    entityType: entityType,
                    entityId: entityId,
                    entityName: entityName,
                    externalSource: info.source,
                    externalUrl: info.url,
                    onSubmit: { explanation in
                        submitLinkReport(
                            entityType: entityType,
                            entityId: entityId,
                            entityName: entityName,
                            externalSource: info.source,
                            externalUrl: info.url,
                            explanation: explanation
                        )
                        reportingInfo = nil
                    },
                    onCancel: {
                        reportingInfo = nil
                    }
                )
            }
        }
    }
    
    // MARK: - Stub submission method
    private func submitLinkReport(entityType: String, entityId: String, entityName: String, externalSource: String, externalUrl: String, explanation: String) {
        // TODO: Implement actual submission logic
        // For now, this is just a stub
        print("Link report submitted:")
        print("  Entity Type: \(entityType)")
        print("  Entity ID: \(entityId)")
        print("  Entity Name: \(entityName)")
        print("  External Source: \(externalSource)")
        print("  External URL: \(externalUrl)")
        print("  Explanation: \(explanation)")
    }
}


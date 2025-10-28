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
    @State private var showingSubmissionAlert = false
    @State private var submissionAlertMessage = ""
    @Environment(\.openURL) var openURL
    
    struct ReportingInfo: Identifiable {
        let id = UUID()
        let source: String
        let url: String
    }
    
    enum MusicBrainzType {
        case work      // For songs
        case artist    // For performers
        case recording // For recordings
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
        self.entityType = "performer"
        self.entityId = entityId
        self.entityName = entityName
    }

    // Convenience initializer for songs (with separate musicbrainzId field)
    init(externalReferences: [String: String]?, musicbrainzId: String?, entityId: String, entityName: String) {
        self.externalReferences = externalReferences
        self.musicbrainzId = musicbrainzId
        self.musicbrainzType = .work
        self.entityType = "song"
        self.entityId = entityId
        self.entityName = entityName
    }
    
    // Convenience initializer for artists (musicbrainz in externalLinks)
    init(externalLinks: [String: String]?, entityId: String, entityName: String) {
        self.externalReferences = externalLinks
        self.musicbrainzId = externalLinks?["musicbrainz"]
        self.musicbrainzType = .artist
        self.entityType = "performer"
        self.entityId = entityId
        self.entityName = entityName
    }
    
    // Convenience initializer for recordings (musicbrainz only)
    init(musicbrainzId: String?, recordingId: String, albumTitle: String) {
        self.externalReferences = nil
        self.musicbrainzId = musicbrainzId
        self.musicbrainzType = .recording
        self.entityType = "recording"
        self.entityId = recordingId
        self.entityName = albumTitle
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
        case .recording:
            return "https://musicbrainz.org/recording/\(mbId)"
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
            .alert("Report Submitted", isPresented: $showingSubmissionAlert) {
                Button("OK", role: .cancel) { }
            } message: {
                Text(submissionAlertMessage)
            }
        }
    }
    
    // MARK: - Submit link report to API
    private func submitLinkReport(entityType: String, entityId: String, entityName: String, externalSource: String, externalUrl: String, explanation: String) {
        Task {
            do {
                let success = try await sendReportToAPI(
                    entityType: entityType,
                    entityId: entityId,
                    entityName: entityName,
                    externalSource: externalSource,
                    externalUrl: externalUrl,
                    explanation: explanation
                )
                
                if success {
                    submissionAlertMessage = "Thank you for your report. We will review it shortly."
                } else {
                    submissionAlertMessage = "Failed to submit report. Please try again later."
                }
                showingSubmissionAlert = true
                
            } catch {
                submissionAlertMessage = "Failed to submit report: \(error.localizedDescription)"
                showingSubmissionAlert = true
            }
        }
    }
    
    // MARK: - API call
    private func sendReportToAPI(entityType: String, entityId: String, entityName: String, externalSource: String, externalUrl: String, explanation: String) async throws -> Bool {
        
        // Get API base URL from environment or use default
        let baseURL = ProcessInfo.processInfo.environment["API_BASE_URL"] ?? "https://linernotesjazz.com"
        
        guard let url = URL(string: "\(baseURL)/api/content-reports") else {
            throw URLError(.badURL)
        }
        
        // Build request body
        let requestBody: [String: Any] = [
            "entity_type": entityType,
            "entity_id": entityId,
            "entity_name": entityName,
            "external_source": externalSource,
            "external_url": externalUrl,
            "explanation": explanation,
            "reporter_platform": "ios",
            "reporter_app_version": Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0"
        ]
        
        // Create request
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: requestBody)
        
        // Send request
        let (data, response) = try await URLSession.shared.data(for: request)
        
        // Check response
        guard let httpResponse = response as? HTTPURLResponse else {
            return false
        }
        
        if httpResponse.statusCode == 201 {
            // Success
            return true
        } else {
            // Log error for debugging
            if let errorDict = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let errorMessage = errorDict["error"] as? String {
                print("API Error: \(errorMessage)")
            }
            return false
        }
    }
}

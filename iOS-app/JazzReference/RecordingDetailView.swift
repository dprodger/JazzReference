//
//  RecordingDetailView.swift
//  JazzReference
//
//  Updated with authority recommendations management button in header
//

import SwiftUI
import Combine

// MARK: - Recording Detail View

struct RecordingDetailView: View {
    let recordingId: String
    @State private var recording: Recording?
    @State private var isLoading = true
    @State private var reportingInfo: ReportingInfo?
    @State private var longPressOccurred = false
    @State private var showingSubmissionAlert = false
    @State private var submissionAlertMessage = ""
    @State private var showingAuthoritySheet = false  // NEW: Authority sheet state
    @Environment(\.openURL) var openURL
    
    struct ReportingInfo: Identifiable {
        let id = UUID()
        let source: String
        let url: String
    }
    
    var body: some View {
        ScrollView {
            if isLoading {
                VStack {
                    Spacer()
                    ProgressView("Loading...")
                        .tint(JazzTheme.brass)
                    Spacer()
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(JazzTheme.backgroundLight)
            } else if let recording = recording {
                VStack(alignment: .leading, spacing: 0) {
                    // Styled Header with Jazz Theme - NOW WITH AUTHORITY BUTTON
                    HStack {
                        Image(systemName: "opticaldisc")
                            .font(.title2)
                            .foregroundColor(JazzTheme.cream)
                        Text("RECORDING")
                            .font(.headline)
                            .fontWeight(.semibold)
                            .foregroundColor(JazzTheme.cream)
                        Spacer()
                        
                        // NEW: Authority recommendations button
                        Button {
                            showingAuthoritySheet = true
                        } label: {
                            HStack(spacing: 4) {
                                Image(systemName: "checkmark.seal")
                                Text("Authority")
                                    .font(.caption)
                            }
                            .foregroundColor(JazzTheme.cream)
                            .padding(.horizontal, 10)
                            .padding(.vertical, 6)
                            .background(JazzTheme.cream.opacity(0.2))
                            .cornerRadius(8)
                        }
                    }
                    .padding()
                    .background(JazzTheme.brassGradient)
                    
                    VStack(alignment: .leading, spacing: 20) {
                        // Album Information
                        VStack(alignment: .leading, spacing: 12) {
                            // Album artwork
                            if let albumArtUrl = recording.albumArtLarge ?? recording.albumArtMedium {
                                AsyncImage(url: URL(string: albumArtUrl)) { phase in
                                    switch phase {
                                    case .empty:
                                        ProgressView()
                                            .frame(maxWidth: .infinity)
                                            .frame(height: 300)
                                    case .success(let image):
                                        image
                                            .resizable()
                                            .aspectRatio(contentMode: .fit)
                                            .frame(maxWidth: .infinity)
                                            .cornerRadius(12)
                                    case .failure:
                                        Image(systemName: "music.note")
                                            .font(.system(size: 80))
                                            .foregroundColor(.secondary)
                                            .frame(maxWidth: .infinity)
                                            .frame(height: 300)
                                            .background(Color(.systemGray5))
                                            .cornerRadius(12)
                                    @unknown default:
                                        EmptyView()
                                    }
                                }
                                .shadow(radius: 8)
                            }
                            
                            HStack {
                                if recording.isCanonical == true {
                                    Image(systemName: "star.fill")
                                        .foregroundColor(JazzTheme.gold)
                                        .font(.title2)
                                }
                                Text(recording.albumTitle ?? "Unknown Album")
                                    .font(.largeTitle)
                                    .bold()
                                    .foregroundColor(JazzTheme.charcoal)
                            }
                            
                            if let songTitle = recording.songTitle {
                                Text(songTitle)
                                    .font(.title2)
                                    .foregroundColor(JazzTheme.smokeGray)
                            }
                            
                            if let composer = recording.composer {
                                Text("Composed by \(composer)")
                                    .font(.subheadline)
                                    .foregroundColor(JazzTheme.smokeGray)
                            }
                        }
                        .padding()
                        
                        // Recording Details
                        VStack(alignment: .leading, spacing: 12) {
                            if let year = recording.recordingYear {
                                DetailRow(
                                    icon: "calendar",
                                    label: "Year",
                                    value: "\(year)"
                                )
                            }
                            
                            if let date = recording.recordingDate {
                                DetailRow(
                                    icon: "calendar.badge.clock",
                                    label: "Recorded",
                                    value: date
                                )
                            }
                            
                            if let label = recording.label {
                                DetailRow(
                                    icon: "music.note.house",
                                    label: "Label",
                                    value: label
                                )
                            }
                        }
                        .padding()
                        .background(JazzTheme.cardBackground)
                        .cornerRadius(10)
                        .padding(.horizontal)
                        
                        // Streaming Links
                        if recording.spotifyUrl != nil || recording.youtubeUrl != nil || recording.appleMusicUrl != nil {
                            VStack(alignment: .leading, spacing: 12) {
                                Text("Listen")
                                    .font(.headline)
                                    .foregroundColor(JazzTheme.charcoal)
                                    .padding(.horizontal)
                                
                                HStack(spacing: 16) {
                                    if let spotifyUrl = recording.spotifyUrl, let url = URL(string: spotifyUrl) {
                                        let urlString = spotifyUrl
                                        Button {
                                            if !longPressOccurred {
                                                openURL(url)
                                            }
                                            longPressOccurred = false
                                        } label: {
                                            StreamingButton(
                                                icon: "music.note",
                                                color: JazzTheme.teal,
                                                label: "Spotify"
                                            )
                                        }
                                        .simultaneousGesture(
                                            LongPressGesture(minimumDuration: 0.5)
                                                .onEnded { _ in
                                                    longPressOccurred = true
                                                    reportingInfo = ReportingInfo(source: "Spotify", url: urlString)
                                                }
                                        )
                                    }
                                    
                                    if let youtubeUrl = recording.youtubeUrl, let url = URL(string: youtubeUrl) {
                                        let urlString = youtubeUrl
                                        Button {
                                            if !longPressOccurred {
                                                openURL(url)
                                            }
                                            longPressOccurred = false
                                        } label: {
                                            StreamingButton(
                                                icon: "play.rectangle.fill",
                                                color: JazzTheme.burgundy,
                                                label: "YouTube"
                                            )
                                        }
                                        .simultaneousGesture(
                                            LongPressGesture(minimumDuration: 0.5)
                                                .onEnded { _ in
                                                    longPressOccurred = true
                                                    reportingInfo = ReportingInfo(source: "YouTube", url: urlString)
                                                }
                                        )
                                    }
                                    
                                    if let appleMusicUrl = recording.appleMusicUrl {
                                        Link(destination: URL(string: appleMusicUrl)!) {
                                            StreamingButton(
                                                icon: "applelogo",
                                                color: JazzTheme.amber,
                                                label: "Apple"
                                            )
                                        }
                                    }
                                }
                                .padding(.horizontal)
                            }
                        }
                        
                        if let notes = recording.notes {
                            VStack(alignment: .leading, spacing: 8) {
                                Text("Notes")
                                    .font(.headline)
                                    .foregroundColor(JazzTheme.charcoal)
                                Text(notes)
                                    .font(.body)
                                    .foregroundColor(JazzTheme.smokeGray)
                            }
                            .padding()
                            .background(JazzTheme.cardBackground)
                            .cornerRadius(10)
                            .padding(.horizontal)
                        }
                        
                        // External References Panel
                        if recording.musicbrainzId != nil {
                            ExternalReferencesPanel(
                                musicbrainzId: recording.musicbrainzId,
                                recordingId: recordingId,
                                albumTitle: recording.albumTitle ?? "Unknown Album"
                            )
                        }
                        
                        Divider()
                            .padding(.horizontal)
                        
                        // Performers Section
                        VStack(alignment: .leading, spacing: 12) {
                            Text("Performers")
                                .font(.title2)
                                .bold()
                                .foregroundColor(JazzTheme.charcoal)
                                .padding(.horizontal)
                            
                            if let performers = recording.performers, !performers.isEmpty {
                                ForEach(performers) { performer in
                                    NavigationLink(destination: PerformerDetailView(performerId: performer.id)) {
                                        PerformerRowView(performer: performer)
                                    }
                                    .buttonStyle(.plain)
                                }
                            } else {
                                Text("No performer information available")
                                    .foregroundColor(JazzTheme.smokeGray)
                                    .padding()
                            }
                        }
                    }
                    .padding(.vertical)
                }
            } else {
                VStack {
                    Spacer()
                    Text("Recording not found")
                        .foregroundColor(JazzTheme.smokeGray)
                    Spacer()
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(JazzTheme.backgroundLight)
            }
        }
        .background(JazzTheme.backgroundLight)
        .navigationBarTitleDisplayMode(.inline)
        .sheet(item: $reportingInfo) { info in
            ReportLinkIssueView(
                entityType: "recording",
                entityId: recordingId,
                entityName: recording?.albumTitle ?? "Unknown Album",
                externalSource: info.source,
                externalUrl: info.url,
                onSubmit: { explanation in
                    submitLinkReport(
                        entityType: "recording",
                        entityId: recordingId,
                        entityName: recording?.albumTitle ?? "Unknown Album",
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
        // NEW: Authority recommendations sheet
        .sheet(isPresented: $showingAuthoritySheet) {
            AuthorityRecommendationsView(
                recordingId: recordingId,
                albumTitle: recording?.albumTitle ?? "Unknown Album"
            )
        }
        .alert("Report Submitted", isPresented: $showingSubmissionAlert) {
            Button("OK", role: .cancel) { }
        } message: {
            Text(submissionAlertMessage)
        }
        .task {
            #if DEBUG
            if ProcessInfo.processInfo.environment["XCODE_RUNNING_FOR_PREVIEWS"] == "1" {
                let networkManager = NetworkManager()
                recording = networkManager.fetchRecordingDetailSync(id: recordingId)
                isLoading = false
                return
            }
            #endif
            
            let networkManager = NetworkManager()
            recording = await networkManager.fetchRecordingDetail(id: recordingId)
            isLoading = false
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

#Preview("Recording Detail - Full") {
    NavigationStack {
        RecordingDetailView(recordingId: "preview-recording-1")
    }
}
#Preview("Recording Detail - Minimal") {
    NavigationStack {
        RecordingDetailView(recordingId: "preview-recording-3")
    }
}

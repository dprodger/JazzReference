//
//  RecordingDetailView.swift
//  JazzReference
//
//  Updated with JazzTheme color palette and consistent styling
//  UPDATED: Added back cover flip support with 3D animation
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
    @State private var showingAuthoritySheet = false
    @State private var showAllReleases = false
    @State private var selectedReleaseId: String?
    @State private var showingStreamingPicker = false
    @State private var isLearnMoreExpanded = false
    @State private var showingBackCover = false
    private let maxReleasesToShow = 5
    @Environment(\.openURL) var openURL
    
    // MARK: - Computed Properties for Selected Release
    
    /// The currently selected release, or nil to use recording defaults
    private var selectedRelease: Release? {
        guard let releaseId = selectedReleaseId,
              let releases = recording?.releases else { return nil }
        return releases.first { $0.id == releaseId }
    }
    
    /// Front cover art URL - uses selected release if user picked one, otherwise uses bestAlbumArt*
    private var displayAlbumArtLarge: String? {
        if let release = selectedRelease {
            return release.coverArtLarge ?? release.coverArtMedium
        }
        // Use bestAlbumArt* which is consistent across API endpoints
        return recording?.bestAlbumArtLarge ?? recording?.bestAlbumArtMedium
    }

    /// Back cover art URL - uses recording's back cover fields
    private var displayBackCoverArtLarge: String? {
        return recording?.backCoverArtLarge ?? recording?.backCoverArtMedium
    }

    /// Whether the recording has a back cover available for flipping
    private var canFlipToBackCover: Bool {
        recording?.canFlipToBackCover ?? false
    }
    
    /// Spotify URL - uses selected release if user picked one, otherwise uses bestSpotifyUrl
    private var displaySpotifyUrl: String? {
        if let release = selectedRelease {
            return release.spotifyTrackUrl ?? release.spotifyAlbumUrl
        }
        // Use bestSpotifyUrl which is consistent across API endpoints
        return recording?.bestSpotifyUrl
    }
    
    /// Display title - selected release title or recording album title
    private var displayAlbumTitle: String {
        selectedRelease?.title ?? recording?.albumTitle ?? "Unknown Album"
    }
    
    /// Performers from selected release if available, otherwise from recording
    private var displayPerformers: [Performer]? {
        // If a release is selected and has performers, use them
        if let release = selectedRelease, let releasePerformers = release.performers, !releasePerformers.isEmpty {
            return releasePerformers
        }
        // Fall back to recording performers
        return recording?.performers
    }
    
    /// Available streaming sources as (name, url) tuples
    private var availableStreamingSources: [(name: String, icon: String, url: String, color: Color)] {
        var sources: [(name: String, icon: String, url: String, color: Color)] = []
        
        if let spotifyUrl = displaySpotifyUrl {
            sources.append((name: "Spotify", icon: "music.note", url: spotifyUrl, color: JazzTheme.teal))
        }
        if let youtubeUrl = recording?.youtubeUrl {
            sources.append((name: "YouTube", icon: "play.rectangle.fill", url: youtubeUrl, color: JazzTheme.burgundy))
        }
        if let appleMusicUrl = recording?.appleMusicUrl {
            sources.append((name: "Apple Music", icon: "applelogo", url: appleMusicUrl, color: JazzTheme.amber))
        }
        
        return sources
    }
    
    /// Whether any streaming source is available
    private var hasStreamingSource: Bool {
        !availableStreamingSources.isEmpty
    }
    
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
                    // Styled Header with Jazz Theme
                    HStack {
                        Image(systemName: "opticaldisc")
                            .font(.title2)
                            .foregroundColor(JazzTheme.cream)
                        Text("RECORDING")
                            .font(.headline)
                            .fontWeight(.semibold)
                            .foregroundColor(JazzTheme.cream)
                        Spacer()
                    }
                    .padding()
                    .background(JazzTheme.brassGradient)
                    
                    VStack(alignment: .leading, spacing: 20) {
                        // Album Information
                        VStack(alignment: .leading, spacing: 12) {
                            // Album artwork with play button overlay and flip support
                            ZStack(alignment: .topTrailing) {
                                // Card-flip container
                                ZStack {
                                    // Front cover
                                    if let frontUrl = displayAlbumArtLarge {
                                        CachedAsyncImage(
                                            url: URL(string: frontUrl),
                                            content: { image in
                                                image
                                                    .resizable()
                                                    .aspectRatio(contentMode: .fit)
                                                    .frame(maxWidth: .infinity)
                                                    .cornerRadius(12)
                                            },
                                            placeholder: {
                                                Rectangle()
                                                    .fill(Color(.systemGray5))
                                                    .aspectRatio(1, contentMode: .fit)
                                                    .cornerRadius(12)
                                                    .overlay(
                                                        ProgressView()
                                                            .tint(JazzTheme.brass)
                                                    )
                                            }
                                        )
                                        .opacity(showingBackCover ? 0 : 1)
                                    } else {
                                        albumArtPlaceholder
                                            .opacity(showingBackCover ? 0 : 1)
                                    }

                                    // Back cover (pre-rotated so it appears correct after flip)
                                    if let backUrl = displayBackCoverArtLarge {
                                        CachedAsyncImage(
                                            url: URL(string: backUrl),
                                            content: { image in
                                                image
                                                    .resizable()
                                                    .aspectRatio(contentMode: .fit)
                                                    .frame(maxWidth: .infinity)
                                                    .cornerRadius(12)
                                            },
                                            placeholder: {
                                                Rectangle()
                                                    .fill(Color(.systemGray5))
                                                    .aspectRatio(1, contentMode: .fit)
                                                    .cornerRadius(12)
                                                    .overlay(
                                                        ProgressView()
                                                            .tint(JazzTheme.brass)
                                                    )
                                            }
                                        )
                                        .rotation3DEffect(.degrees(180), axis: (x: 0, y: 1, z: 0))
                                        .opacity(showingBackCover ? 1 : 0)
                                    }
                                }
                                .rotation3DEffect(
                                    .degrees(showingBackCover ? 180 : 0),
                                    axis: (x: 0, y: 1, z: 0)
                                )

                                // Play button overlay (only on front)
                                if hasStreamingSource && !showingBackCover {
                                    playButtonOverlay
                                }

                                // Flip button badge (shown when back cover available)
                                if canFlipToBackCover {
                                    Button(action: {
                                        withAnimation(.easeInOut(duration: 0.4)) {
                                            showingBackCover.toggle()
                                        }
                                    }) {
                                        Image(systemName: showingBackCover ? "arrow.uturn.backward" : "arrow.trianglehead.2.clockwise.rotate.90")
                                            .foregroundColor(.white)
                                            .font(.system(size: 14, weight: .semibold))
                                            .padding(10)
                                            .background(Color.black.opacity(0.6))
                                            .clipShape(Circle())
                                    }
                                    .buttonStyle(PlainButtonStyle())
                                    .padding(12)
                                }
                            }
                            .shadow(radius: 8)
                            .animation(.easeInOut(duration: 0.3), value: selectedReleaseId)
                            
                            HStack {
                                if recording.isCanonical == true {
                                    Image(systemName: "star.fill")
                                        .foregroundColor(JazzTheme.gold)
                                        .font(.title2)
                                }
                                Text(displayAlbumTitle)
                                    .font(.largeTitle)
                                    .bold()
                                    .foregroundColor(JazzTheme.charcoal)
                                    .animation(.easeInOut(duration: 0.3), value: selectedReleaseId)
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
                        
                        // Learn More Section (Collapsible)
                        learnMoreSection(recording)
                        
                        // Releases Section - shows all releases containing this recording
                        if let releases = recording.releases, releases.count > 1 {
                            releasesSection(releases)
                        }
                        
                        Divider()
                            .padding(.horizontal)
                        
                        // Performers Section
                        VStack(alignment: .leading, spacing: 12) {
                            HStack {
                                Text("Performers")
                                    .font(.title2)
                                    .bold()
                                    .foregroundColor(JazzTheme.charcoal)
                                
                                // Indicator when showing release-specific performers
                                if selectedRelease != nil, let releasePerformers = selectedRelease?.performers, !releasePerformers.isEmpty {
                                    Text("(from selected release)")
                                        .font(.caption)
                                        .foregroundColor(JazzTheme.smokeGray)
                                }
                            }
                            .padding(.horizontal)
                            
                            if let performers = displayPerformers, !performers.isEmpty {
                                ForEach(performers) { performer in
                                    NavigationLink(destination: PerformerDetailView(performerId: performer.id)) {
                                        PerformerRowView(performer: performer)
                                    }
                                    .buttonStyle(.plain)
                                }
                                .animation(.easeInOut(duration: 0.3), value: selectedReleaseId)
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
        .toolbarBackground(JazzTheme.brass, for: .navigationBar)
        .toolbarBackground(.visible, for: .navigationBar)
        .toolbarColorScheme(.dark, for: .navigationBar)
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Button {
                    showingAuthoritySheet = true
                } label: {
                    Image(systemName: "checkmark.seal")
                }
            }
        }
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
        .sheet(isPresented: $showingAuthoritySheet) {
            AuthorityRecommendationsView(
                recordingId: recordingId,
                albumTitle: recording?.albumTitle ?? "Unknown Album",
                songId: recording?.songId  // ← Add this line
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
                autoSelectFirstRelease()
                isLoading = false
                return
            }
            #endif
            
            let networkManager = NetworkManager()
            recording = await networkManager.fetchRecordingDetail(id: recordingId)
            autoSelectFirstRelease()
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
        let baseURL = ProcessInfo.processInfo.environment["API_BASE_URL"] ?? "https://approachnote.com"
        
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
    
    // MARK: - Releases Section
    
    @ViewBuilder
    private func releasesSection(_ releases: [Release]) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Also Available On")
                    .font(.headline)
                    .foregroundColor(JazzTheme.charcoal)
                
                Spacer()
                
                // Spotify count badge
                let spotifyCount = releases.filter { $0.hasSpotify }.count
                if spotifyCount > 0 {
                    HStack(spacing: 4) {
                        Image(systemName: "music.note")
                            .font(.caption)
                            .foregroundColor(JazzTheme.teal)
                        Text("\(spotifyCount)")
                            .font(.caption)
                            .foregroundColor(JazzTheme.smokeGray)
                    }
                }
            }
            
            let displayedReleases = showAllReleases ? releases : Array(releases.prefix(maxReleasesToShow))
            
            ForEach(displayedReleases) { release in
                Button {
                    withAnimation(.easeInOut(duration: 0.3)) {
                        if selectedReleaseId == release.id {
                            // Deselect if already selected
                            selectedReleaseId = nil
                        } else {
                            selectedReleaseId = release.id
                        }
                    }
                } label: {
                    releaseRow(release, isSelected: selectedReleaseId == release.id)
                }
                .buttonStyle(.plain)
            }
            
            // Show more/less button
            if releases.count > maxReleasesToShow {
                Button {
                    withAnimation {
                        showAllReleases.toggle()
                    }
                } label: {
                    HStack {
                        Text(showAllReleases ? "Show Less" : "Show All \(releases.count) Releases")
                            .font(.subheadline)
                        Image(systemName: showAllReleases ? "chevron.up" : "chevron.down")
                            .font(.caption)
                    }
                    .foregroundColor(JazzTheme.burgundy)
                }
                .padding(.top, 4)
            }
        }
        .padding()
        .background(JazzTheme.cardBackground)
        .cornerRadius(10)
        .padding(.horizontal)
    }
    
    @ViewBuilder
    private func releaseRow(_ release: Release, isSelected: Bool) -> some View {
        HStack(alignment: .top, spacing: 12) {
            // Selection indicator
            if isSelected {
                Image(systemName: "checkmark.circle.fill")
                    .font(.title3)
                    .foregroundColor(JazzTheme.burgundy)
            } else {
                Image(systemName: "circle")
                    .font(.title3)
                    .foregroundColor(JazzTheme.smokeGray.opacity(0.5))
            }
            
            // Cover art or placeholder
            if let artUrl = release.coverArtSmall, let url = URL(string: artUrl) {
                CachedAsyncImage(
                    url: url,
                    content: { image in
                        image
                            .resizable()
                            .aspectRatio(contentMode: .fill)
                            .frame(width: 50, height: 50)
                            .clipped()
                            .cornerRadius(4)
                    },
                    placeholder: {
                        Rectangle()
                            .fill(JazzTheme.smokeGray.opacity(0.3))
                            .frame(width: 50, height: 50)
                            .cornerRadius(4)
                    }
                )
                .overlay(
                    RoundedRectangle(cornerRadius: 4)
                        .stroke(isSelected ? JazzTheme.burgundy : Color.clear, lineWidth: 2)
                )
            } else {
                Rectangle()
                    .fill(JazzTheme.smokeGray.opacity(0.2))
                    .frame(width: 50, height: 50)
                    .cornerRadius(4)
                    .overlay(
                        Image(systemName: "opticaldisc")
                            .foregroundColor(JazzTheme.smokeGray)
                    )
                    .overlay(
                        RoundedRectangle(cornerRadius: 4)
                            .stroke(isSelected ? JazzTheme.burgundy : Color.clear, lineWidth: 2)
                    )
            }
            
            VStack(alignment: .leading, spacing: 4) {
                // Release title
                Text(release.title)
                    .font(.subheadline)
                    .fontWeight(isSelected ? .bold : .medium)
                    .foregroundColor(isSelected ? JazzTheme.burgundy : JazzTheme.charcoal)
                    .lineLimit(2)
                
                // Artist and year
                HStack(spacing: 4) {
                    if let artist = release.artistCredit {
                        Text(artist)
                            .lineLimit(1)
                    }
                    if release.releaseYear != nil && release.artistCredit != nil {
                        Text("•")
                    }
                    if let year = release.releaseYear {
                        Text(String(year))
                    }
                }
                .font(.caption)
                .foregroundColor(JazzTheme.smokeGray)
                
                // Track position
                if let trackPos = release.trackPositionDisplay {
                    Text(trackPos)
                        .font(.caption2)
                        .foregroundColor(JazzTheme.smokeGray)
                }
                
                // Format badge
                if let format = release.formatName {
                    Text(format)
                        .font(.caption2)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(JazzTheme.smokeGray.opacity(0.2))
                        .cornerRadius(4)
                        .foregroundColor(JazzTheme.charcoal)
                }
            }
            
            Spacer()
            
            // Spotify indicator (not a link - the whole row is tappable)
            if release.spotifyTrackUrl != nil || release.spotifyAlbumUrl != nil {
                Image(systemName: "music.note")
                    .font(.title3)
                    .foregroundColor(JazzTheme.teal)
            }
        }
        .padding(.vertical, 6)
        .padding(.horizontal, 8)
        .background(isSelected ? JazzTheme.burgundy.opacity(0.1) : Color.clear)
        .cornerRadius(8)
    }
    
    // MARK: - Album Art Placeholder
    
    private var albumArtPlaceholder: some View {
        Rectangle()
            .fill(Color(.systemGray5))
            .frame(maxWidth: .infinity)
            .aspectRatio(1, contentMode: .fit)
            .cornerRadius(12)
            .overlay(
                Image(systemName: "music.note")
                    .font(.system(size: 80))
                    .foregroundColor(.secondary)
            )
    }
    
    // MARK: - Play Button Overlay
    
    private var playButtonOverlay: some View {
        VStack {
            Spacer()
            HStack {
                Spacer()
                
                Button {
                    handlePlayButtonTap()
                } label: {
                    ZStack {
                        Circle()
                            .fill(.ultraThinMaterial)
                            .frame(width: 70, height: 70)
                        
                        Circle()
                            .fill(JazzTheme.burgundy)
                            .frame(width: 60, height: 60)
                        
                        Image(systemName: "play.fill")
                            .font(.title)
                            .foregroundColor(.white)
                            .offset(x: 2) // Slight offset for visual centering
                    }
                    .shadow(color: .black.opacity(0.3), radius: 8, x: 0, y: 4)
                }
                
                Spacer()
            }
            Spacer()
        }
        .confirmationDialog(
            "Listen on",
            isPresented: $showingStreamingPicker,
            titleVisibility: .visible
        ) {
            ForEach(availableStreamingSources, id: \.url) { source in
                Button {
                    if let url = URL(string: source.url) {
                        openURL(url)
                    }
                } label: {
                    Label(source.name, systemImage: source.icon)
                }
            }
            Button("Cancel", role: .cancel) { }
        }
    }
    
    private func handlePlayButtonTap() {
        let sources = availableStreamingSources
        
        if sources.count == 1, let firstSource = sources.first, let url = URL(string: firstSource.url) {
            // Single source - open directly
            openURL(url)
        } else if sources.count > 1 {
            // Multiple sources - show picker
            showingStreamingPicker = true
        }
    }
    
    /// Auto-select the default release from the API, falling back to first release with art
    private func autoSelectFirstRelease() {
        guard let releases = recording?.releases, !releases.isEmpty else { return }
        
        // Prefer the API's default_release_id - this is computed server-side
        // to match the best_cover_art_* and best_spotify_url logic
        if let defaultId = recording?.defaultReleaseId,
           releases.contains(where: { $0.id == defaultId }) {
            selectedReleaseId = defaultId
            return
        }
        
        // Fallback: Sort and pick the first release with Spotify and cover art
        let sorted = releases.sorted { r1, r2 in
            let r1HasSpotify = r1.spotifyAlbumId != nil
            let r2HasSpotify = r2.spotifyAlbumId != nil
            if r1HasSpotify != r2HasSpotify {
                return r1HasSpotify && !r2HasSpotify
            }
            switch (r1.releaseYear, r2.releaseYear) {
            case (nil, nil): return false
            case (nil, _): return false
            case (_, nil): return true
            case let (y1?, y2?): return y1 > y2
            }
        }
        
        if let releaseWithSpotifyAndArt = sorted.first(where: {
            $0.spotifyAlbumId != nil && ($0.coverArtLarge != nil || $0.coverArtMedium != nil)
        }) {
            selectedReleaseId = releaseWithSpotifyAndArt.id
            return
        }
        
        if let releaseWithArt = sorted.first(where: { $0.coverArtLarge != nil || $0.coverArtMedium != nil }) {
            selectedReleaseId = releaseWithArt.id
            return
        }
        
        selectedReleaseId = sorted.first?.id
    }
    // MARK: - Learn More Section (Collapsible)
    
    @ViewBuilder
    private func learnMoreSection(_ recording: Recording) -> some View {
        let hasContent = recording.recordingYear != nil ||
                         recording.recordingDate != nil ||
                         recording.label != nil ||
                         recording.notes != nil ||
                         recording.musicbrainzId != nil
        
        if hasContent {
            VStack(alignment: .leading, spacing: 0) {
                // Collapsible header
                Button {
                    withAnimation(.easeInOut(duration: 0.2)) {
                        isLearnMoreExpanded.toggle()
                    }
                } label: {
                    HStack {
                        Text("Learn More")
                            .font(.headline)
                            .foregroundColor(JazzTheme.charcoal)
                        
                        Spacer()
                        
                        Image(systemName: isLearnMoreExpanded ? "chevron.up" : "chevron.down")
                            .font(.subheadline)
                            .foregroundColor(JazzTheme.brass)
                    }
                    .padding()
                    .background(JazzTheme.cardBackground)
                }
                .buttonStyle(.plain)
                
                // Expandable content
                if isLearnMoreExpanded {
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
                        
                        if let notes = recording.notes {
                            VStack(alignment: .leading, spacing: 4) {
                                HStack {
                                    Image(systemName: "note.text")
                                        .foregroundColor(JazzTheme.brass)
                                        .frame(width: 24)
                                    Text("Notes")
                                        .font(.subheadline)
                                        .foregroundColor(JazzTheme.smokeGray)
                                }
                                Text(notes)
                                    .font(.body)
                                    .foregroundColor(JazzTheme.charcoal)
                                    .padding(.leading, 32)
                            }
                        }
                        
                        // External References within Learn More
                        if recording.musicbrainzId != nil {
                            Divider()
                                .padding(.vertical, 4)
                            
                            ExternalReferencesPanel(
                                musicbrainzId: recording.musicbrainzId,
                                recordingId: recordingId,
                                albumTitle: recording.albumTitle ?? "Unknown Album"
                            )
                            .padding(.horizontal, -16) // Counteract parent padding
                        }
                    }
                    .padding()
                    .background(JazzTheme.cardBackground)
                }
            }
            .cornerRadius(10)
            .padding(.horizontal)
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

//
//  RecordingDetailView.swift
//  JazzReferenceMac
//
//  macOS-specific recording detail view
//

import SwiftUI

struct RecordingDetailView: View {
    let recordingId: String
    @State private var recording: Recording?
    @State private var isLoading = true
    @State private var localFavoriteCount: Int?
    @State private var showingLoginAlert = false
    @State private var selectedReleaseId: String?
    @State private var showingBackCover = false
    @State private var showingContributionSheet = false
    @Environment(\.dismiss) private var dismiss
    @EnvironmentObject var authManager: AuthenticationManager
    @EnvironmentObject var favoritesManager: FavoritesManager

    private let networkManager = NetworkManager()

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

    /// Image source for the currently displayed album art (for watermark badge)
    private var displayAlbumArtSource: String? {
        if let release = selectedRelease {
            return release.coverArtSource
        }
        return recording?.displayAlbumArtSource
    }

    /// Source URL for the currently displayed album art (for watermark badge)
    private var displayAlbumArtSourceUrl: String? {
        if let release = selectedRelease {
            return release.coverArtSourceUrl
        }
        return recording?.displayAlbumArtSourceUrl
    }

    /// Display title - selected release title or recording album title
    private var displayAlbumTitle: String {
        selectedRelease?.title ?? recording?.albumTitle ?? "Unknown Album"
    }

    /// Spotify URL - uses selected release if user picked one, otherwise uses bestSpotifyUrl
    private var displaySpotifyUrl: String? {
        if let release = selectedRelease {
            return release.spotifyTrackUrl
        }
        return recording?.bestSpotifyUrl
    }

    // MARK: - Favorites Computed Properties

    /// Whether the current user has favorited this recording
    private var isFavorited: Bool {
        favoritesManager.isFavorited(recordingId)
    }

    /// Display count for favorites (uses local count if available, otherwise from recording)
    private var displayFavoriteCount: Int {
        localFavoriteCount ?? recording?.favoriteCount ?? 0
    }

    var body: some View {
        ScrollView {
            if isLoading {
                ThemedProgressView(message: "Loading...")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .padding(.top, 100)
            } else if let recording = recording {
                VStack(alignment: .leading, spacing: 24) {
                    // Header with album art
                    recordingHeader(recording)

                    Divider()

                    // Recording info
                    recordingInfo(recording)

                    // Streaming links
                    streamingSection(recording)

                    // Performers
                    if let performers = recording.performers, !performers.isEmpty {
                        performersSection(performers)
                    }

                    // Community Data
                    communityDataSection(recording)

                    // Releases
                    if let releases = recording.releases, !releases.isEmpty {
                        releasesSection(releases)
                    }
                }
                .padding()
            } else {
                Text("Recording not found")
                    .foregroundColor(.secondary)
                    .padding(.top, 100)
            }
        }
        .background(JazzTheme.backgroundLight)
        .toolbar {
            ToolbarItem(placement: .cancellationAction) {
                Button("Close") {
                    dismiss()
                }
            }
            ToolbarItem(placement: .primaryAction) {
                Button {
                    handleFavoriteButtonTap()
                } label: {
                    HStack(spacing: 4) {
                        Image(systemName: isFavorited ? "heart.fill" : "heart")
                        if displayFavoriteCount > 0 {
                            Text("\(displayFavoriteCount)")
                                .font(JazzTheme.caption())
                        }
                    }
                }
                .buttonStyle(.borderedProminent)
                .tint(isFavorited ? .red : JazzTheme.burgundy)
                .help(isFavorited ? "Remove from favorites" : "Add to favorites")
            }
        }
        .alert("Sign In Required", isPresented: $showingLoginAlert) {
            Button("OK", role: .cancel) { }
        } message: {
            Text("Please sign in to favorite recordings.")
        }
        .sheet(isPresented: $showingContributionSheet) {
            if let recording = recording {
                MacRecordingContributionEditView(
                    recordingId: recordingId,
                    recordingTitle: "\(recording.songTitle ?? "Recording") - \(recording.albumTitle ?? "")",
                    currentContribution: recording.userContribution,
                    onSave: {
                        Task {
                            await loadRecording()
                        }
                    }
                )
                .environmentObject(authManager)
            }
        }
        .task(id: recordingId) {
            await loadRecording()
        }
    }

    // MARK: - View Components

    @ViewBuilder
    private func recordingHeader(_ recording: Recording) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            // Full-width album art with flip support
            ZStack(alignment: .topTrailing) {
                // Card-flip container
                ZStack {
                    // Front cover
                    if let frontUrl = displayAlbumArtLarge {
                        AsyncImage(url: URL(string: frontUrl)) { image in
                            image
                                .resizable()
                                .aspectRatio(contentMode: .fit)
                        } placeholder: {
                            Rectangle()
                                .fill(JazzTheme.cardBackground)
                                .aspectRatio(1, contentMode: .fit)
                                .overlay {
                                    ProgressView()
                                        .tint(JazzTheme.brass)
                                }
                        }
                        .opacity(showingBackCover ? 0 : 1)
                    } else {
                        albumArtPlaceholder
                            .aspectRatio(1, contentMode: .fit)
                            .opacity(showingBackCover ? 0 : 1)
                    }

                    // Back cover (pre-rotated so it appears correct after flip)
                    if let backUrl = displayBackCoverArtLarge {
                        AsyncImage(url: URL(string: backUrl)) { image in
                            image
                                .resizable()
                                .aspectRatio(contentMode: .fit)
                        } placeholder: {
                            Rectangle()
                                .fill(JazzTheme.cardBackground)
                                .aspectRatio(1, contentMode: .fit)
                                .overlay {
                                    ProgressView()
                                        .tint(JazzTheme.brass)
                                }
                        }
                        .rotation3DEffect(.degrees(180), axis: (x: 0, y: 1, z: 0))
                        .opacity(showingBackCover ? 1 : 0)
                    }
                }
                .frame(maxWidth: .infinity)
                .cornerRadius(12)
                .rotation3DEffect(
                    .degrees(showingBackCover ? 180 : 0),
                    axis: (x: 0, y: 1, z: 0)
                )
                .shadow(radius: 4)
                .animation(.easeInOut(duration: 0.3), value: selectedReleaseId)

                // Flip button badge (shown when back cover available)
                if canFlipToBackCover {
                    Button {
                        withAnimation(.easeInOut(duration: 0.4)) {
                            showingBackCover.toggle()
                        }
                    } label: {
                        Image(systemName: showingBackCover ? "arrow.uturn.backward" : "arrow.trianglehead.2.clockwise.rotate.90")
                            .foregroundColor(.white)
                            .font(.system(size: 14, weight: .semibold))
                            .padding(10)
                            .background(Color.black.opacity(0.6))
                            .clipShape(Circle())
                    }
                    .buttonStyle(.plain)
                    .padding(12)
                    .help(showingBackCover ? "Show front cover" : "Show back cover")
                }

                // Source badge (shows front or back cover source)
                VStack {
                    Spacer()
                    HStack {
                        if showingBackCover {
                            AlbumArtSourceBadge(
                                source: recording.backCoverSource,
                                sourceUrl: recording.backCoverSourceUrl
                            )
                            .padding(8)
                        } else {
                            AlbumArtSourceBadge(
                                source: displayAlbumArtSource,
                                sourceUrl: displayAlbumArtSourceUrl
                            )
                            .padding(8)
                        }
                        Spacer()
                    }
                }
            }

            // Song title, album title, and artist below the image
            VStack(alignment: .leading, spacing: 8) {
                // Recording Name (Year)
                HStack {
                    if recording.isCanonical == true {
                        Image(systemName: "star.fill")
                            .foregroundColor(JazzTheme.gold)
                    }
                    if let songTitle = recording.songTitle {
                        let yearSuffix = recording.recordingYear.map { " (\($0))" } ?? ""
                        Text("\(songTitle)\(yearSuffix)")
                            .font(JazzTheme.largeTitle())
                            .foregroundColor(JazzTheme.charcoal)
                    }
                }

                // Release Name (uses selected release if available)
                Text(displayAlbumTitle)
                    .font(JazzTheme.title2())
                    .foregroundColor(JazzTheme.smokeGray)
                    .animation(.easeInOut(duration: 0.3), value: selectedReleaseId)

                // Leader names
                if let performers = recording.performers {
                    let leaders = performers.filter { $0.role == "leader" }
                    if !leaders.isEmpty {
                        Text(leaders.map { $0.name }.joined(separator: ", "))
                            .font(JazzTheme.title3())
                            .foregroundColor(JazzTheme.brass)
                    }
                }

                // Label and Authority badge on the same row
                HStack(spacing: 12) {
                    if let label = recording.label {
                        Label(label, systemImage: "building.2")
                            .font(JazzTheme.subheadline())
                            .foregroundColor(JazzTheme.smokeGray)
                    }

                    if recording.hasAuthority, let badgeText = recording.authorityBadgeText {
                        AuthorityBadge(text: badgeText, source: recording.primaryAuthoritySource)
                    }
                }
            }
        }
    }

    private var albumArtPlaceholder: some View {
        Rectangle()
            .fill(JazzTheme.cardBackground)
            .overlay {
                Image(systemName: "music.note")
                    .font(.system(size: 50))
                    .foregroundColor(JazzTheme.smokeGray)
            }
    }

    @ViewBuilder
    private func recordingInfo(_ recording: Recording) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            if let notes = recording.notes, !notes.isEmpty {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Notes")
                        .font(JazzTheme.headline())
                        .foregroundColor(JazzTheme.charcoal)
                    Text(notes)
                        .font(JazzTheme.body())
                        .foregroundColor(JazzTheme.charcoal)
                }
            }

            if let date = recording.recordingDate {
                DetailRow(icon: "calendar", label: "Recording Date", value: date)
            }
        }
    }

    /// Get Spotify URL - uses selected release if available, otherwise falls back to streaming links or legacy field
    private func spotifyUrl(for recording: Recording) -> String? {
        // First check if we have a selected release with a Spotify URL
        if let release = selectedRelease, let trackUrl = release.spotifyTrackUrl {
            return trackUrl
        }
        // Fall back to streamingLinks or legacy field
        if let link = recording.streamingLinks?["spotify"], let url = link.bestPlaybackUrl {
            return url
        }
        return recording.bestSpotifyUrl
    }

    /// Get Apple Music URL from streamingLinks or legacy field
    private func appleMusicUrl(for recording: Recording) -> String? {
        if let link = recording.streamingLinks?["apple_music"], let url = link.bestPlaybackUrl {
            return url
        }
        return recording.appleMusicUrl
    }

    /// Get YouTube URL from streamingLinks or legacy field
    private func youtubeUrl(for recording: Recording) -> String? {
        if let link = recording.streamingLinks?["youtube"], let url = link.bestPlaybackUrl {
            return url
        }
        return recording.youtubeUrl
    }

    @ViewBuilder
    private func streamingSection(_ recording: Recording) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Listen")
                .font(JazzTheme.headline())
                .foregroundColor(JazzTheme.charcoal)

            HStack(spacing: 16) {
                if let spotifyUrlString = spotifyUrl(for: recording),
                   let url = URL(string: spotifyUrlString) {
                    Link(destination: url) {
                        HStack {
                            Image(systemName: "play.circle.fill")
                                .font(.title2)
                            Text("Spotify")
                        }
                        .padding(.horizontal, 16)
                        .padding(.vertical, 10)
                        .background(Color.green)
                        .foregroundColor(.white)
                        .cornerRadius(8)
                    }
                    .buttonStyle(.plain)
                }

                if let appleMusicUrlString = appleMusicUrl(for: recording),
                   let url = URL(string: appleMusicUrlString) {
                    Link(destination: url) {
                        HStack {
                            Image(systemName: "applelogo")
                                .font(.title2)
                            Text("Apple Music")
                        }
                        .padding(.horizontal, 16)
                        .padding(.vertical, 10)
                        .background(Color(red: 252/255, green: 60/255, blue: 68/255))
                        .foregroundColor(.white)
                        .cornerRadius(8)
                    }
                    .buttonStyle(.plain)
                }

                if let youtubeUrlString = youtubeUrl(for: recording),
                   let url = URL(string: youtubeUrlString) {
                    Link(destination: url) {
                        HStack {
                            Image(systemName: "play.rectangle.fill")
                                .font(.title2)
                            Text("YouTube")
                        }
                        .padding(.horizontal, 16)
                        .padding(.vertical, 10)
                        .background(Color.red)
                        .foregroundColor(.white)
                        .cornerRadius(8)
                    }
                    .buttonStyle(.plain)
                }
            }
        }
    }

    @ViewBuilder
    private func performersSection(_ performers: [Performer]) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Personnel (\(performers.count.formatted()))")
                .font(JazzTheme.headline())
                .foregroundColor(JazzTheme.charcoal)

            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
                ForEach(performers) { performer in
                    HStack {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(performer.name)
                                .font(JazzTheme.subheadline(weight: .medium))
                                .foregroundColor(JazzTheme.charcoal)

                            if let instrument = performer.instrument {
                                Text(instrument)
                                    .font(JazzTheme.caption())
                                    .foregroundColor(JazzTheme.smokeGray)
                            }
                        }

                        Spacer()

                        if let role = performer.role {
                            Text(role.capitalized)
                                .font(JazzTheme.caption2())
                                .padding(.horizontal, 6)
                                .padding(.vertical, 2)
                                .background(role == "leader" ? JazzTheme.burgundy : JazzTheme.brass.opacity(0.3))
                                .foregroundColor(role == "leader" ? .white : JazzTheme.charcoal)
                                .cornerRadius(4)
                        }
                    }
                    .padding(10)
                    .background(JazzTheme.cardBackground)
                    .cornerRadius(8)
                }
            }
        }
    }

    @ViewBuilder
    private func communityDataSection(_ recording: Recording) -> some View {
        MacCommunityDataSection(
            recordingId: recording.id,
            communityData: recording.communityData,
            userContribution: recording.userContribution,
            isAuthenticated: authManager.isAuthenticated,
            onEditTapped: {
                showingContributionSheet = true
            }
        )
    }

    @ViewBuilder
    private func releasesSection(_ releases: [Release]) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Releases (\(releases.count.formatted()))")
                    .font(JazzTheme.headline())
                    .foregroundColor(JazzTheme.charcoal)

                Spacer()

                Text("Click to change cover art")
                    .font(JazzTheme.caption())
                    .foregroundColor(JazzTheme.smokeGray)
            }

            ForEach(releases) { release in
                let isSelected = selectedReleaseId == release.id

                Button {
                    withAnimation(.easeInOut(duration: 0.3)) {
                        if selectedReleaseId == release.id {
                            // Deselect if already selected
                            selectedReleaseId = nil
                        } else {
                            selectedReleaseId = release.id
                        }
                        // Reset back cover when changing release
                        showingBackCover = false
                    }
                } label: {
                    HStack(spacing: 12) {
                        // Selection indicator
                        Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                            .font(JazzTheme.title3())
                            .foregroundColor(isSelected ? JazzTheme.burgundy : JazzTheme.smokeGray.opacity(0.5))

                        // Release cover art
                        AsyncImage(url: URL(string: release.coverArtSmall ?? "")) { image in
                            image
                                .resizable()
                                .aspectRatio(contentMode: .fill)
                        } placeholder: {
                            Rectangle()
                                .fill(JazzTheme.cardBackground)
                                .overlay {
                                    Image(systemName: "opticaldisc")
                                        .foregroundColor(JazzTheme.smokeGray)
                                }
                        }
                        .frame(width: 50, height: 50)
                        .cornerRadius(4)
                        .overlay(
                            RoundedRectangle(cornerRadius: 4)
                                .stroke(isSelected ? JazzTheme.burgundy : Color.clear, lineWidth: 2)
                        )

                        VStack(alignment: .leading, spacing: 2) {
                            Text(release.title)
                                .font(JazzTheme.subheadline(weight: isSelected ? .bold : .medium))
                                .foregroundColor(isSelected ? JazzTheme.burgundy : JazzTheme.charcoal)
                                .lineLimit(1)

                            HStack(spacing: 8) {
                                Text(release.yearDisplay)
                                    .font(JazzTheme.caption())
                                    .foregroundColor(JazzTheme.smokeGray)

                                if let format = release.formatName {
                                    Text("•")
                                        .foregroundColor(JazzTheme.smokeGray)
                                    Text(format)
                                        .font(JazzTheme.caption())
                                        .foregroundColor(JazzTheme.smokeGray)
                                }

                                if let label = release.label {
                                    Text("•")
                                        .foregroundColor(JazzTheme.smokeGray)
                                    Text(label)
                                        .font(JazzTheme.caption())
                                        .foregroundColor(JazzTheme.smokeGray)
                                        .lineLimit(1)
                                }
                            }
                        }

                        Spacer()

                        // Spotify indicator
                        if release.hasSpotify {
                            Image(systemName: "music.note")
                                .foregroundColor(.green)
                                .help("Available on Spotify")
                        }
                    }
                    .padding(10)
                    .background(isSelected ? JazzTheme.burgundy.opacity(0.1) : JazzTheme.cardBackground)
                    .cornerRadius(8)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
            }
        }
    }

    // MARK: - Data Loading

    private func loadRecording() async {
        isLoading = true
        recording = await fetchRecordingWithAuth()
        autoSelectFirstRelease()
        isLoading = false
    }

    /// Fetch recording detail, using authenticated request if user is logged in
    /// This ensures the user's contribution is included in the response
    private func fetchRecordingWithAuth() async -> Recording? {
        guard let url = URL(string: "\(NetworkManager.baseURL)/recordings/\(recordingId)") else {
            return nil
        }

        do {
            let data: Data
            if authManager.isAuthenticated {
                // Use authenticated request to get user's contribution
                data = try await authManager.makeAuthenticatedRequest(url: url)
            } else {
                // Unauthenticated request
                let (responseData, _) = try await URLSession.shared.data(from: url)
                data = responseData
            }
            return try JSONDecoder().decode(Recording.self, from: data)
        } catch {
            print("Error fetching recording detail: \(error)")
            return nil
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

    // MARK: - Favorites

    /// Handle favorite button tap - toggle favorite or show login prompt
    private func handleFavoriteButtonTap() {
        guard authManager.isAuthenticated else {
            showingLoginAlert = true
            return
        }

        Task {
            if let newCount = await favoritesManager.toggleFavorite(recordingId: recordingId) {
                localFavoriteCount = newCount
            }
        }
    }
}

#Preview {
    RecordingDetailView(recordingId: "preview-id")
        .environmentObject(AuthenticationManager())
        .environmentObject(FavoritesManager())
}

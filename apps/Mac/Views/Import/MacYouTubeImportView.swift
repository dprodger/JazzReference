//
//  MacYouTubeImportView.swift
//  JazzReferenceMac
//
//  View for completing YouTube video import by selecting a song
//

import SwiftUI

struct MacYouTubeImportView: View {
    let youtubeData: ImportedYouTubeData
    let onSuccess: () -> Void
    let onCancel: () -> Void

    @State private var searchText = ""
    @State private var searchResults: [Song] = []
    @State private var isSearching = false
    @State private var selectedSong: Song?
    @State private var isImporting = false
    @State private var importError: String?
    @State private var showingRecordingPicker = false
    @State private var showingRecordingChoice = false
    @State private var showingLogin = false

    @Environment(\.dismiss) private var dismiss
    @EnvironmentObject var authManager: AuthenticationManager

    private let networkManager = NetworkManager()

    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Button("Cancel") {
                    onCancel()
                    dismiss()
                }
                .keyboardShortcut(.cancelAction)

                Spacer()

                Text("Link to Song")
                    .font(.headline)

                Spacer()

                // Placeholder for symmetry
                Button("") { }
                    .hidden()
            }
            .padding()

            Divider()

            if !authManager.isAuthenticated {
                authRequiredView
            } else {
                // Video Info Header
                videoInfoHeader

                Divider()

                // Song Search
                songSearchSection

                Spacer()

                // Action Buttons
                if isImporting {
                    ProgressView("Importing...")
                        .padding()
                }
            }
        }
        .frame(minWidth: 500, minHeight: 500)
        .onAppear {
            if authManager.isAuthenticated {
                Task {
                    try? await Task.sleep(nanoseconds: 100_000_000)
                    let keywords = extractKeywords(from: youtubeData.title)
                    if !keywords.isEmpty {
                        await MainActor.run {
                            searchText = keywords
                        }
                        await searchSongs()
                    }
                }
            }
        }
        .alert("Import Error", isPresented: Binding(
            get: { importError != nil },
            set: { if !$0 { importError = nil } }
        )) {
            Button("OK") { importError = nil }
        } message: {
            Text(importError ?? "Unknown error")
        }
        .sheet(isPresented: $showingRecordingPicker) {
            if let song = selectedSong {
                MacRecordingPickerView(
                    song: song,
                    youtubeData: youtubeData,
                    onSelect: { recordingId in
                        Task {
                            await importVideo(songId: song.id, recordingId: recordingId)
                        }
                    },
                    onCancel: {
                        showingRecordingPicker = false
                    }
                )
            }
        }
        .confirmationDialog(
            "Link to Recording?",
            isPresented: $showingRecordingChoice,
            titleVisibility: .visible
        ) {
            Button("Pick a Recording") {
                showingRecordingPicker = true
            }
            Button("Skip - Link to Song Only") {
                if let song = selectedSong {
                    Task {
                        await importVideo(songId: song.id, recordingId: nil)
                    }
                }
            }
            Button("Cancel", role: .cancel) {
                selectedSong = nil
            }
        } message: {
            Text("You can link this transcription to a specific recording, or just to the song.")
        }
        .sheet(isPresented: $showingLogin) {
            MacLoginView()
                .environmentObject(authManager)
        }
    }

    // MARK: - Auth Required View

    private var authRequiredView: some View {
        VStack(spacing: 24) {
            Spacer()

            Image(systemName: "lock.fill")
                .font(.system(size: 50))
                .foregroundColor(.secondary)

            Text("Sign In Required")
                .font(.title2)
                .fontWeight(.semibold)

            Text("You need to be signed in to import YouTube videos")
                .font(.body)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)

            Button("Sign In") {
                showingLogin = true
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)

            Spacer()
        }
        .padding()
    }

    // MARK: - Video Info Header

    private var videoInfoHeader: some View {
        HStack(spacing: 12) {
            Image(systemName: "play.rectangle.fill")
                .font(.title)
                .foregroundColor(.red)

            VStack(alignment: .leading, spacing: 4) {
                Text(youtubeData.title)
                    .font(.headline)
                    .lineLimit(2)

                HStack(spacing: 8) {
                    Text(youtubeData.videoType.displayName)
                        .font(.caption)
                        .foregroundColor(.white)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 2)
                        .background(youtubeData.videoType == .transcription ? Color.blue : Color.green)
                        .cornerRadius(4)

                    if let channel = youtubeData.channelName {
                        Text(channel)
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
            }

            Spacer()
        }
        .padding()
        .background(Color(NSColor.controlBackgroundColor))
    }

    // MARK: - Song Search Section

    private var songSearchSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Search for a song to link this video to:")
                .font(.subheadline)
                .foregroundColor(.secondary)
                .padding(.horizontal)
                .padding(.top)

            // Search field
            HStack {
                Image(systemName: "magnifyingglass")
                    .foregroundColor(.secondary)

                TextField("Search songs...", text: $searchText)
                    .textFieldStyle(.plain)
                    .onSubmit {
                        Task { await searchSongs() }
                    }

                if !searchText.isEmpty {
                    Button(action: {
                        searchText = ""
                        searchResults = []
                    }) {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundColor(.secondary)
                    }
                    .buttonStyle(.plain)
                }

                if isSearching {
                    ProgressView()
                        .scaleEffect(0.7)
                }
            }
            .padding()
            .background(Color(NSColor.controlBackgroundColor))
            .cornerRadius(8)
            .padding(.horizontal)

            // Search Results
            if !searchResults.isEmpty {
                List {
                    ForEach(searchResults) { song in
                        Button(action: {
                            selectedSong = song
                            if youtubeData.videoType == .transcription {
                                showingRecordingChoice = true
                            } else {
                                Task {
                                    await importVideo(songId: song.id, recordingId: nil)
                                }
                            }
                        }) {
                            HStack {
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(song.title)
                                        .font(.headline)

                                    if let composer = song.composer {
                                        Text(composer)
                                            .font(.subheadline)
                                            .foregroundColor(.secondary)
                                    }
                                }

                                Spacer()

                                Image(systemName: "chevron.right")
                                    .foregroundColor(.secondary)
                            }
                            .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                    }
                }
            } else if !searchText.isEmpty && !isSearching {
                VStack(spacing: 8) {
                    Image(systemName: "music.note")
                        .font(.largeTitle)
                        .foregroundColor(.secondary)

                    Text("No songs found")
                        .font(.body)
                        .foregroundColor(.secondary)

                    Text("Try different keywords")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                .frame(maxWidth: .infinity)
                .padding(.top, 40)
            }
        }
    }

    // MARK: - Helper Functions

    private func extractKeywords(from title: String) -> String {
        var cleaned = title
            .replacingOccurrences(of: "Solo Transcription", with: "", options: .caseInsensitive)
            .replacingOccurrences(of: "Transcription", with: "", options: .caseInsensitive)
            .replacingOccurrences(of: "Backing Track", with: "", options: .caseInsensitive)
            .replacingOccurrences(of: "Play Along", with: "", options: .caseInsensitive)
            .replacingOccurrences(of: "Play-Along", with: "", options: .caseInsensitive)

        if let regex = try? NSRegularExpression(pattern: "\\([^)]*\\)", options: []) {
            cleaned = regex.stringByReplacingMatches(in: cleaned, range: NSRange(cleaned.startIndex..., in: cleaned), withTemplate: "")
        }

        let words = cleaned.split(separator: " ").prefix(3)
        return words.joined(separator: " ").trimmingCharacters(in: .whitespaces)
    }

    private func searchSongs() async {
        guard !searchText.isEmpty else { return }

        isSearching = true
        defer { isSearching = false }

        do {
            searchResults = try await networkManager.searchSongs(query: searchText)
        } catch {
            print("Search error: \(error)")
            searchResults = []
        }
    }

    private func importVideo(songId: String, recordingId: String?) async {
        isImporting = true
        defer { isImporting = false }

        let userId = authManager.currentUser?.id

        do {
            if youtubeData.videoType == .transcription {
                try await networkManager.createTranscription(
                    songId: songId,
                    recordingId: recordingId,
                    youtubeUrl: youtubeData.url,
                    userId: userId
                )
            } else {
                try await networkManager.createVideo(
                    songId: songId,
                    youtubeUrl: youtubeData.url,
                    videoType: "backing_track",
                    title: youtubeData.title,
                    userId: userId
                )
            }

            await MainActor.run {
                if youtubeData.videoType == .transcription {
                    NotificationCenter.default.post(
                        name: .transcriptionCreated,
                        object: nil,
                        userInfo: ["songId": songId]
                    )
                } else {
                    NotificationCenter.default.post(
                        name: .videoCreated,
                        object: nil,
                        userInfo: ["songId": songId]
                    )
                }
                onSuccess()
                dismiss()
            }
        } catch {
            importError = error.localizedDescription
        }
    }
}

// MARK: - Recording Picker View

struct MacRecordingPickerView: View {
    let song: Song
    let youtubeData: ImportedYouTubeData
    let onSelect: (String) -> Void
    let onCancel: () -> Void

    @State private var recordings: [Recording] = []
    @State private var isLoading = true
    @State private var loadError: String?
    @State private var searchText = ""

    @Environment(\.dismiss) private var dismiss

    private let networkManager = NetworkManager()

    private var sortedRecordings: [Recording] {
        recordings.sorted { r1, r2 in
            let artist1 = r1.artistCredit ?? ""
            let artist2 = r2.artistCredit ?? ""
            return artist1.localizedCaseInsensitiveCompare(artist2) == .orderedAscending
        }
    }

    private var filteredRecordings: [Recording] {
        if searchText.isEmpty {
            return sortedRecordings
        }
        let query = searchText.lowercased()
        return sortedRecordings.filter { recording in
            (recording.artistCredit?.lowercased().contains(query) ?? false) ||
            (recording.albumTitle?.lowercased().contains(query) ?? false) ||
            (recording.recordingYear.map { String($0).contains(query) } ?? false)
        }
    }

    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Button("Cancel") {
                    onCancel()
                    dismiss()
                }
                .keyboardShortcut(.cancelAction)

                Spacer()

                Text("Select Recording")
                    .font(.headline)

                Spacer()

                Button("") { }
                    .hidden()
            }
            .padding()

            Divider()

            if isLoading {
                Spacer()
                ProgressView("Loading recordings...")
                Spacer()
            } else if let error = loadError {
                Spacer()
                VStack(spacing: 12) {
                    Image(systemName: "exclamationmark.triangle")
                        .font(.largeTitle)
                        .foregroundColor(.orange)
                    Text(error)
                        .foregroundColor(.secondary)
                }
                Spacer()
            } else if recordings.isEmpty {
                Spacer()
                VStack(spacing: 12) {
                    Image(systemName: "opticaldisc")
                        .font(.largeTitle)
                        .foregroundColor(.secondary)
                    Text("No recordings found")
                    Text("This song doesn't have any recordings yet")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                Spacer()
            } else {
                // Search field
                HStack {
                    Image(systemName: "magnifyingglass")
                        .foregroundColor(.secondary)

                    TextField("Search by artist or album...", text: $searchText)
                        .textFieldStyle(.plain)

                    if !searchText.isEmpty {
                        Button(action: { searchText = "" }) {
                            Image(systemName: "xmark.circle.fill")
                                .foregroundColor(.secondary)
                        }
                        .buttonStyle(.plain)
                    }
                }
                .padding()
                .background(Color(NSColor.controlBackgroundColor))

                // Results count
                HStack {
                    Text("\(filteredRecordings.count) recording\(filteredRecordings.count == 1 ? "" : "s")")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Spacer()
                    Text("Sorted by artist")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                .padding(.horizontal)
                .padding(.vertical, 8)

                // Recordings list
                if filteredRecordings.isEmpty {
                    Spacer()
                    VStack(spacing: 8) {
                        Image(systemName: "magnifyingglass")
                            .font(.largeTitle)
                            .foregroundColor(.secondary)
                        Text("No matching recordings")
                            .foregroundColor(.secondary)
                    }
                    Spacer()
                } else {
                    List(filteredRecordings) { recording in
                        Button(action: {
                            onSelect(recording.id)
                            dismiss()
                        }) {
                            recordingRow(recording)
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
        }
        .frame(minWidth: 450, minHeight: 400)
        .task {
            await loadRecordings()
        }
    }

    private func recordingRow(_ recording: Recording) -> some View {
        HStack(spacing: 12) {
            // Album art placeholder
            if let artUrl = recording.bestAlbumArtSmall, let url = URL(string: artUrl) {
                AsyncImage(url: url) { image in
                    image.resizable().aspectRatio(contentMode: .fill)
                } placeholder: {
                    Color.gray.opacity(0.3)
                }
                .frame(width: 40, height: 40)
                .cornerRadius(4)
            } else {
                RoundedRectangle(cornerRadius: 4)
                    .fill(Color.gray.opacity(0.3))
                    .frame(width: 40, height: 40)
                    .overlay {
                        Image(systemName: "opticaldisc")
                            .foregroundColor(.gray)
                    }
            }

            VStack(alignment: .leading, spacing: 2) {
                Text(recording.albumTitle ?? "Unknown Album")
                    .font(.headline)

                HStack(spacing: 8) {
                    if let artist = recording.artistCredit {
                        Text(artist)
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }

                    if let year = recording.recordingYear {
                        Text("(\(String(year)))")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
            }

            Spacer()

            Image(systemName: "chevron.right")
                .foregroundColor(.secondary)
        }
        .padding(.vertical, 4)
    }

    private func loadRecordings() async {
        isLoading = true
        defer { isLoading = false }

        if let songDetail = await networkManager.fetchSongDetail(id: song.id) {
            recordings = songDetail.recordings ?? []
        } else {
            loadError = "Failed to load recordings"
        }
    }
}

extension Notification.Name {
    static let transcriptionCreated = Notification.Name("transcriptionCreated")
    static let videoCreated = Notification.Name("videoCreated")
}

#Preview {
    MacYouTubeImportView(
        youtubeData: ImportedYouTubeData(
            videoId: "abc123",
            title: "Chet Baker - Born to be Blue (Solo Transcription)",
            url: "https://www.youtube.com/watch?v=abc123",
            channelName: "Jazz Transcriptions",
            description: nil,
            videoType: .transcription
        ),
        onSuccess: { print("Success") },
        onCancel: { print("Cancel") }
    )
    .environmentObject(AuthenticationManager())
}

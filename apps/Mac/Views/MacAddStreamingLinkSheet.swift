//
//  MacAddStreamingLinkSheet.swift
//  JazzReferenceMac
//
//  Sheet for adding manual Spotify/Apple Music streaming links
//

import SwiftUI

struct MacAddStreamingLinkSheet: View {
    let recordingId: String
    let releaseId: String
    let releaseTitle: String
    let onSuccess: () -> Void

    @Environment(\.dismiss) var dismiss
    @EnvironmentObject var authManager: AuthenticationManager

    @State private var urlInput: String = ""
    @State private var isSaving = false
    @State private var errorMessage: String?
    @State private var successMessage: String?

    private let networkManager = NetworkManager()

    var body: some View {
        VStack(spacing: 0) {
            // Header
            headerView

            Divider()

            // Content
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    // Instructions
                    instructionsView

                    // URL Input
                    urlInputView

                    // Error/Success messages
                    if let error = errorMessage {
                        errorView(error)
                    }

                    if let success = successMessage {
                        successView(success)
                    }
                }
                .padding(20)
            }

            Divider()

            // Footer with buttons
            footerView
        }
        .frame(width: 500, height: 400)
        .background(JazzTheme.backgroundLight)
    }

    // MARK: - Header

    private var headerView: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text("Add Streaming Link")
                    .font(JazzTheme.title2())
                    .foregroundColor(JazzTheme.charcoal)

                Text(releaseTitle)
                    .font(JazzTheme.subheadline())
                    .foregroundColor(JazzTheme.smokeGray)
                    .lineLimit(1)
            }

            Spacer()

            Button {
                dismiss()
            } label: {
                Image(systemName: "xmark.circle.fill")
                    .font(.title2)
                    .foregroundColor(JazzTheme.smokeGray)
            }
            .buttonStyle(.plain)
        }
        .padding()
    }

    // MARK: - Instructions

    private var instructionsView: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Paste a Spotify or Apple Music track URL")
                .font(JazzTheme.headline())
                .foregroundColor(JazzTheme.charcoal)

            VStack(alignment: .leading, spacing: 8) {
                HStack(spacing: 8) {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(.green)
                        .font(.caption)
                    Text("Spotify: https://open.spotify.com/track/...")
                        .font(JazzTheme.caption())
                        .foregroundColor(JazzTheme.smokeGray)
                }

                HStack(spacing: 8) {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(.green)
                        .font(.caption)
                    Text("Apple Music: https://music.apple.com/.../song/...")
                        .font(JazzTheme.caption())
                        .foregroundColor(JazzTheme.smokeGray)
                }

                HStack(spacing: 8) {
                    Image(systemName: "info.circle")
                        .foregroundColor(JazzTheme.brass)
                        .font(.caption)
                    Text("This link will be preserved during automatic re-matching")
                        .font(JazzTheme.caption())
                        .foregroundColor(JazzTheme.smokeGray)
                }
            }
            .padding(12)
            .background(JazzTheme.cardBackground)
            .cornerRadius(8)
        }
    }

    // MARK: - URL Input

    private var urlInputView: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Track URL or ID")
                .font(JazzTheme.subheadline(weight: .medium))
                .foregroundColor(JazzTheme.charcoal)

            HStack {
                TextField("Paste URL here...", text: $urlInput)
                    .textFieldStyle(.roundedBorder)
                    .font(JazzTheme.body())
                    .disabled(isSaving)

                // Paste button
                Button {
                    if let clipboard = NSPasteboard.general.string(forType: .string) {
                        urlInput = clipboard
                    }
                } label: {
                    Image(systemName: "doc.on.clipboard")
                        .foregroundColor(JazzTheme.brass)
                }
                .buttonStyle(.plain)
                .help("Paste from clipboard")
                .disabled(isSaving)
            }

            // Service indicator based on input
            if !urlInput.isEmpty {
                serviceIndicator
            }
        }
    }

    @ViewBuilder
    private var serviceIndicator: some View {
        let service = detectService(from: urlInput)
        HStack(spacing: 6) {
            if let service = service {
                Image(systemName: service == "spotify" ? "checkmark.circle.fill" : "checkmark.circle.fill")
                    .foregroundColor(.green)
                Text("Detected: \(service == "spotify" ? "Spotify" : "Apple Music")")
                    .font(JazzTheme.caption())
                    .foregroundColor(.green)
            } else if urlInput.count > 5 {
                Image(systemName: "questionmark.circle")
                    .foregroundColor(.orange)
                Text("Could not detect service - will validate on save")
                    .font(JazzTheme.caption())
                    .foregroundColor(.orange)
            }
        }
    }

    /// Simple client-side service detection for UI feedback
    private func detectService(from input: String) -> String? {
        let trimmed = input.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.contains("spotify.com/track/") || trimmed.hasPrefix("spotify:track:") {
            return "spotify"
        }
        if trimmed.contains("music.apple.com") {
            return "apple_music"
        }
        // Check for raw IDs
        let alphanumericPattern = try? NSRegularExpression(pattern: "^[a-zA-Z0-9]{22}$")
        if alphanumericPattern?.firstMatch(in: trimmed, range: NSRange(trimmed.startIndex..., in: trimmed)) != nil {
            return "spotify"
        }
        let numericPattern = try? NSRegularExpression(pattern: "^\\d{9,12}$")
        if numericPattern?.firstMatch(in: trimmed, range: NSRange(trimmed.startIndex..., in: trimmed)) != nil {
            return "apple_music"
        }
        return nil
    }

    // MARK: - Messages

    private func errorView(_ message: String) -> some View {
        HStack(spacing: 8) {
            Image(systemName: "exclamationmark.triangle.fill")
                .foregroundColor(.red)
            Text(message)
                .font(JazzTheme.subheadline())
                .foregroundColor(.red)
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.red.opacity(0.1))
        .cornerRadius(8)
    }

    private func successView(_ message: String) -> some View {
        HStack(spacing: 8) {
            Image(systemName: "checkmark.circle.fill")
                .foregroundColor(.green)
            Text(message)
                .font(JazzTheme.subheadline())
                .foregroundColor(.green)
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.green.opacity(0.1))
        .cornerRadius(8)
    }

    // MARK: - Footer

    private var footerView: some View {
        HStack {
            Spacer()

            Button("Cancel") {
                dismiss()
            }
            .keyboardShortcut(.cancelAction)

            Button {
                Task {
                    await saveLink()
                }
            } label: {
                if isSaving {
                    ProgressView()
                        .scaleEffect(0.7)
                        .frame(width: 60)
                } else {
                    Text("Save")
                }
            }
            .buttonStyle(.borderedProminent)
            .tint(JazzTheme.burgundy)
            .disabled(urlInput.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || isSaving)
            .keyboardShortcut(.defaultAction)
        }
        .padding()
    }

    // MARK: - Actions

    private func saveLink() async {
        guard let token = authManager.getAccessToken() else {
            errorMessage = "Please sign in to add streaming links"
            return
        }

        let trimmedUrl = urlInput.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedUrl.isEmpty else {
            errorMessage = "Please enter a URL"
            return
        }

        isSaving = true
        errorMessage = nil
        successMessage = nil

        let response = await networkManager.addManualStreamingLink(
            recordingId: recordingId,
            releaseId: releaseId,
            url: trimmedUrl,
            authToken: token
        )

        await MainActor.run {
            isSaving = false

            if let response = response {
                if response.success {
                    let serviceName = response.service == "spotify" ? "Spotify" : "Apple Music"
                    successMessage = "\(serviceName) link added successfully!"

                    // Dismiss after a short delay
                    DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
                        onSuccess()
                        dismiss()
                    }
                } else {
                    errorMessage = response.error ?? "Failed to add link"
                }
            } else {
                errorMessage = "Network error. Please try again."
            }
        }
    }
}

#Preview {
    MacAddStreamingLinkSheet(
        recordingId: "test-recording",
        releaseId: "test-release",
        releaseTitle: "Kind of Blue",
        onSuccess: {}
    )
    .environmentObject(AuthenticationManager())
}

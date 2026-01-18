//
//  MacArtistCreationView.swift
//  JazzReferenceMac
//
//  Artist creation view for importing from the Share Extension
//

import SwiftUI

struct MacArtistCreationView: View {
    @Environment(\.dismiss) var dismiss

    // Form fields - pre-populated with imported data
    @State private var name: String
    @State private var musicbrainzId: String

    @State private var isSaving = false
    @State private var showingError = false
    @State private var errorMessage = ""

    // Initialize with imported data
    init(importedData: ImportedArtistData? = nil) {
        _name = State(initialValue: importedData?.name ?? "")
        _musicbrainzId = State(initialValue: importedData?.musicbrainzId ?? "")
    }

    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Button("Cancel") {
                    dismiss()
                }
                .keyboardShortcut(.cancelAction)

                Spacer()

                Text("Create Artist")
                    .font(.headline)

                Spacer()

                Button("Save") {
                    saveArtist()
                }
                .keyboardShortcut(.defaultAction)
                .disabled(name.isEmpty || isSaving)
            }
            .padding()

            Divider()

            // Form content
            Form {
                Section {
                    TextField("Artist Name", text: $name)
                        .textFieldStyle(.roundedBorder)

                    TextField("MusicBrainz ID", text: $musicbrainzId)
                        .textFieldStyle(.roundedBorder)
                        .font(.system(.body, design: .monospaced))
                } header: {
                    Text("Basic Information")
                }

                Section {
                    Text("Additional details (bio, dates, instruments) will be automatically fetched by the backend.")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
            .formStyle(.grouped)
            .padding()

            if isSaving {
                ProgressView("Saving...")
                    .padding()
            }
        }
        .frame(minWidth: 400, minHeight: 300)
        .alert("Error", isPresented: $showingError) {
            Button("OK", role: .cancel) { }
        } message: {
            Text(errorMessage)
        }
    }

    private func saveArtist() {
        guard !name.isEmpty else {
            errorMessage = "Artist name is required"
            showingError = true
            return
        }

        isSaving = true

        Task {
            do {
                try await saveArtistToAPI()

                await MainActor.run {
                    isSaving = false
                    print("Artist saved successfully")
                    NotificationCenter.default.post(name: .artistCreated, object: nil)
                    dismiss()
                }
            } catch {
                await MainActor.run {
                    isSaving = false
                    errorMessage = "Failed to save artist: \(error.localizedDescription)"
                    showingError = true
                }
            }
        }
    }

    private func saveArtistToAPI() async throws {
        guard let url = URL(string: "\(NetworkManager.baseURL)/performers") else {
            throw URLError(.badURL)
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let artistData: [String: Any] = [
            "name": name,
            "musicbrainz_id": musicbrainzId.isEmpty ? NSNull() : musicbrainzId,
        ]

        request.httpBody = try JSONSerialization.data(withJSONObject: artistData)

        print("Sending artist creation request:")
        print("   URL: \(url)")
        print("   Name: \(name)")

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw URLError(.badServerResponse)
        }

        print("Response status: \(httpResponse.statusCode)")

        switch httpResponse.statusCode {
        case 200...299:
            if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                print("Success response: \(json)")
            }

        case 409:
            if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let error = json["error"] as? String {
                throw ArtistCreationError.alreadyExists(error)
            }
            throw ArtistCreationError.alreadyExists("Artist already exists")

        case 400:
            if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let error = json["error"] as? String {
                throw ArtistCreationError.validationError(error)
            }
            throw ArtistCreationError.validationError("Invalid data")

        default:
            if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let error = json["error"] as? String {
                throw ArtistCreationError.serverError(error)
            }
            throw ArtistCreationError.serverError("Server returned status \(httpResponse.statusCode)")
        }
    }
}

enum ArtistCreationError: LocalizedError {
    case alreadyExists(String)
    case validationError(String)
    case serverError(String)

    var errorDescription: String? {
        switch self {
        case .alreadyExists(let message):
            return "Artist Already Exists: \(message)"
        case .validationError(let message):
            return "Validation Error: \(message)"
        case .serverError(let message):
            return "Server Error: \(message)"
        }
    }
}

extension Notification.Name {
    static let artistCreated = Notification.Name("artistCreated")
}

#Preview {
    MacArtistCreationView(importedData: ImportedArtistData(
        name: "Miles Davis",
        musicbrainzId: "561d854a-6a28-4aa7-8c99-323e6ce46c2a",
        sourceUrl: "https://musicbrainz.org/artist/561d854a-6a28-4aa7-8c99-323e6ce46c2a",
        importedAt: Date()
    ))
}

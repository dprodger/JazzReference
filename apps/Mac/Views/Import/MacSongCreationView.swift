//
//  MacSongCreationView.swift
//  JazzReferenceMac
//
//  Song creation view for importing from the Share Extension
//

import SwiftUI

struct MacSongCreationView: View {
    @Environment(\.dismiss) var dismiss

    // Form fields - pre-populated with imported data
    @State private var title: String
    @State private var composer: String
    @State private var musicbrainzId: String
    @State private var workType: String
    @State private var key: String

    @State private var isSaving = false
    @State private var showingError = false
    @State private var errorMessage = ""

    // Initialize with imported data
    init(importedData: ImportedSongData? = nil) {
        _title = State(initialValue: importedData?.title ?? "")
        _composer = State(initialValue: importedData?.composerString ?? "")
        _musicbrainzId = State(initialValue: importedData?.musicbrainzId ?? "")
        _workType = State(initialValue: importedData?.workType ?? "")
        _key = State(initialValue: importedData?.key ?? "")
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

                Text("Create Song")
                    .font(.headline)

                Spacer()

                Button("Save") {
                    saveSong()
                }
                .keyboardShortcut(.defaultAction)
                .disabled(title.isEmpty || isSaving)
            }
            .padding()

            Divider()

            // Form content
            Form {
                Section {
                    TextField("Song Title", text: $title)
                        .textFieldStyle(.roundedBorder)

                    TextField("Composer", text: $composer)
                        .textFieldStyle(.roundedBorder)

                    TextField("MusicBrainz ID", text: $musicbrainzId)
                        .textFieldStyle(.roundedBorder)
                        .font(.system(.body, design: .monospaced))
                } header: {
                    Text("Basic Information")
                }

                Section {
                    TextField("Work Type (e.g., Song, Instrumental)", text: $workType)
                        .textFieldStyle(.roundedBorder)

                    TextField("Key (e.g., Eb, F minor)", text: $key)
                        .textFieldStyle(.roundedBorder)
                } header: {
                    Text("Additional Details")
                }

                Section {
                    Text("Additional details (structure, recordings) can be added later through the app.")
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
        .frame(minWidth: 400, minHeight: 400)
        .alert("Error", isPresented: $showingError) {
            Button("OK", role: .cancel) { }
        } message: {
            Text(errorMessage)
        }
    }

    private func saveSong() {
        guard !title.isEmpty else {
            errorMessage = "Song title is required"
            showingError = true
            return
        }

        isSaving = true

        Task {
            do {
                try await saveSongToAPI()

                await MainActor.run {
                    isSaving = false
                    print("Song saved successfully")
                    NotificationCenter.default.post(name: .songCreated, object: nil)
                    dismiss()
                }
            } catch {
                await MainActor.run {
                    isSaving = false
                    errorMessage = "Failed to save song: \(error.localizedDescription)"
                    showingError = true
                }
            }
        }
    }

    private func saveSongToAPI() async throws {
        guard let url = URL(string: "\(NetworkManager.baseURL)/songs") else {
            throw URLError(.badURL)
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        var songData: [String: Any] = [
            "title": title,
        ]

        if !composer.isEmpty {
            songData["composer"] = composer
        }
        if !musicbrainzId.isEmpty {
            songData["musicbrainz_id"] = musicbrainzId
        }
        if !workType.isEmpty {
            songData["external_references"] = ["work_type": workType]
        }

        request.httpBody = try JSONSerialization.data(withJSONObject: songData)

        print("Sending song creation request:")
        print("   URL: \(url)")
        print("   Title: \(title)")

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw URLError(.badServerResponse)
        }

        guard httpResponse.statusCode == 201 || httpResponse.statusCode == 200 else {
            if let errorDict = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let errorMsg = errorDict["error"] as? String {
                throw NSError(domain: "API", code: httpResponse.statusCode,
                            userInfo: [NSLocalizedDescriptionKey: errorMsg])
            }
            throw URLError(.badServerResponse)
        }

        print("Song created successfully (status: \(httpResponse.statusCode))")
    }
}

extension Notification.Name {
    static let songCreated = Notification.Name("songCreated")
}

#Preview {
    MacSongCreationView(importedData: ImportedSongData(
        title: "All the Things You Are",
        musicbrainzId: "bc8bca8d-967d-305d-9291-0b73cdd6f930",
        composers: ["Jerome Kern", "Oscar Hammerstein II"],
        workType: "Song",
        key: "A flat major",
        annotation: nil,
        wikipediaUrl: nil,
        sourceUrl: nil,
        importedAt: Date()
    ))
}

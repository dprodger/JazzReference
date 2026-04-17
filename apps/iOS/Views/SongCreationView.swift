//
//  SongCreationView.swift
//  Approach Note
//
//  Created by Dave Rodger on 11/1/25.
//

import SwiftUI
import os

// Notification for when a song is created and lists need to refresh
extension Notification.Name {
    static let songCreated = Notification.Name("songCreated")
}

struct SongCreationView: View {
    @Environment(\.dismiss) var dismiss
    @EnvironmentObject var authManager: AuthenticationManager

    // Form fields - pre-populated with imported data
    @State private var title: String
    @State private var composer: String
    @State private var musicbrainzId: String
    @State private var workType: String
    @State private var key: String
    
    @State private var isSaving = false
    @State private var showingError = false
    @State private var errorMessage = ""
    
    // Initialize with imported data (or empty if creating manually)
    init(importedData: ImportedSongData? = nil) {
        NSLog("🎨 SongCreationView.init()")
        NSLog("   Received title: '%@'", importedData?.title ?? "NIL")
        
        _title = State(initialValue: importedData?.title ?? "")
        _composer = State(initialValue: importedData?.composerString ?? "")
        _musicbrainzId = State(initialValue: importedData?.musicbrainzId ?? "")
        _workType = State(initialValue: importedData?.workType ?? "")
        _key = State(initialValue: importedData?.key ?? "")
        
        NSLog("✅ Init complete, title state: '%@'", importedData?.title ?? "EMPTY")
    }
    
    var body: some View {
        NavigationView {
            Form {
                Section(header: Text("Basic Information")) {
                    TextField("Song Title", text: $title)
                    TextField("Composer", text: $composer)
                    TextField("MusicBrainz ID", text: $musicbrainzId)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .font(.system(.body, design: .monospaced))
                }
                
                Section(header: Text("Additional Details")) {
                    TextField("Work Type (e.g., Song, Instrumental)", text: $workType)
                    TextField("Key (e.g., Eb, F minor)", text: $key)
                }
                
                Section {
                    Text("Additional details (structure, recordings) can be added later through the app.")
                        .font(ApproachNoteTheme.caption())
                        .foregroundColor(.secondary)
                }
                
                Section {
                    Button(action: saveSong) {
                        if isSaving {
                            HStack {
                                ProgressView()
                                Text("Creating Song...")
                            }
                        } else {
                            Text("Create Song")
                                .frame(maxWidth: .infinity)
                        }
                    }
                    .disabled(title.isEmpty || isSaving)
                    .foregroundColor(title.isEmpty ? Color.gray : Color.blue)
                }
            }
            .navigationTitle("Create Song")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Cancel") {
                        dismiss()
                    }
                }
            }
            .onAppear {
                NSLog("📱 SongCreationView.onAppear()")
                NSLog("   title = '%@'", title)
                NSLog("   composer = '%@'", composer)
                NSLog("   musicbrainzId = '%@'", musicbrainzId)
            }
            .alert("Error", isPresented: $showingError) {
                Button("OK", role: .cancel) { }
            } message: {
                Text(errorMessage)
            }
        }
    }
    
    private func saveSong() {
        // Validate required fields
        guard !title.isEmpty else {
            errorMessage = "Song title is required"
            showingError = true
            return
        }
        
        isSaving = true
        
        // Save song to API
        Task {
            do {
                try await saveSongToAPI()
                
                await MainActor.run {
                    isSaving = false
                    Log.ui.info("Song saved successfully")
                    // Notify SongsListView to refresh
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
    
    // MARK: - API Integration
    
    private func saveSongToAPI() async throws {
        let url = URL.api(path: "/songs")

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

        let body = try JSONSerialization.data(withJSONObject: songData)

        Log.ui.debug("Sending song creation request: url=\(url, privacy: .private), title=\(title, privacy: .public), composer=\(composer, privacy: .public), musicbrainzId=\(musicbrainzId, privacy: .private)")

        _ = try await authManager.makeAuthenticatedRequest(
            url: url,
            method: "POST",
            body: body
        )

        Log.ui.info("Song created successfully")
    }
}

#Preview {
    SongCreationView(importedData: ImportedSongData(
        title: "All the Things You Are",
        musicbrainzId: "bc8bca8d-967d-305d-9291-0b73cdd6f930",
        composers: ["Jerome Kern", "Oscar Hammerstein II"],
        workType: "Song",
        key: "A♭ major",
        annotation: nil,
        wikipediaUrl: nil,
        sourceUrl: nil,
        importedAt: Date()
    ))
}

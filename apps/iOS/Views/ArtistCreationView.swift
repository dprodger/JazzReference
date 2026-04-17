//
//  ArtistCreationView.swift
//  Approach Note
//
//  Simple artist creation view that works with imported MusicBrainz data
//  SIMPLIFIED VERSION - Only name, MusicBrainz ID, and Wikipedia URL
//

import SwiftUI
import os

// Notification for when an artist is created and lists need to refresh
extension Notification.Name {
    static let artistCreated = Notification.Name("artistCreated")
}

struct ArtistCreationView: View {
    @Environment(\.dismiss) var dismiss
    @EnvironmentObject var authManager: AuthenticationManager

    // Form fields - pre-populated with imported data (minimal set only)
    @State private var name: String
    @State private var musicbrainzId: String
    
    @State private var isSaving = false
    @State private var showingError = false
    @State private var errorMessage = ""
    
    // Initialize with imported data (or empty if creating manually)
    init(importedData: ImportedArtistData? = nil) {
        NSLog("🎨 ArtistCreationView.init()")
        NSLog("   Received name: '%@'", importedData?.name ?? "NIL")
        
        _name = State(initialValue: importedData?.name ?? "")
        _musicbrainzId = State(initialValue: importedData?.musicbrainzId ?? "")
        
        NSLog("✅ Init complete, name state: '%@'", importedData?.name ?? "EMPTY")
    }
    
    var body: some View {
        NavigationView {
            Form {
                Section(header: Text("Basic Information")) {
                    TextField("Artist Name", text: $name)
                    TextField("MusicBrainz ID", text: $musicbrainzId)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .font(.system(.body, design: .monospaced))
                }
                
                Section {
                    Text("Additional details (bio, dates, instruments) will be automatically fetched by the backend.")
                        .font(ApproachNoteTheme.caption())
                        .foregroundColor(.gray)
                }
                
                Section {
                    Button(action: saveArtist) {
                        HStack {
                            Spacer()
                            if isSaving {
                                ProgressView()
                                    .progressViewStyle(CircularProgressViewStyle(tint: .white))
                            } else {
                                Text("Save Artist")
                                    .foregroundColor(.white)
                            }
                            Spacer()
                        }
                    }
                    .disabled(name.isEmpty || isSaving)
                    .listRowBackground(name.isEmpty ? Color.gray : Color.blue)
                }
            }
            .navigationTitle("Create Artist")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Cancel") {
                        dismiss()
                    }
                }
            }
            .onAppear {
                NSLog("📱 ArtistCreationView.onAppear()")
                NSLog("   name = '%@'", name)
                NSLog("   musicbrainzId = '%@'", musicbrainzId)
            }
            .alert("Error", isPresented: $showingError) {
                Button("OK", role: .cancel) { }
            } message: {
                Text(errorMessage)
            }
        }
    }
    
    private func saveArtist() {
        // Validate required fields
        guard !name.isEmpty else {
            errorMessage = "Artist name is required"
            showingError = true
            return
        }
        
        isSaving = true
        
        // Save artist to API
        Task {
            do {
                try await saveArtistToAPI()
                
                await MainActor.run {
                    isSaving = false
                    Log.ui.info("Artist saved successfully")
                    // Notify ArtistsListView to refresh
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
    
    // MARK: - API Integration
    
    private func saveArtistToAPI() async throws {
        let url = URL.api(path: "/performers")

        let artistData: [String: Any] = [
            "name": name,
            "musicbrainz_id": musicbrainzId.isEmpty ? NSNull() : musicbrainzId,
        ]

        let body = try JSONSerialization.data(withJSONObject: artistData)

        Log.ui.debug("Sending artist creation request: url=\(url, privacy: .private), name=\(name, privacy: .public), musicbrainzId=\(musicbrainzId, privacy: .private)")

        _ = try await authManager.makeAuthenticatedRequest(
            url: url,
            method: "POST",
            body: body
        )

        Log.ui.info("Artist created successfully")
    }
}

// MARK: - Preview
#Preview {
    ArtistCreationView(importedData: ImportedArtistData(
        name: "Miles Davis",
        musicbrainzId: "561d854a-6a28-4aa7-8c99-323e6ce46c2a",
        sourceUrl: "https://musicbrainz.org/artist/561d854a-6a28-4aa7-8c99-323e6ce46c2a",
        importedAt: Date()
    ))
}

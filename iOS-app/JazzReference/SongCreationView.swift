//
//  SongCreationView.swift
//  JazzReference
//
//  Created by Dave Rodger on 11/1/25.
//

import SwiftUI

struct SongCreationView: View {
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
                        .font(JazzTheme.caption())
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
                    print("✅ Song saved successfully")
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
        guard let url = URL(string: "\(NetworkManager.baseURL)/songs") else {
            throw URLError(.badURL)
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        // Build request body
        var songData: [String: Any] = [
            "title": title,
        ]
        
        // Add optional fields only if they're not empty
        if !composer.isEmpty {
            songData["composer"] = composer
        }
        if !musicbrainzId.isEmpty {
            songData["musicbrainz_id"] = musicbrainzId
        }
        if !workType.isEmpty {
            // Store work type in external_references as metadata
            songData["external_references"] = ["work_type": workType]
        }
        if !key.isEmpty {
            // Could add key to structure field or external_references
            // For now, we'll skip it as the schema doesn't have a dedicated key field
        }
        
        // Convert to JSON
        request.httpBody = try JSONSerialization.data(withJSONObject: songData)
        
        // Log the request (for debugging)
        print("📤 Sending song creation request:")
        print("   URL: \(url)")
        print("   Title: \(title)")
        if !composer.isEmpty {
            print("   Composer: \(composer)")
        }
        if !musicbrainzId.isEmpty {
            print("   MusicBrainz ID: \(musicbrainzId)")
        }
        
        // Perform request
        let (data, response) = try await URLSession.shared.data(for: request)
        
        // Check response
        guard let httpResponse = response as? HTTPURLResponse else {
            throw URLError(.badServerResponse)
        }
        
        guard httpResponse.statusCode == 201 || httpResponse.statusCode == 200 else {
            // Try to parse error message from response
            if let errorDict = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let errorMsg = errorDict["error"] as? String {
                throw NSError(domain: "API", code: httpResponse.statusCode,
                            userInfo: [NSLocalizedDescriptionKey: errorMsg])
            }
            throw URLError(.badServerResponse)
        }
        
        print("✅ Song created successfully (status: \(httpResponse.statusCode))")
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

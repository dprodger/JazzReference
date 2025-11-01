//
//  ArtistCreationView.swift
//  JazzReference
//
//  Simple artist creation view that works with imported MusicBrainz data
//  SIMPLIFIED VERSION - Only name, MusicBrainz ID, and Wikipedia URL
//

import SwiftUI

struct ArtistCreationView: View {
    @Environment(\.dismiss) var dismiss
    
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
                        .font(.caption)
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
                    print("✅ Artist saved successfully")
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
        guard let url = URL(string: "\(NetworkManager.baseURL)/performers") else {
            throw URLError(.badURL)
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        // Build request body with only the minimal fields
        // Backend will handle fetching additional details based on MusicBrainz ID
        let artistData: [String: Any] = [
            "name": name,
            "musicbrainz_id": musicbrainzId.isEmpty ? NSNull() : musicbrainzId,
        ]
        
        // Convert to JSON
        request.httpBody = try JSONSerialization.data(withJSONObject: artistData)
        
        // Log the request (for debugging)
        print("📤 Sending artist creation request:")
        print("   URL: \(url)")
        print("   Name: \(name)")
        if !musicbrainzId.isEmpty {
            print("   MusicBrainz ID: \(musicbrainzId)")
        }
        
        // Perform request
        let (data, response) = try await URLSession.shared.data(for: request)
        
        // Check response
        guard let httpResponse = response as? HTTPURLResponse else {
            throw URLError(.badServerResponse)
        }
        
        print("📥 Response status: \(httpResponse.statusCode)")
        
        // Handle different status codes
        switch httpResponse.statusCode {
        case 200...299:
            // Success
            if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                print("✅ Success response: \(json)")
            }
            
        case 409:
            // Conflict - artist already exists
            if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let error = json["error"] as? String {
                throw ArtistCreationError.alreadyExists(error)
            }
            throw ArtistCreationError.alreadyExists("Artist already exists")
            
        case 400:
            // Bad request - validation error
            if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let error = json["error"] as? String {
                throw ArtistCreationError.validationError(error)
            }
            throw ArtistCreationError.validationError("Invalid data")
            
        default:
            // Other error
            if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let error = json["error"] as? String {
                throw ArtistCreationError.serverError(error)
            }
            throw ArtistCreationError.serverError("Server returned status \(httpResponse.statusCode)")
        }
    }
}

// MARK: - Error Types

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

// MARK: - Preview
#Preview {
    ArtistCreationView(importedData: ImportedArtistData(
        name: "Miles Davis",
        musicbrainzId: "561d854a-6a28-4aa7-8c99-323e6ce46c2a",
        sourceUrl: "https://musicbrainz.org/artist/561d854a-6a28-4aa7-8c99-323e6ce46c2a",
        importedAt: Date()
    ))
}

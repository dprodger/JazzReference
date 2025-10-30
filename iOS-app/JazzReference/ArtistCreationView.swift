//
//  ArtistCreationView.swift
//  JazzReference
//
//  Simple artist creation view that works with imported MusicBrainz data
//  THIS IS A MINIMAL WORKING VERSION - Customize for your needs
//

import SwiftUI

struct ArtistCreationView: View {
    @Environment(\.dismiss) var dismiss
    
    // Form fields - pre-populated with imported data
    @State private var name: String
    @State private var musicbrainzId: String
    @State private var biography: String
    @State private var birthDate: String
    @State private var deathDate: String
    @State private var instruments: String
    @State private var wikipediaUrl: String
    
    @State private var isSaving = false
    @State private var showingError = false
    @State private var errorMessage = ""
    
    // Initialize with imported data (or empty if creating manually)
    init(importedData: ImportedArtistData? = nil) {
        _name = State(initialValue: importedData?.name ?? "")
        _musicbrainzId = State(initialValue: importedData?.musicbrainzId ?? "")
        _biography = State(initialValue: importedData?.biography ?? "")
        _birthDate = State(initialValue: importedData?.formattedBirthDate ?? "")
        _deathDate = State(initialValue: importedData?.formattedDeathDate ?? "")
        _instruments = State(initialValue: importedData?.instruments?.joined(separator: ", ") ?? "")
        _wikipediaUrl = State(initialValue: importedData?.wikipediaUrl ?? "")
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
                
                Section(header: Text("Biography")) {
                    TextEditor(text: $biography)
                        .frame(minHeight: 100)
                }
                
                Section(header: Text("Dates")) {
                    TextField("Birth Date (YYYY-MM-DD or YYYY)", text: $birthDate)
                        .textInputAutocapitalization(.never)
                    TextField("Death Date (YYYY-MM-DD or YYYY)", text: $deathDate)
                        .textInputAutocapitalization(.never)
                }
                
                Section(header: Text("Additional Information")) {
                    TextField("Instruments (comma-separated)", text: $instruments)
                    TextField("Wikipedia URL", text: $wikipediaUrl)
                        .textInputAutocapitalization(.never)
                        .keyboardType(.URL)
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
        
        // TODO: Replace this with your actual API call
        // For now, this is a placeholder that simulates saving
        
        print("💾 Saving artist:")
        print("   Name: \(name)")
        print("   MusicBrainz ID: \(musicbrainzId)")
        print("   Biography: \(biography.prefix(50))...")
        
        // Simulate API call
        Task {
            do {
                // TODO: Uncomment and implement your API call
                // try await saveArtistToAPI()
                
                // Simulate network delay
                try await Task.sleep(nanoseconds: 1_000_000_000)
                
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
    
    // TODO: Implement your actual API call here
    private func saveArtistToAPI() async throws {
        // Example API implementation:
        /*
        guard let url = URL(string: "\(NetworkManager.baseURL)/artists") else {
            throw NSError(domain: "Invalid URL", code: 0)
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let artistData: [String: Any] = [
            "name": name,
            "musicbrainz_id": musicbrainzId.isEmpty ? NSNull() : musicbrainzId,
            "biography": biography.isEmpty ? NSNull() : biography,
            "birth_date": birthDate.isEmpty ? NSNull() : birthDate,
            "death_date": deathDate.isEmpty ? NSNull() : deathDate,
            "instruments": instruments.isEmpty ? [] : instruments.split(separator: ",").map { $0.trimmingCharacters(in: .whitespaces) },
            "wikipedia_url": wikipediaUrl.isEmpty ? NSNull() : wikipediaUrl
        ]
        
        request.httpBody = try JSONSerialization.data(withJSONObject: artistData)
        
        let (_, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse,
              (200...299).contains(httpResponse.statusCode) else {
            throw NSError(domain: "API Error", code: 0)
        }
        */
    }
}

// MARK: - Preview
#Preview {
    ArtistCreationView(importedData: ImportedArtistData(
        name: "Miles Davis",
        musicbrainzId: "561d854a-6a28-4aa7-8c99-323e6ce46c2a",
        biography: "Miles Dewey Davis III was an American jazz trumpeter, bandleader, and composer. He is among the most influential and acclaimed figures in the history of jazz and 20th-century music.",
        birthDate: "1926-05-26",
        deathDate: "1991-09-28",
        instruments: ["trumpet", "flugelhorn"],
        wikipediaUrl: "https://en.wikipedia.org/wiki/Miles_Davis",
        sourceUrl: "https://musicbrainz.org/artist/561d854a-6a28-4aa7-8c99-323e6ce46c2a",
        importedAt: Date()
    ))
}

//
//  AuthorityRecommendation.swift
//  JazzReference
//
//  Created by Dave Rodger on 11/28/25.
//  View and manage authority recommendations for a recording
//

import SwiftUI

// MARK: - Authority Recommendations View

struct AuthorityRecommendationsView: View {
    let recordingId: String
    let albumTitle: String
    
    @State private var authorities: [AuthorityRecommendation] = []
    @State private var isLoading = true
    @State private var errorMessage: String?
    @State private var showingAddSheet = false
    @State private var deleteTarget: AuthorityRecommendation?
    @State private var showingDeleteConfirmation = false
    
    @Environment(\.dismiss) private var dismiss
    @Environment(\.openURL) private var openURL
    
    var body: some View {
        NavigationStack {
            Group {
                if isLoading {
                    ProgressView("Loading...")
                        .tint(JazzTheme.brass)
                } else if let error = errorMessage {
                    VStack(spacing: 16) {
                        Image(systemName: "exclamationmark.triangle")
                            .font(.largeTitle)
                            .foregroundColor(.red)
                        Text(error)
                            .foregroundColor(.secondary)
                        Button("Retry") {
                            Task { await loadAuthorities() }
                        }
                        .buttonStyle(.bordered)
                    }
                    .padding()
                } else if authorities.isEmpty {
                    VStack(spacing: 16) {
                        Image(systemName: "doc.badge.plus")
                            .font(.system(size: 48))
                            .foregroundColor(JazzTheme.smokeGray)
                        Text("No Authority References")
                            .font(.headline)
                            .foregroundColor(JazzTheme.charcoal)
                        Text("This recording has no authority recommendations linked to it.")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal)
                    }
                    .padding()
                } else {
                    List {
                        ForEach(authorities) { authority in
                            AuthorityRowView(authority: authority)
                                .swipeActions(edge: .trailing, allowsFullSwipe: false) {
                                    Button(role: .destructive) {
                                        deleteTarget = authority
                                        showingDeleteConfirmation = true
                                    } label: {
                                        Label("Delete", systemImage: "trash")
                                    }
                                }
                                .onTapGesture {
                                    if let urlString = authority.sourceUrl,
                                       let url = URL(string: urlString) {
                                        openURL(url)
                                    }
                                }
                        }
                    }
                    .listStyle(.insetGrouped)
                }
            }
            .navigationTitle("Authority References")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Done") {
                        dismiss()
                    }
                }
                ToolbarItem(placement: .primaryAction) {
                    Button {
                        showingAddSheet = true
                    } label: {
                        Image(systemName: "plus")
                    }
                }
            }
            .sheet(isPresented: $showingAddSheet) {
                AddAuthorityView(recordingId: recordingId) { newAuthority in
                    authorities.append(newAuthority)
                    showingAddSheet = false
                }
            }
            .confirmationDialog(
                "Delete Authority Reference",
                isPresented: $showingDeleteConfirmation,
                titleVisibility: .visible
            ) {
                Button("Delete", role: .destructive) {
                    if let authority = deleteTarget {
                        Task { await deleteAuthority(authority) }
                    }
                }
                Button("Cancel", role: .cancel) {
                    deleteTarget = nil
                }
            } message: {
                if let authority = deleteTarget {
                    Text("Remove this \(authority.displayName) reference from the recording?")
                }
            }
            .task {
                await loadAuthorities()
            }
        }
    }
    
    // MARK: - Data Loading
    
    private func loadAuthorities() async {
        isLoading = true
        errorMessage = nil
        
        guard let url = URL(string: "\(NetworkManager.baseURL)/recordings/\(recordingId)/authorities") else {
            errorMessage = "Invalid URL"
            isLoading = false
            return
        }
        
        do {
            let (data, response) = try await URLSession.shared.data(from: url)
            
            guard let httpResponse = response as? HTTPURLResponse else {
                errorMessage = "Invalid response"
                isLoading = false
                return
            }
            
            if httpResponse.statusCode == 200 {
                let decoded = try JSONDecoder().decode(AuthoritiesResponse.self, from: data)
                authorities = decoded.authorities
            } else if httpResponse.statusCode == 404 {
                errorMessage = "Recording not found"
            } else {
                errorMessage = "Failed to load authorities"
            }
        } catch {
            print("Error loading authorities: \(error)")
            errorMessage = "Failed to load: \(error.localizedDescription)"
        }
        
        isLoading = false
    }
    
    private func deleteAuthority(_ authority: AuthorityRecommendation) async {
        guard let url = URL(string: "\(NetworkManager.baseURL)/authorities/\(authority.id)") else {
            return
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"
        
        do {
            let (_, response) = try await URLSession.shared.data(for: request)
            
            if let httpResponse = response as? HTTPURLResponse,
               httpResponse.statusCode == 200 {
                // Remove from local list
                authorities.removeAll { $0.id == authority.id }
            }
        } catch {
            print("Error deleting authority: \(error)")
        }
        
        deleteTarget = nil
    }
}

// MARK: - Authority Row View

struct AuthorityRowView: View {
    let authority: AuthorityRecommendation
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                // Source badge
                Text(authority.displayName)
                    .font(.caption)
                    .fontWeight(.semibold)
                    .foregroundColor(.white)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(authority.sourceColor)
                    .cornerRadius(4)
                
                Spacer()
                
                if authority.sourceUrl != nil {
                    Image(systemName: "arrow.up.right.square")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
            
            // Artist/Album info
            if let artist = authority.artistName {
                Text(artist)
                    .font(.headline)
                    .foregroundColor(JazzTheme.charcoal)
            }
            
            if let album = authority.albumTitle {
                Text(album)
                    .font(.subheadline)
                    .foregroundColor(JazzTheme.smokeGray)
            }
            
            // Year
            if let year = authority.recordingYear {
                Text("(\(year))")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            // Recommendation text
            if let text = authority.recommendationText, !text.isEmpty {
                Text(text)
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .lineLimit(3)
                    .padding(.top, 4)
            }
        }
        .padding(.vertical, 4)
    }
}

// MARK: - Add Authority View

struct AddAuthorityView: View {
    let recordingId: String
    let onAdd: (AuthorityRecommendation) -> Void
    
    @State private var source: String = ""
    @State private var sourceUrl: String = ""
    @State private var recommendationText: String = ""
    @State private var artistName: String = ""
    @State private var albumTitle: String = ""
    @State private var recordingYear: String = ""
    @State private var isSubmitting = false
    @State private var errorMessage: String?
    
    @Environment(\.dismiss) private var dismiss
    
    private let commonSources = [
        "jazzstandards.com",
        "ted_gioia",
        "allmusic",
        "discogs",
        "wikipedia"
    ]
    
    var isValid: Bool {
        !source.trimmingCharacters(in: .whitespaces).isEmpty &&
        !sourceUrl.trimmingCharacters(in: .whitespaces).isEmpty
    }
    
    var body: some View {
        NavigationStack {
            Form {
                Section("Required") {
                    Picker("Source", selection: $source) {
                        Text("Select source...").tag("")
                        ForEach(commonSources, id: \.self) { src in
                            Text(displayName(for: src)).tag(src)
                        }
                        Text("Other").tag("other")
                    }
                    
                    if source == "other" {
                        TextField("Custom source name", text: $source)
                    }
                    
                    TextField("Source URL", text: $sourceUrl)
                        .keyboardType(.URL)
                        .autocapitalization(.none)
                        .autocorrectionDisabled()
                }
                
                Section("Optional Details") {
                    TextField("Artist Name", text: $artistName)
                    TextField("Album Title", text: $albumTitle)
                    TextField("Year", text: $recordingYear)
                        .keyboardType(.numberPad)
                }
                
                Section("Recommendation Text") {
                    TextEditor(text: $recommendationText)
                        .frame(minHeight: 80)
                }
                
                if let error = errorMessage {
                    Section {
                        Text(error)
                            .foregroundColor(.red)
                    }
                }
            }
            .navigationTitle("Add Reference")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        dismiss()
                    }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Add") {
                        Task { await submitAuthority() }
                    }
                    .disabled(!isValid || isSubmitting)
                }
            }
            .disabled(isSubmitting)
            .overlay {
                if isSubmitting {
                    ProgressView()
                        .scaleEffect(1.5)
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                        .background(Color.black.opacity(0.1))
                }
            }
        }
    }
    
    private func displayName(for source: String) -> String {
        switch source {
        case "jazzstandards.com": return "JazzStandards.com"
        case "ted_gioia": return "Ted Gioia"
        case "allmusic": return "AllMusic"
        case "discogs": return "Discogs"
        case "wikipedia": return "Wikipedia"
        default: return source
        }
    }
    
    private func submitAuthority() async {
        isSubmitting = true
        errorMessage = nil
        
        guard let url = URL(string: "\(NetworkManager.baseURL)/recordings/\(recordingId)/authorities") else {
            errorMessage = "Invalid URL"
            isSubmitting = false
            return
        }
        
        var requestBody: [String: Any] = [
            "source": source,
            "source_url": sourceUrl
        ]
        
        if !recommendationText.isEmpty {
            requestBody["recommendation_text"] = recommendationText
        }
        if !artistName.isEmpty {
            requestBody["artist_name"] = artistName
        }
        if !albumTitle.isEmpty {
            requestBody["album_title"] = albumTitle
        }
        if let year = Int(recordingYear) {
            requestBody["recording_year"] = year
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        do {
            request.httpBody = try JSONSerialization.data(withJSONObject: requestBody)
            
            let (data, response) = try await URLSession.shared.data(for: request)
            
            guard let httpResponse = response as? HTTPURLResponse else {
                errorMessage = "Invalid response"
                isSubmitting = false
                return
            }
            
            if httpResponse.statusCode == 201 {
                let authority = try JSONDecoder().decode(AuthorityRecommendation.self, from: data)
                onAdd(authority)
            } else if httpResponse.statusCode == 409 {
                errorMessage = "This reference already exists"
            } else {
                errorMessage = "Failed to add reference"
            }
        } catch {
            print("Error adding authority: \(error)")
            errorMessage = "Error: \(error.localizedDescription)"
        }
        
        isSubmitting = false
    }
}

// MARK: - Preview

#Preview {
    AuthorityRecommendationsView(
        recordingId: "preview-recording",
        albumTitle: "Kind of Blue"
    )
}

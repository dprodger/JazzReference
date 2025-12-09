//
//  AuthorityRecommendation.swift
//  JazzReference
//
//  Created by Dave Rodger on 11/28/25.
//  View and manage authority recommendations for a recording
//  Updated to show unmatched song recommendations for linking
//

import SwiftUI

// MARK: - Authority Recommendations View

struct AuthorityRecommendationsView: View {
    let recordingId: String
    let albumTitle: String
    let songId: String?  // Optional: when provided, also fetch unmatched song recommendations
    
    @State private var authorities: [AuthorityRecommendation] = []
    @State private var unmatchedAuthorities: [AuthorityRecommendation] = []
    @State private var isLoading = true
    @State private var errorMessage: String?
    @State private var showingAddSheet = false
    @State private var deleteTarget: AuthorityRecommendation?
    @State private var showingDeleteConfirmation = false
    @State private var linkTarget: AuthorityRecommendation?
    @State private var showingLinkConfirmation = false
    @State private var linkingInProgress = false
    
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
                            .font(JazzTheme.largeTitle())
                            .foregroundColor(.red)
                        Text(error)
                            .foregroundColor(.secondary)
                        Button("Retry") {
                            Task { await loadAuthorities() }
                        }
                        .buttonStyle(.bordered)
                    }
                    .padding()
                } else if authorities.isEmpty && unmatchedAuthorities.isEmpty {
                    VStack(spacing: 16) {
                        Image(systemName: "doc.badge.plus")
                            .font(.system(size: 48))
                            .foregroundColor(JazzTheme.smokeGray)
                        Text("No Authority References")
                            .font(JazzTheme.headline())
                            .foregroundColor(JazzTheme.charcoal)
                        Text("This recording has no authority recommendations linked to it.")
                            .font(JazzTheme.subheadline())
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal)
                    }
                    .padding()
                } else {
                    List {
                        // Section for authorities linked to this recording
                        if !authorities.isEmpty {
                            Section {
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
                            } header: {
                                Text("Linked to This Recording")
                            }
                        }
                        
                        // Section for unmatched song recommendations
                        if !unmatchedAuthorities.isEmpty {
                            Section {
                                ForEach(unmatchedAuthorities) { authority in
                                    UnmatchedAuthorityRowView(authority: authority)
                                        .swipeActions(edge: .leading, allowsFullSwipe: true) {
                                            Button {
                                                linkTarget = authority
                                                showingLinkConfirmation = true
                                            } label: {
                                                Label("Link", systemImage: "link")
                                            }
                                            .tint(JazzTheme.teal)
                                        }
                                        .onTapGesture {
                                            if let urlString = authority.sourceUrl,
                                               let url = URL(string: urlString) {
                                                openURL(url)
                                            }
                                        }
                                }
                            } header: {
                                HStack {
                                    Text("Unmatched Song Recommendations")
                                    Spacer()
                                    Text("\(unmatchedAuthorities.count)")
                                        .font(JazzTheme.caption())
                                        .foregroundColor(.secondary)
                                }
                            } footer: {
                                Text("Swipe right to link a recommendation to this recording")
                                    .font(JazzTheme.caption())
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
                    Text("Remove this \(authority.sourceDisplayName) reference from the recording?")
                }
            }
            .confirmationDialog(
                "Link to This Recording",
                isPresented: $showingLinkConfirmation,
                titleVisibility: .visible
            ) {
                Button("Link to \(albumTitle)") {
                    if let authority = linkTarget {
                        Task { await linkAuthority(authority) }
                    }
                }
                Button("Cancel", role: .cancel) {
                    linkTarget = nil
                }
            } message: {
                if let authority = linkTarget {
                    Text("Link \"\(authority.artistName ?? "Unknown") - \(authority.albumTitle ?? "Unknown")\" to this recording?")
                }
            }
            .overlay {
                if linkingInProgress {
                    ProgressView("Linking...")
                        .padding()
                        .background(Color(.systemBackground))
                        .cornerRadius(10)
                        .shadow(radius: 10)
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
        
        // Load recording authorities
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
                let decoded = try JSONDecoder().decode(RecordingAuthoritiesResponse.self, from: data)
                authorities = decoded.authorities
                
                // If we have a songId, also load unmatched song recommendations
                let effectiveSongId = songId ?? decoded.songId
                if let sid = effectiveSongId {
                    await loadUnmatchedSongAuthorities(songId: sid)
                }
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
    
    private func loadUnmatchedSongAuthorities(songId: String) async {
        guard let url = URL(string: "\(NetworkManager.baseURL)/songs/\(songId)/authorities") else {
            return
        }
        
        do {
            let (data, response) = try await URLSession.shared.data(from: url)
            
            guard let httpResponse = response as? HTTPURLResponse,
                  httpResponse.statusCode == 200 else {
                return
            }
            
            let decoded = try JSONDecoder().decode(SongAuthoritiesResponse.self, from: data)
            
            // Filter to only unmatched (recording_id is nil)
            unmatchedAuthorities = decoded.authorities.filter { $0.recordingId == nil }
        } catch {
            print("Error loading song authorities: \(error)")
        }
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
    
    private func linkAuthority(_ authority: AuthorityRecommendation) async {
        linkingInProgress = true
        
        guard let url = URL(string: "\(NetworkManager.baseURL)/authorities/\(authority.id)/link") else {
            linkingInProgress = false
            return
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "PATCH"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body: [String: Any] = ["recording_id": recordingId]
        
        do {
            request.httpBody = try JSONSerialization.data(withJSONObject: body)
            
            let (data, response) = try await URLSession.shared.data(for: request)
            
            if let httpResponse = response as? HTTPURLResponse,
               httpResponse.statusCode == 200 {
                // Decode the updated authority
                let updatedAuthority = try JSONDecoder().decode(AuthorityRecommendation.self, from: data)
                
                // Move from unmatched to matched
                unmatchedAuthorities.removeAll { $0.id == authority.id }
                authorities.append(updatedAuthority)
            }
        } catch {
            print("Error linking authority: \(error)")
        }
        
        linkTarget = nil
        linkingInProgress = false
    }
}

// MARK: - Response Structs

struct RecordingAuthoritiesResponse: Codable {
    let recordingId: String
    let songId: String?
    let authorities: [AuthorityRecommendation]
    let count: Int
    
    enum CodingKeys: String, CodingKey {
        case recordingId = "recording_id"
        case songId = "song_id"
        case authorities
        case count
    }
}

struct SongAuthoritiesResponse: Codable {
    let songId: String
    let songTitle: String?
    let authorities: [AuthorityRecommendation]
    let totalCount: Int
    let matchedCount: Int
    let unmatchedCount: Int
    
    enum CodingKeys: String, CodingKey {
        case songId = "song_id"
        case songTitle = "song_title"
        case authorities
        case totalCount = "total_count"
        case matchedCount = "matched_count"
        case unmatchedCount = "unmatched_count"
    }
}

// MARK: - Authority Row View

struct AuthorityRowView: View {
    let authority: AuthorityRecommendation
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                // Source badge
                Text(authority.sourceDisplayName)
                    .font(JazzTheme.caption())
                    .fontWeight(.semibold)
                    .foregroundColor(.white)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(authority.sourceColor)
                    .cornerRadius(4)
                
                Spacer()
                
                if authority.sourceUrl != nil {
                    Image(systemName: "arrow.up.right.square")
                        .font(JazzTheme.caption())
                        .foregroundColor(.secondary)
                }
            }
            
            // Artist/Album info
            if let artist = authority.artistName {
                Text(artist)
                    .font(JazzTheme.headline())
                    .foregroundColor(JazzTheme.charcoal)
            }
            
            if let album = authority.albumTitle {
                Text(album)
                    .font(JazzTheme.subheadline())
                    .foregroundColor(JazzTheme.smokeGray)
            }
            
            // Year
            if let year = authority.recordingYear {
                Text("(\(year))")
                    .font(JazzTheme.caption())
                    .foregroundColor(.secondary)
            }
            
            // Recommendation text
            if let text = authority.recommendationText, !text.isEmpty {
                Text(text)
                    .font(JazzTheme.caption())
                    .foregroundColor(.secondary)
                    .lineLimit(3)
                    .padding(.top, 4)
            }
        }
        .padding(.vertical, 4)
    }
}

// MARK: - Unmatched Authority Row View

struct UnmatchedAuthorityRowView: View {
    let authority: AuthorityRecommendation
    
    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    // Source badge
                    Text(authority.sourceDisplayName)
                        .font(JazzTheme.caption())
                        .fontWeight(.semibold)
                        .foregroundColor(.white)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(authority.sourceColor)
                        .cornerRadius(4)
                    
                    // Unmatched indicator
                    Text("Unlinked")
                        .font(JazzTheme.caption2())
                        .foregroundColor(JazzTheme.amber)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(JazzTheme.amber.opacity(0.15))
                        .cornerRadius(4)
                    
                    Spacer()
                    
                    if authority.sourceUrl != nil {
                        Image(systemName: "arrow.up.right.square")
                            .font(JazzTheme.caption())
                            .foregroundColor(.secondary)
                    }
                }
                
                // Artist/Album info
                if let artist = authority.artistName {
                    Text(artist)
                        .font(JazzTheme.headline())
                        .foregroundColor(JazzTheme.charcoal)
                }
                
                if let album = authority.albumTitle {
                    Text(album)
                        .font(JazzTheme.subheadline())
                        .foregroundColor(JazzTheme.smokeGray)
                }
                
                // Year
                if let year = authority.recordingYear {
                    Text("(\(year))")
                        .font(JazzTheme.caption())
                        .foregroundColor(.secondary)
                }
            }
            
            // Link hint icon
            Image(systemName: "link.badge.plus")
                .font(JazzTheme.title3())
                .foregroundColor(JazzTheme.teal.opacity(0.5))
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
        albumTitle: "Kind of Blue",
        songId: "preview-song"
    )
}

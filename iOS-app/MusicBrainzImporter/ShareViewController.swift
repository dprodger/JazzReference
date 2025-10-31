//
//  ShareViewController.swift
//  MusicBrainzImporter
//
//  Safari Share Extension for importing MusicBrainz artist data into Jazz Reference
//

import UIKit
import SwiftUI
import Social
import UniformTypeIdentifiers

// MARK: - Data Models (Must be in extension target)

struct ArtistData: Codable {
    let name: String
    let musicbrainzId: String
    let biography: String?
    let birthDate: String?
    let deathDate: String?
    let instruments: [String]?
    let wikipediaUrl: String?
    let sourceUrl: String?
}

// MARK: - Artist Match Result

enum ArtistMatchResult {
    case notFound                    // Artist doesn't exist at all
    case exactMatch(existingArtist: ExistingArtist)  // Same name and same MusicBrainz ID
    case nameMatchNoMbid(existingArtist: ExistingArtist)  // Same name but blank MusicBrainz ID
    case nameMatchDifferentMbid(existingArtist: ExistingArtist)  // Same name but different MusicBrainz ID
}

struct ExistingArtist: Codable {
    let id: String
    let name: String
    let biography: String?
    let birthDate: String?
    let deathDate: String?
    var musicbrainzId: String?
    
    var shortBio: String {
        guard let bio = biography, !bio.isEmpty else {
            return "No biography available"
        }
        // Return first 200 characters
        let prefix = String(bio.prefix(200))
        return bio.count > 200 ? prefix + "..." : prefix
    }
    
    enum CodingKeys: String, CodingKey {
        case id, name, biography
        case birthDate = "birth_date"
        case deathDate = "death_date"
        case musicbrainzId = "musicbrainz_id"
    }
}

// MARK: - Database Service

class ArtistDatabaseService {
    static let shared = ArtistDatabaseService()
    
    // TODO: Update with your actual backend URL
    // For development, you might use: http://localhost:5001
    // For production, use your deployed backend URL
    private  let baseURL = "https://jazzreference.onrender.com/api"

    private init() {}
    
    /// Check if an artist exists in the database by name and/or MusicBrainz ID
    func checkArtistExists(name: String, musicbrainzId: String) async throws -> ArtistMatchResult {
        // Search by name first
        guard let encodedName = name.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) else {
            throw URLError(.badURL)
        }
        
        let urlString = "\(baseURL)/performers/search?name=\(encodedName)"
        guard let url = URL(string: urlString) else {
            throw URLError(.badURL)
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.timeoutInterval = 10.0
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw URLError(.badServerResponse)
        }
        
        if httpResponse.statusCode == 404 {
            // No artist found with this name
            return .notFound
        }
        
        guard httpResponse.statusCode == 200 else {
            throw URLError(.badServerResponse)
        }
        
        // Parse the response
        let decoder = JSONDecoder()
        let results = try decoder.decode([ExistingArtist].self, from: data)
        
        // Check for exact name match (case-insensitive)
        guard let matchingArtist = results.first(where: { $0.name.lowercased() == name.lowercased() }) else {
            return .notFound
        }
        
        // Now check the MusicBrainz ID
        if let existingMbid = matchingArtist.musicbrainzId {
            if existingMbid == musicbrainzId {
                // Exact match: same name and same MusicBrainz ID
                return .exactMatch(existingArtist: matchingArtist)
            } else {
                // Different MusicBrainz ID
                return .nameMatchDifferentMbid(existingArtist: matchingArtist)
            }
        } else {
            // Name matches but no MusicBrainz ID in database
            return .nameMatchNoMbid(existingArtist: matchingArtist)
        }
    }
}

// MARK: - Shared Data Manager

class SharedArtistData {
    static func saveSharedData(_ artistData: ArtistData, appGroup: String) {
        guard let sharedDefaults = UserDefaults(suiteName: appGroup) else {
            print("❌ Failed to get shared UserDefaults")
            return
        }
        
        let encoder = JSONEncoder()
        if let encoded = try? encoder.encode(artistData) {
            sharedDefaults.set(encoded, forKey: "pendingArtistImport")
            sharedDefaults.synchronize()
            print("✅ Artist data saved to shared container")
        } else {
            print("❌ Failed to encode artist data")
        }
    }
}

// MARK: - Share View Controller

class ShareViewController: UIViewController {
    
    // MARK: - Properties
    private var artistData: ArtistData?
    private var existingArtist: ExistingArtist?
    private let appGroupIdentifier = "group.me.rodger.david.JazzReference"
    
    // MARK: - Lifecycle
    override func viewDidLoad() {
        super.viewDidLoad()
        
        // Set up the view appearance
        view.backgroundColor = .systemBackground
        
        print("📱 Share extension launched")
        
        // Start extracting data
        extractArtistData()
    }
    
    // MARK: - Data Extraction
    private func extractArtistData() {
        print("🔍 Starting data extraction...")
        
        // Get the extension context
        guard let extensionItem = extensionContext?.inputItems.first as? NSExtensionItem else {
            print("❌ No extension item found")
            showError("No data available")
            return
        }
        
        guard let itemProvider = extensionItem.attachments?.first else {
            print("❌ No item provider found")
            showError("No data available")
            return
        }
        
        print("✓ Extension item and provider found")
        
        // Check for property list (JavaScript preprocessing results)
        let propertyListType = "com.apple.property-list"
        
        if itemProvider.hasItemConformingToTypeIdentifier(propertyListType) {
            print("✓ Property list type found, loading item...")
            
            itemProvider.loadItem(forTypeIdentifier: propertyListType, options: nil) { [weak self] (item, error) in
                guard let self = self else { return }
                
                if let error = error {
                    print("❌ Error loading item: \(error.localizedDescription)")
                    DispatchQueue.main.async {
                        self.showError("Failed to load page data")
                    }
                    return
                }
                
                print("✓ Item loaded successfully")
                
                // The item should be a Dictionary containing the JavaScript preprocessing results
                if let dictionary = item as? [String: Any] {
                    print("✓ Got dictionary from item")
                    
                    // Check for the JavaScript preprocessing results key
                    if let results = dictionary[NSExtensionJavaScriptPreprocessingResultsKey] as? [String: Any] {
                        print("✓ Got JavaScript preprocessing results")
                        
                        DispatchQueue.main.async {
                            self.processExtractedData(results)
                        }
                    } else {
                        print("❌ No JavaScript preprocessing results found")
                        DispatchQueue.main.async {
                            self.showError("Could not extract data from page")
                        }
                    }
                } else if let data = item as? Data {
                    print("✓ Got Data, attempting to deserialize...")
                    do {
                        if let dict = try PropertyListSerialization.propertyList(from: data, options: [], format: nil) as? [String: Any] {
                            print("✓ Successfully deserialized property list")
                            if let results = dict[NSExtensionJavaScriptPreprocessingResultsKey] as? [String: Any] {
                                print("✓ Got JavaScript preprocessing results from deserialized data")
                                DispatchQueue.main.async {
                                    self.processExtractedData(results)
                                }
                                return
                            }
                        }
                    } catch {
                        print("❌ Failed to deserialize property list: \(error)")
                    }
                    DispatchQueue.main.async {
                        self.showError("Invalid data format")
                    }
                } else {
                    print("❌ Item is not Dictionary or Data: \(type(of: item))")
                    DispatchQueue.main.async {
                        self.showError("Invalid data format")
                    }
                }
            }
        } else {
            print("❌ No property list type found")
            showError("This extension only works with web pages")
        }
    }
    
    // MARK: - Data Processing
    private func processExtractedData(_ data: [String: Any]) {
        print("📄 Processing extracted data...")
        
        // Check for error from JavaScript
        if let error = data["error"] as? String {
            print("❌ JavaScript error: \(error)")
            showError(error)
            return
        }
        
        // Extract artist information from the JavaScript results
        // Handle optional fields that might not be present
        let name = data["name"] as? String ?? ""
        let musicbrainzId = data["musicbrainzId"] as? String ?? ""
        let biography = data["biography"] as? String
        let birthDate = data["birthDate"] as? String
        let deathDate = data["deathDate"] as? String
        let instruments = data["instruments"] as? [String]
        let wikipediaUrl = data["wikipediaUrl"] as? String
        let sourceUrl = data["url"] as? String
        
        let artistData = ArtistData(
            name: name,
            musicbrainzId: musicbrainzId,
            biography: biography,
            birthDate: birthDate,
            deathDate: deathDate,
            instruments: instruments,
            wikipediaUrl: wikipediaUrl,
            sourceUrl: sourceUrl
        )
        
        print("🎵 Extracted artist: \(artistData.name)")
        print("🆔 MusicBrainz ID: \(artistData.musicbrainzId)")
        
        // Validate that we got at least a name and ID
        guard !artistData.name.isEmpty, !artistData.musicbrainzId.isEmpty else {
            print("❌ Missing required fields - name: '\(artistData.name)', id: '\(artistData.musicbrainzId)'")
            showError("Could not extract artist information from this page")
            return
        }
        
        self.artistData = artistData
        print("✅ Data validation passed")
        
        // Check if artist already exists in database
        checkArtistExistence(artistData)
    }
    
    // MARK: - Database Checking
    private func checkArtistExistence(_ artistData: ArtistData) {
        print("🔍 Checking if artist exists in database...")
        
        // Show loading indicator
        showLoadingView()
        
        Task {
            do {
                let result = try await ArtistDatabaseService.shared.checkArtistExists(
                    name: artistData.name,
                    musicbrainzId: artistData.musicbrainzId
                )
                
                await MainActor.run {
                    print("✅ Database check complete")
                    self.handleArtistMatchResult(result, artistData: artistData)
                }
            } catch {
                await MainActor.run {
                    print("⚠️ Database check failed: \(error.localizedDescription)")
                    print("   Proceeding with import anyway...")
                    // If database check fails, just proceed with normal import
                    self.showConfirmationView(with: artistData)
                }
            }
        }
    }
    
    private func handleArtistMatchResult(_ result: ArtistMatchResult, artistData: ArtistData) {
        switch result {
        case .notFound:
            print("ℹ️ Artist not found - showing normal import")
            showConfirmationView(with: artistData)
            
        case .exactMatch(let existingArtist):
            print("ℹ️ Exact match found - artist already exists")
            self.existingArtist = existingArtist
            showExactMatchView(artistData: artistData, existingArtist: existingArtist)
            
        case .nameMatchNoMbid(let existingArtist):
            print("ℹ️ Name match with blank MusicBrainz ID")
            self.existingArtist = existingArtist
            showNameMatchNoMbidView(artistData: artistData, existingArtist: existingArtist)
            
        case .nameMatchDifferentMbid(let existingArtist):
            print("ℹ️ Name match with different MusicBrainz ID")
            self.existingArtist = existingArtist
            showNameMatchDifferentMbidView(artistData: artistData, existingArtist: existingArtist)
        }
    }
    
    // MARK: - UI Views
    
    private func showLoadingView() {
        let loadingView = LoadingView()
        replaceCurrentView(with: loadingView)
    }
    
    private func showConfirmationView(with artistData: ArtistData) {
        print("🎨 Showing confirmation view")
        
        let confirmationView = ArtistImportConfirmationView(
            artistData: artistData,
            onImport: { [weak self] in
                self?.importArtist()
            },
            onCancel: { [weak self] in
                self?.cancelImport()
            }
        )
        
        replaceCurrentView(with: confirmationView)
    }
    
    private func showExactMatchView(artistData: ArtistData, existingArtist: ExistingArtist) {
        print("🎨 Showing exact match view")
        
        let view = ArtistExactMatchView(
            artistData: artistData,
            existingArtist: existingArtist,
            onOpenInApp: { [weak self] in
                self?.openArtistInApp(artistId: existingArtist.id)
            },
            onCancel: { [weak self] in
                self?.cancelImport()
            }
        )
        
        replaceCurrentView(with: view)
    }
    
    private func showNameMatchNoMbidView(artistData: ArtistData, existingArtist: ExistingArtist) {
        print("🎨 Showing name match (no MBID) view")
        
        let view = ArtistNameMatchNoMbidView(
            artistData: artistData,
            existingArtist: existingArtist,
            onAssociate: { [weak self] in
                // TODO: Implement association logic
                self?.showNotImplementedAlert("Associate MusicBrainz ID")
            },
            onCancel: { [weak self] in
                self?.cancelImport()
            }
        )
        
        replaceCurrentView(with: view)
    }
    
    private func showNameMatchDifferentMbidView(artistData: ArtistData, existingArtist: ExistingArtist) {
        print("🎨 Showing name match (different MBID) view")
        
        let view = ArtistNameMatchDifferentMbidView(
            artistData: artistData,
            existingArtist: existingArtist,
            onOverwrite: { [weak self] in
                // TODO: Implement overwrite logic
                self?.showNotImplementedAlert("Overwrite MusicBrainz ID")
            },
            onCancel: { [weak self] in
                self?.cancelImport()
            }
        )
        
        replaceCurrentView(with: view)
    }
    
    private func showError(_ message: String) {
        print("⚠️ Showing error: \(message)")
        
        let errorView = ErrorView(
            message: message,
            onDismiss: { [weak self] in
                self?.cancelImport()
            }
        )
        
        replaceCurrentView(with: errorView)
    }
    
    private func replaceCurrentView<Content: View>(with swiftUIView: Content) {
        // Remove all existing views
        view.subviews.forEach { $0.removeFromSuperview() }
        children.forEach { $0.removeFromParent() }
        
        // Create hosting controller
        let hostingController = UIHostingController(rootView: swiftUIView)
        
        // Add as child view controller
        addChild(hostingController)
        view.addSubview(hostingController.view)
        hostingController.view.frame = view.bounds
        hostingController.view.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        hostingController.didMove(toParent: self)
    }
    
    // MARK: - Actions
    private func importArtist() {
        guard let artistData = artistData else {
            print("❌ No artist data to import")
            showError("No artist data available")
            return
        }
        
        print("💾 Saving artist data: \(artistData.name)")
        
        // Save to shared container
        SharedArtistData.saveSharedData(artistData, appGroup: appGroupIdentifier)
        
        // Show success and close
        showSuccessAndClose()
    }
    
    private func openArtistInApp(artistId: String) {
        print("🔗 Opening artist in app: \(artistId)")
        
        // TODO: Implement deep link to open the main app at the artist detail page
        // For now, just show a placeholder
        showNotImplementedAlert("Open in App")
    }
    
    private func showNotImplementedAlert(_ feature: String) {
        let alertView = NotImplementedView(
            feature: feature,
            onDismiss: { [weak self] in
                self?.cancelImport()
            }
        )
        replaceCurrentView(with: alertView)
    }
    
    private func cancelImport() {
        print("❌ User cancelled import")
        extensionContext?.completeRequest(returningItems: nil, completionHandler: nil)
    }
    
    private func showSuccessAndClose() {
        print("✅ Showing success message")
        
        // Show brief success message
        let successView = SuccessView()
        replaceCurrentView(with: successView)
        
        // Close after a brief delay
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) { [weak self] in
            print("👋 Closing extension")
            self?.extensionContext?.completeRequest(returningItems: nil, completionHandler: nil)
        }
    }
}

// MARK: - SwiftUI Views

struct LoadingView: View {
    var body: some View {
        VStack(spacing: 20) {
            ProgressView()
                .scaleEffect(1.5)
            
            Text("Checking database...")
                .font(.subheadline)
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(.systemBackground))
    }
}

struct ArtistImportConfirmationView: View {
    let artistData: ArtistData
    let onImport: () -> Void
    let onCancel: () -> Void
    
    var body: some View {
        VStack(spacing: 20) {
            // Header
            VStack(spacing: 8) {
                Image(systemName: "person.badge.plus")
                    .font(.system(size: 50))
                    .foregroundColor(.blue)
                
                Text("Import Artist")
                    .font(.title2)
                    .bold()
            }
            .padding(.top, 40)
            
            // Artist information
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    InfoRow(label: "Name", value: artistData.name)
                    
                    InfoRow(label: "MusicBrainz ID", value: artistData.musicbrainzId)
                    
                    if let birthDate = artistData.birthDate {
                        InfoRow(label: "Born", value: birthDate)
                    }
                    
                    if let deathDate = artistData.deathDate {
                        InfoRow(label: "Died", value: deathDate)
                    }
                    
                    if let instruments = artistData.instruments, !instruments.isEmpty {
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Instruments")
                                .font(.caption)
                                .foregroundColor(.secondary)
                            Text(instruments.joined(separator: ", "))
                                .font(.body)
                        }
                    }
                    
                    if let bio = artistData.biography, !bio.isEmpty {
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Biography Preview")
                                .font(.caption)
                                .foregroundColor(.secondary)
                            Text(bio.prefix(150) + (bio.count > 150 ? "..." : ""))
                                .font(.caption)
                                .foregroundColor(.secondary)
                                .lineLimit(3)
                        }
                    }
                }
                .padding()
            }
            .background(Color(.systemGray6))
            .cornerRadius(12)
            .padding(.horizontal)
            
            Spacer()
            
            // Action buttons
            VStack(spacing: 12) {
                Button(action: onImport) {
                    Text("Import to Jazz Reference")
                        .font(.headline)
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color.blue)
                        .cornerRadius(12)
                }
                
                Button(action: onCancel) {
                    Text("Cancel")
                        .font(.headline)
                        .foregroundColor(.blue)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color(.systemGray6))
                        .cornerRadius(12)
                }
            }
            .padding(.horizontal)
            .padding(.bottom, 20)
        }
        .background(Color(.systemBackground))
    }
}

struct ArtistExactMatchView: View {
    let artistData: ArtistData
    let existingArtist: ExistingArtist
    let onOpenInApp: () -> Void
    let onCancel: () -> Void
    
    var body: some View {
        VStack(spacing: 20) {
            // Header with warning icon
            VStack(spacing: 12) {
                Image(systemName: "exclamationmark.triangle.fill")
                    .font(.system(size: 50))
                    .foregroundColor(.orange)
                
                Text("Artist Already Exists")
                    .font(.title2)
                    .bold()
                
                Text("\(artistData.name) is already in the database")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
            }
            .padding(.top, 40)
            .padding(.horizontal)
            
            // Comparison
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    Text("Database Record")
                        .font(.headline)
                        .foregroundColor(.secondary)
                    
                    InfoRow(label: "Name", value: existingArtist.name)
                    InfoRow(label: "MusicBrainz ID", value: existingArtist.musicbrainzId ?? "None")
                    
                    if let bio = existingArtist.biography, !bio.isEmpty {
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Biography")
                                .font(.caption)
                                .foregroundColor(.secondary)
                            Text(existingArtist.shortBio)
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                }
                .padding()
            }
            .background(Color(.systemGray6))
            .cornerRadius(12)
            .padding(.horizontal)
            
            Spacer()
            
            // Action buttons
            VStack(spacing: 12) {
                Button(action: onOpenInApp) {
                    HStack {
                        Image(systemName: "arrow.up.forward.app")
                        Text("View in Jazz Reference")
                    }
                    .font(.headline)
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(Color.blue)
                    .cornerRadius(12)
                }
                
                Button(action: onCancel) {
                    Text("Close")
                        .font(.headline)
                        .foregroundColor(.blue)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color(.systemGray6))
                        .cornerRadius(12)
                }
            }
            .padding(.horizontal)
            .padding(.bottom, 20)
        }
        .background(Color(.systemBackground))
    }
}

struct ArtistNameMatchNoMbidView: View {
    let artistData: ArtistData
    let existingArtist: ExistingArtist
    let onAssociate: () -> Void
    let onCancel: () -> Void
    
    var body: some View {
        VStack(spacing: 20) {
            // Header
            VStack(spacing: 12) {
                Image(systemName: "link.badge.plus")
                    .font(.system(size: 50))
                    .foregroundColor(.blue)
                
                Text("Associate MusicBrainz ID?")
                    .font(.title2)
                    .bold()
                
                Text("An artist named \(artistData.name) exists without a MusicBrainz ID")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
            }
            .padding(.top, 40)
            .padding(.horizontal)
            
            // Comparison
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    // Existing artist
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Current Database Record")
                            .font(.headline)
                            .foregroundColor(.secondary)
                        
                        InfoRow(label: "Name", value: existingArtist.name)
                        InfoRow(label: "MusicBrainz ID", value: "None (blank)")
                            .foregroundColor(.orange)
                    }
                    .padding()
                    .background(Color(.systemGray6))
                    .cornerRadius(8)
                    
                    // Arrow
                    HStack {
                        Spacer()
                        Image(systemName: "arrow.down")
                            .foregroundColor(.blue)
                            .font(.title3)
                        Spacer()
                    }
                    
                    // New data
                    VStack(alignment: .leading, spacing: 12) {
                        Text("From MusicBrainz")
                            .font(.headline)
                            .foregroundColor(.secondary)
                        
                        InfoRow(label: "Name", value: artistData.name)
                        InfoRow(label: "MusicBrainz ID", value: artistData.musicbrainzId)
                            .foregroundColor(.green)
                    }
                    .padding()
                    .background(Color(.systemGray6))
                    .cornerRadius(8)
                }
                .padding()
            }
            
            Spacer()
            
            // Action buttons
            VStack(spacing: 12) {
                Button(action: onAssociate) {
                    Text("Associate ID with Existing Artist")
                        .font(.headline)
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color.blue)
                        .cornerRadius(12)
                }
                
                Button(action: onCancel) {
                    Text("Cancel")
                        .font(.headline)
                        .foregroundColor(.blue)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color(.systemGray6))
                        .cornerRadius(12)
                }
            }
            .padding(.horizontal)
            .padding(.bottom, 20)
        }
        .background(Color(.systemBackground))
    }
}

struct ArtistNameMatchDifferentMbidView: View {
    let artistData: ArtistData
    let existingArtist: ExistingArtist
    let onOverwrite: () -> Void
    let onCancel: () -> Void
    
    var body: some View {
        VStack(spacing: 20) {
            // Header with warning
            VStack(spacing: 12) {
                Image(systemName: "exclamationmark.triangle.fill")
                    .font(.system(size: 50))
                    .foregroundColor(.red)
                
                Text("Different Artist Found")
                    .font(.title2)
                    .bold()
                
                Text("An artist named \(artistData.name) exists with a different MusicBrainz ID")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
            }
            .padding(.top, 40)
            .padding(.horizontal)
            
            // Comparison
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    // Existing artist
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Current Database Record")
                            .font(.headline)
                            .foregroundColor(.secondary)
                        
                        InfoRow(label: "Name", value: existingArtist.name)
                        InfoRow(label: "MusicBrainz ID", value: existingArtist.musicbrainzId ?? "None")
                            .foregroundColor(.orange)
                        
                        if let bio = existingArtist.biography, !bio.isEmpty {
                            VStack(alignment: .leading, spacing: 4) {
                                Text("Biography")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                                Text(existingArtist.shortBio)
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                        }
                    }
                    .padding()
                    .background(Color(.systemGray6))
                    .cornerRadius(8)
                    
                    Divider()
                    
                    // New data
                    VStack(alignment: .leading, spacing: 12) {
                        Text("From MusicBrainz (New)")
                            .font(.headline)
                            .foregroundColor(.secondary)
                        
                        InfoRow(label: "Name", value: artistData.name)
                        InfoRow(label: "MusicBrainz ID", value: artistData.musicbrainzId)
                            .foregroundColor(.red)
                        
                        if let bio = artistData.biography, !bio.isEmpty {
                            VStack(alignment: .leading, spacing: 4) {
                                Text("Biography")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                                Text(String(bio.prefix(150)) + (bio.count > 150 ? "..." : ""))
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                        }
                    }
                    .padding()
                    .background(Color(.systemGray6))
                    .cornerRadius(8)
                    
                    Text("⚠️ These appear to be different artists with the same name")
                        .font(.caption)
                        .foregroundColor(.orange)
                        .padding()
                        .frame(maxWidth: .infinity)
                        .background(Color.orange.opacity(0.1))
                        .cornerRadius(8)
                }
                .padding()
            }
            
            Spacer()
            
            // Action buttons
            VStack(spacing: 12) {
                Button(action: onOverwrite) {
                    VStack(spacing: 4) {
                        Text("Overwrite with New Information")
                            .font(.headline)
                        Text("(This will replace the existing record)")
                            .font(.caption)
                    }
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(Color.red)
                    .cornerRadius(12)
                }
                
                Button(action: onCancel) {
                    Text("Cancel - Keep Existing")
                        .font(.headline)
                        .foregroundColor(.blue)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color(.systemGray6))
                        .cornerRadius(12)
                }
            }
            .padding(.horizontal)
            .padding(.bottom, 20)
        }
        .background(Color(.systemBackground))
    }
}

struct ErrorView: View {
    let message: String
    let onDismiss: () -> Void
    
    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "xmark.circle.fill")
                .font(.system(size: 60))
                .foregroundColor(.red)
            
            Text("Error")
                .font(.title2)
                .bold()
            
            Text(message)
                .font(.body)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal)
            
            Spacer()
            
            Button(action: onDismiss) {
                Text("Close")
                    .font(.headline)
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(Color.red)
                    .cornerRadius(12)
            }
            .padding(.horizontal)
            .padding(.bottom, 20)
        }
        .padding(.top, 60)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(.systemBackground))
    }
}

struct SuccessView: View {
    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 80))
                .foregroundColor(.green)
            
            Text("Artist Saved!")
                .font(.title2)
                .bold()
            
            Text("You can now close this window")
                .font(.subheadline)
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(.systemBackground))
    }
}

struct NotImplementedView: View {
    let feature: String
    let onDismiss: () -> Void
    
    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "wrench.and.screwdriver")
                .font(.system(size: 60))
                .foregroundColor(.orange)
            
            Text("Coming Soon")
                .font(.title2)
                .bold()
            
            Text("\(feature) will be implemented in a future update")
                .font(.body)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal)
            
            Spacer()
            
            Button(action: onDismiss) {
                Text("Close")
                    .font(.headline)
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(Color.blue)
                    .cornerRadius(12)
            }
            .padding(.horizontal)
            .padding(.bottom, 20)
        }
        .padding(.top, 60)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(.systemBackground))
    }
}

// MARK: - Helper Views

struct InfoRow: View {
    let label: String
    let value: String
    
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label)
                .font(.caption)
                .foregroundColor(.secondary)
            Text(value)
                .font(.body)
        }
    }
}

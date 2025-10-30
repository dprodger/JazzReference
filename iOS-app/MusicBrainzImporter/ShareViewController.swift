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

// MARK: - Shared Data Manager (Must be in extension target)

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
        print("🔄 Processing extracted data...")
        
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
        
        // Show the confirmation view
        showConfirmationView(with: artistData)
    }
    
    // MARK: - UI
    private func showConfirmationView(with artistData: ArtistData) {
        print("🎨 Showing confirmation view")
        
        // Create SwiftUI view
        let confirmationView = ArtistImportConfirmationView(
            artistData: artistData,
            onImport: { [weak self] in
                self?.importArtist()
            },
            onCancel: { [weak self] in
                self?.cancelImport()
            }
        )
        
        // Wrap in hosting controller
        let hostingController = UIHostingController(rootView: confirmationView)
        
        // Add as child view controller
        addChild(hostingController)
        view.addSubview(hostingController.view)
        hostingController.view.frame = view.bounds
        hostingController.view.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        hostingController.didMove(toParent: self)
    }
    
    private func showError(_ message: String) {
        print("⚠️ Showing error: \(message)")
        
        let errorView = ErrorView(
            message: message,
            onDismiss: { [weak self] in
                self?.cancelImport()
            }
        )
        
        let hostingController = UIHostingController(rootView: errorView)
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
    
    private func cancelImport() {
        print("❌ User cancelled import")
        extensionContext?.completeRequest(returningItems: nil, completionHandler: nil)
    }
    
    private func showSuccessAndClose() {
        print("✅ Showing success message")
        
        // Show brief success message
        let successView = SuccessView()
        let hostingController = UIHostingController(rootView: successView)
        
        // Replace current view
        view.subviews.forEach { $0.removeFromSuperview() }
        children.forEach { $0.removeFromParent() }
        
        addChild(hostingController)
        view.addSubview(hostingController.view)
        hostingController.view.frame = view.bounds
        hostingController.view.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        hostingController.didMove(toParent: self)
        
        // Close after a brief delay
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) { [weak self] in
            print("👋 Closing extension")
            self?.extensionContext?.completeRequest(returningItems: nil, completionHandler: nil)
        }
    }
}

// MARK: - SwiftUI Views

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
            .padding(.bottom, 30)
        }
        .background(Color(.systemBackground))
    }
}

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

struct ErrorView: View {
    let message: String
    let onDismiss: () -> Void
    
    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 50))
                .foregroundColor(.orange)
            
            Text("Error")
                .font(.title2)
                .bold()
            
            Text(message)
                .font(.body)
                .multilineTextAlignment(.center)
                .foregroundColor(.secondary)
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
            .padding(.bottom, 30)
        }
        .padding(.top, 40)
        .background(Color(.systemBackground))
    }
}

struct SuccessView: View {
    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 70))
                .foregroundColor(.green)
            
            Text("Artist data imported!")
                .font(.title2)
                .bold()
            
            Text("Open Jazz Reference to complete the artist creation")
                .font(.body)
                .multilineTextAlignment(.center)
                .foregroundColor(.secondary)
                .padding(.horizontal)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(.systemBackground))
    }
}


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

// MARK: - Share View Controller

class ShareViewController: UIViewController {
    
    // MARK: - Properties
    private var artistData: ArtistData?
    private var existingArtist: ExistingArtist?
    private var songData: SongData?
    private var existingSong: ExistingSong?
    private var isSongImport: Bool = false
    private let appGroupIdentifier = "group.me.rodger.david.JazzReference"
    
    // MARK: - Lifecycle
    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .systemBackground
        
        // First, detect if this is an artist or song page
        detectPageType()
    }

    // MARK: - Data Extraction
    
    private func detectPageType() {
        print("🔍 Detecting page type...")
        
        guard let extensionItem = extensionContext?.inputItems.first as? NSExtensionItem,
              let itemProvider = extensionItem.attachments?.first else {
            print("❌ No extension item found")
            showError("No data available")
            return
        }
        
        // Check if we have a URL to determine the type
        if itemProvider.hasItemConformingToTypeIdentifier(UTType.url.identifier) {
            itemProvider.loadItem(forTypeIdentifier: UTType.url.identifier, options: nil) { [weak self] (item, error) in
                if let url = item as? URL {
                    let urlString = url.absoluteString
                    if urlString.contains("musicbrainz.org/work/") {
                        self?.isSongImport = true
                        print("📍 Detected: Song/Work page")
                    } else if urlString.contains("musicbrainz.org/artist/") {
                        self?.isSongImport = false
                        print("📍 Detected: Artist page")
                    }
                }
                
                // Now proceed with extraction
                DispatchQueue.main.async {
                    if self?.isSongImport == true {
                        self?.extractSongData()
                    } else {
                        self?.extractArtistData()
                    }
                }
            }
        } else {
            // If we can't get URL, default to artist
            extractArtistData()
        }
    }
    
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
            showError("This extension only works with web pages(!)")
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
        
        // Extract ONLY minimal artist information from the JavaScript results
        let name = data["name"] as? String ?? ""
        let musicbrainzId = data["musicbrainzId"] as? String ?? ""
        let wikipediaUrl = data["wikipediaUrl"] as? String
        let sourceUrl = data["url"] as? String
        
        let artistData = ArtistData(
            name: name,
            musicbrainzId: musicbrainzId,
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
    
    // MARK: - Song Extraction and Processing
    
    private func extractSongData() {
        NSLog("🔍 Starting song data extraction...")
        
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
        
        NSLog("✓ Extension item and provider found")
        
        let propertyListType = "com.apple.property-list"
        
        showError("extension item adn provider found")
        if itemProvider.hasItemConformingToTypeIdentifier(propertyListType) {
            NSLog("✓ Property list type found, loading item...")
            
            itemProvider.loadItem(forTypeIdentifier: propertyListType, options: nil) { [weak self] (item, error) in
                guard let self = self else { return }
                
                if let error = error {
                    NSLog("❌ Error loading item: \(error.localizedDescription)")
                    DispatchQueue.main.async {
                        self.showError("Failed to load page data")
                    }
                    return
                }
                
                NSLog("✓ Item loaded successfully")
                
                if let dictionary = item as? [String: Any] {
                    NSLog("✓ Got dictionary from item")
                    
                    if let results = dictionary[NSExtensionJavaScriptPreprocessingResultsKey] as? [String: Any] {
                        NSLog("✓ Got JavaScript preprocessing results")
                        
                        DispatchQueue.main.async {
                            self.processSongData(results)
                        }
                    } else {
                        NSLog("❌ No JavaScript preprocessing results found")
                        DispatchQueue.main.async {
                            self.showError("Could not extract data from page")
                        }
                    }
                } else if let data = item as? Data {
                    NSLog("✓ Got Data, attempting to deserialize...")
                    do {
                        if let dict = try PropertyListSerialization.propertyList(from: data, options: [], format: nil) as? [String: Any] {
                            NSLog("✓ Successfully deserialized property list")
                            
                            if let results = dict[NSExtensionJavaScriptPreprocessingResultsKey] as? [String: Any] {
                                NSLog("✓ Got JavaScript preprocessing results from deserialized data")
                                
                                DispatchQueue.main.async {
                                    self.processSongData(results)
                                }
                            } else {
                                NSLog("❌ No JavaScript preprocessing results in deserialized data")
                                DispatchQueue.main.async {
                                    self.showError("Could not extract song data from page")
                                }
                            }
                        }
                    } catch {
                        NSLog("❌ Error deserializing property list: \(error)")
                        DispatchQueue.main.async {
                            self.showError("Failed to process page data")
                        }
                    }
                } else {
                    NSLog("❌ Item is not a dictionary or Data")
                    DispatchQueue.main.async {
                        self.showError("Unexpected data format")
                    }
                }
            }
        } else {
            self.showError("Property list type not available")
            NSLog("❌ Property list type not available")
            showError("Cannot extract data from this page")
        }
    }
    
    private func processSongData(_ data: [String: Any]) {
        print("📋 Processing song data...")
        print("Data keys: \(data.keys)")
        
        // Check if there's an error from JavaScript
        if let error = data["error"] as? String {
            print("❌ JavaScript error: \(error)")
            showError(error)
            return
        }
        
        // Extract required fields
        guard let title = data["title"] as? String,
              !title.isEmpty else {
            print("❌ Missing or empty title")
            showError("Could not extract song title from page")
            return
        }
        
        guard let musicbrainzId = data["musicbrainzId"] as? String,
              !musicbrainzId.isEmpty else {
            print("❌ Missing or empty MusicBrainz ID")
            showError("Could not extract MusicBrainz ID from page")
            return
        }
        
        print("✓ Got title: \(title)")
        print("✓ Got MusicBrainz ID: \(musicbrainzId)")
        
        // Extract optional fields
        let composers = data["composers"] as? [String]
        let workType = data["workType"] as? String
        let key = data["key"] as? String
        let annotation = data["annotation"] as? String
        let wikipediaUrl = data["wikipediaUrl"] as? String
        let sourceUrl = data["url"] as? String
        
        // Create SongData
        let songData = SongData(
            title: title,
            musicbrainzId: musicbrainzId,
            composers: composers,
            workType: workType,
            key: key,
            annotation: annotation,
            wikipediaUrl: wikipediaUrl,
            sourceUrl: sourceUrl
        )
        
        self.songData = songData
        
        print("✓ SongData created successfully")
        print("  Title: \(title)")
        if let composers = composers {
            print("  Composers: \(composers.joined(separator: ", "))")
        }
        
        // Check if song already exists in database
        showLoadingView()
        checkSongMatch(songData: songData)
    }
    
    private func checkSongMatch(songData: SongData) {
        Task {
            do {
                print("🔍 Checking if song exists in database...")
                let result = try await SongDatabaseService.shared.checkSongExists(
                    title: songData.title,
                    musicbrainzId: songData.musicbrainzId
                )
                
                DispatchQueue.main.async {
                    self.processSongMatch(result: result, songData: songData)
                }
            } catch {
                print("❌ Error checking song: \(error)")
                DispatchQueue.main.async {
                    // If database check fails, just proceed with import
                    print("⚠️ Database check failed, proceeding with import anyway...")
                    self.showSongConfirmationView(with: songData)
                }
            }
        }
    }
    
    private func processSongMatch(result: SongMatchResult, songData: SongData) {
        switch result {
        case .notFound:
            print("✓ Song not found in database - showing import view")
            showSongConfirmationView(with: songData)
            
        case .exactMatch(let existingSong):
            print("⚠️ Exact match found - song already exists")
            self.existingSong = existingSong
            showSongExactMatchView(songData: songData, existingSong: existingSong)
            
        case .titleMatchNoMbid(let existingSong):
            print("⚠️ Title match with no MusicBrainz ID")
            self.existingSong = existingSong
            showSongTitleMatchNoMbidView(songData: songData, existingSong: existingSong)
            
        case .titleMatchDifferentMbid(let existingSong):
            print("⚠️ Title match with different MusicBrainz ID")
            self.existingSong = existingSong
            showSongTitleMatchDifferentMbidView(songData: songData, existingSong: existingSong)
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
    
    private func showSongConfirmationView(with songData: SongData) {
        print("🎨 Showing song confirmation view")
        
        let confirmationView = SongImportConfirmationView(
            songData: songData,
            onImport: { [weak self] in
                self?.importSong()
            },
            onCancel: { [weak self] in
                self?.cancelImport()
            }
        )
        
        replaceCurrentView(with: confirmationView)
    }
    
    private func showSongExactMatchView(songData: SongData, existingSong: ExistingSong) {
        print("🎨 Showing song exact match view")
        
        let view = SongExactMatchView(
            songData: songData,
            existingSong: existingSong,
            onOpenInApp: { [weak self] in
                self?.openSongInApp(songId: existingSong.id)
            },
            onCancel: { [weak self] in
                self?.cancelImport()
            }
        )
        
        replaceCurrentView(with: view)
    }
    
    private func showSongTitleMatchNoMbidView(songData: SongData, existingSong: ExistingSong) {
        print("🎨 Showing song title match (no MBID) view")
        
        let view = SongTitleMatchNoMbidView(
            songData: songData,
            existingSong: existingSong,
            onAssociate: { [weak self] in
                self?.showNotImplementedAlert("Associate MusicBrainz ID to song")
            },
            onCancel: { [weak self] in
                self?.cancelImport()
            }
        )
        
        replaceCurrentView(with: view)
    }
    
    private func showSongTitleMatchDifferentMbidView(songData: SongData, existingSong: ExistingSong) {
        print("🎨 Showing song title match (different MBID) view")
        
        let view = SongTitleMatchDifferentMbidView(
            songData: songData,
            existingSong: existingSong,
            onOverwrite: { [weak self] in
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
    // UPDATED importArtist() using NSLog instead of print()
    // NSLog is more reliable for extension debugging

    private func importArtist() {
        NSLog("🎯 importArtist() called")
        
        guard let artistData = artistData else {
            showError("No artist data to import")
            return
        }
        
        NSLog("💾 Saving artist data to shared container")
        SharedArtistData.saveSharedData(artistData, appGroup: appGroupIdentifier)
        NSLog("✅ Data saved successfully")
        
        // Show success message with clear next step
        DispatchQueue.main.async { [weak self] in
            let alert = UIAlertController(
                title: "✅ Artist Data Imported",
                message: "Open the Jazz Reference app to complete adding \(artistData.name) to your collection.",
                preferredStyle: .alert
            )
            
            alert.addAction(UIAlertAction(title: "Got It", style: .default) { [weak self] _ in
                NSLog("👋 User acknowledged, closing extension")
                // Extension will close, user manually opens main app
                self?.extensionContext?.completeRequest(returningItems: nil, completionHandler: nil)
            })
            
            self?.present(alert, animated: true)
        }
    }
    
    private func openMainAppForImport() {
        print("🔗 Opening main app for import...")
        
        guard let url = URL(string: "jazzreference://import-artist") else {
            print("❌ Invalid URL scheme")
            showError("Could not open main app")
            return
        }
        
        var responder = self as UIResponder?
        let selector = #selector(openURL(_:))
        
        while responder != nil {
            if responder!.responds(to: selector) && responder != self {
                responder!.perform(selector, with: url)
                
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) { [weak self] in
                    print("✅ Main app opened, closing extension")
                    self?.extensionContext?.completeRequest(returningItems: nil, completionHandler: nil)
                }
                return
            }
            responder = responder?.next
        }
        
        print("❌ Could not open URL")
        showError("Could not open main app")
    }

    @objc private func openURL(_ url: URL) {
        // Called via perform selector
    }
    
    private func openArtistInApp(artistId: String) {
        print("🔗 Opening artist in app: \(artistId)")
        
        // TODO: Implement deep link to open the main app at the artist detail page
        // For now, just show a placeholder
        showNotImplementedAlert("Open in App")
    }
    
    private func importSong() {
        print("💾 Importing song...")
        
        guard let songData = songData else {
            showError("No song data to import")
            return
        }
        
        NSLog("💾 Saving song data to shared container")
        SharedSongData.saveSharedData(songData, appGroup: appGroupIdentifier)
        NSLog("✅ Data saved successfully")
        
        // Show success message with clear next step
        DispatchQueue.main.async { [weak self] in
            let alert = UIAlertController(
                title: "✅ Song Data Imported",
                message: "Open the Jazz Reference app to complete adding \(songData.title) to your collection.",
                preferredStyle: .alert
            )
            
            alert.addAction(UIAlertAction(title: "Got It", style: .default) { [weak self] _ in
                NSLog("👋 User acknowledged, closing extension")
                self?.extensionContext?.completeRequest(returningItems: nil, completionHandler: nil)
            })
            
            self?.present(alert, animated: true)
        }
    }
    
    private func openSongInApp(songId: String) {
        print("🔗 Opening song in app: \(songId)")
        
        // TODO: Implement deep link to open the main app at the song detail page
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

// MARK: - Song Import Views

struct SongImportConfirmationView: View {
    let songData: SongData
    let onImport: () -> Void
    let onCancel: () -> Void
    
    var body: some View {
        VStack(spacing: 20) {
            VStack(spacing: 12) {
                Image(systemName: "music.note")
                    .font(.system(size: 50))
                    .foregroundColor(.blue)
                
                Text("Import Song")
                    .font(.title2)
                    .bold()
                
                Text("Review the song information below")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            }
            .padding(.top, 40)
            
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    InfoRow(label: "Title", value: songData.title)
                    
                    if let composerString = songData.composerString {
                        InfoRow(label: "Composer(s)", value: composerString)
                    }
                    
                    if let workType = songData.workType {
                        InfoRow(label: "Type", value: workType)
                    }
                    
                    if let key = songData.key {
                        InfoRow(label: "Key", value: key)
                    }
                    
                    InfoRow(label: "MusicBrainz ID", value: songData.musicbrainzId)
                }
                .padding()
            }
            .background(Color(.systemGray6))
            .cornerRadius(12)
            .padding(.horizontal)
            
            Spacer()
            
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

struct SongExactMatchView: View {
    let songData: SongData
    let existingSong: ExistingSong
    let onOpenInApp: () -> Void
    let onCancel: () -> Void
    
    var body: some View {
        VStack(spacing: 20) {
            VStack(spacing: 12) {
                Image(systemName: "checkmark.circle.fill")
                    .font(.system(size: 50))
                    .foregroundColor(.green)
                
                Text("Song Already Exists")
                    .font(.title2)
                    .bold()
                
                Text("\(songData.title) is already in the database")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
            }
            .padding(.top, 40)
            .padding(.horizontal)
            
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    Text("Database Record")
                        .font(.headline)
                        .foregroundColor(.secondary)
                    
                    InfoRow(label: "Title", value: existingSong.title)
                    
                    if let composer = existingSong.composer {
                        InfoRow(label: "Composer", value: composer)
                    }
                    
                    InfoRow(label: "MusicBrainz ID", value: existingSong.musicbrainzId ?? "None")
                }
                .padding()
            }
            .background(Color(.systemGray6))
            .cornerRadius(12)
            .padding(.horizontal)
            
            Spacer()
            
            VStack(spacing: 12) {
                Button(action: onOpenInApp) {
                    Text("Open in Jazz Reference")
                        .font(.headline)
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color.blue)
                        .cornerRadius(12)
                }
                
                Button(action: onCancel) {
                    Text("Done")
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

struct SongTitleMatchNoMbidView: View {
    let songData: SongData
    let existingSong: ExistingSong
    let onAssociate: () -> Void
    let onCancel: () -> Void
    
    var body: some View {
        VStack(spacing: 20) {
            VStack(spacing: 12) {
                Image(systemName: "link.circle.fill")
                    .font(.system(size: 50))
                    .foregroundColor(.orange)
                
                Text("Song Found Without ID")
                    .font(.title2)
                    .bold()
                
                Text("A song named \(songData.title) exists but has no MusicBrainz ID")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
            }
            .padding(.top, 40)
            .padding(.horizontal)
            
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Current Database Record")
                            .font(.headline)
                            .foregroundColor(.secondary)
                        
                        InfoRow(label: "Title", value: existingSong.title)
                        
                        if let composer = existingSong.composer {
                            InfoRow(label: "Composer", value: composer)
                        } else {
                            InfoRow(label: "Composer", value: "Not set")
                        }
                        
                        InfoRow(label: "MusicBrainz ID", value: "Not set")
                    }
                    .padding()
                    .background(Color(.systemGray5))
                    .cornerRadius(8)
                    
                    HStack {
                        Spacer()
                        Image(systemName: "arrow.down")
                            .foregroundColor(.secondary)
                        Spacer()
                    }
                    
                    VStack(alignment: .leading, spacing: 12) {
                        Text("MusicBrainz Data")
                            .font(.headline)
                            .foregroundColor(.secondary)
                        
                        InfoRow(label: "Title", value: songData.title)
                        
                        if let composerString = songData.composerString {
                            InfoRow(label: "Composer(s)", value: composerString)
                        }
                        
                        InfoRow(label: "MusicBrainz ID", value: songData.musicbrainzId)
                    }
                    .padding()
                    .background(Color.blue.opacity(0.1))
                    .cornerRadius(8)
                }
                .padding(.horizontal)
            }
            
            Spacer()
            
            VStack(spacing: 12) {
                Button(action: onAssociate) {
                    Text("Associate MusicBrainz ID")
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

struct SongTitleMatchDifferentMbidView: View {
    let songData: SongData
    let existingSong: ExistingSong
    let onOverwrite: () -> Void
    let onCancel: () -> Void
    
    var body: some View {
        VStack(spacing: 20) {
            VStack(spacing: 12) {
                Image(systemName: "exclamationmark.triangle.fill")
                    .font(.system(size: 50))
                    .foregroundColor(.red)
                
                Text("Different Song Found")
                    .font(.title2)
                    .bold()
                
                Text("A song named \(songData.title) exists with a different MusicBrainz ID")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
            }
            .padding(.top, 40)
            .padding(.horizontal)
            
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Current Database Record")
                            .font(.headline)
                            .foregroundColor(.secondary)
                        
                        InfoRow(label: "Title", value: existingSong.title)
                        
                        if let composer = existingSong.composer {
                            InfoRow(label: "Composer", value: composer)
                        }
                        
                        InfoRow(label: "MusicBrainz ID", value: existingSong.musicbrainzId ?? "None")
                    }
                    .padding()
                    .background(Color(.systemGray5))
                    .cornerRadius(8)
                    
                    HStack {
                        Spacer()
                        Text("VS")
                            .font(.headline)
                            .foregroundColor(.red)
                        Spacer()
                    }
                    
                    VStack(alignment: .leading, spacing: 12) {
                        Text("MusicBrainz Data")
                            .font(.headline)
                            .foregroundColor(.secondary)
                        
                        InfoRow(label: "Title", value: songData.title)
                        
                        if let composerString = songData.composerString {
                            InfoRow(label: "Composer(s)", value: composerString)
                        }
                        
                        InfoRow(label: "MusicBrainz ID", value: songData.musicbrainzId)
                    }
                    .padding()
                    .background(Color.red.opacity(0.1))
                    .cornerRadius(8)
                }
                .padding(.horizontal)
            }
            
            VStack(spacing: 8) {
                Text("⚠️ Warning")
                    .font(.headline)
                    .foregroundColor(.red)
                
                Text("These may be different songs with the same title. Overwriting will replace the existing MusicBrainz ID.")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
            }
            .padding(.horizontal)
            
            Spacer()
            
            VStack(spacing: 12) {
                Button(action: onOverwrite) {
                    Text("Overwrite MusicBrainz ID")
                        .font(.headline)
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color.red)
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

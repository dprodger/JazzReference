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
    private var youtubeData: YouTubeData?
    private var isSongImport: Bool = false
    private var isYouTubeImport: Bool = false
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
        NSLog("🔍 Starting data extraction...")
        
        // We can't reliably detect the page type before JavaScript preprocessing
        // because the URL might not be available in the share extension context.
        // Instead, we'll extract the data and let the JavaScript tell us what type it is
        // based on the URL and fields it returns.
        extractData()
    }
    
    private func extractData() {
        NSLog("🔍 Extracting page data...")
        
        // Get the extension context
        guard let extensionItem = extensionContext?.inputItems.first as? NSExtensionItem else {
            NSLog("❌ No extension item found")
            showError("No data available")
            return
        }
        
        guard let itemProvider = extensionItem.attachments?.first else {
            NSLog("❌ No item provider found")
            showError("No data available")
            return
        }
        
        NSLog("✓ Extension item and provider found")
        
        // Check for property list (JavaScript preprocessing results)
        let propertyListType = "com.apple.property-list"
        
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
                
                // The item should be a Dictionary containing the JavaScript preprocessing results
                if let dictionary = item as? [String: Any] {
                    NSLog("✓ Got dictionary from item")
                    
                    // Check for the JavaScript preprocessing results key
                    if let results = dictionary[NSExtensionJavaScriptPreprocessingResultsKey] as? [String: Any] {
                        NSLog("✓ Got JavaScript preprocessing results")
                        
                        DispatchQueue.main.async {
                            self.processExtractedData(results)
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
                                    self.processExtractedData(results)
                                }
                                return
                            }
                        }
                    } catch {
                        NSLog("❌ Failed to deserialize property list: \(error)")
                    }
                    DispatchQueue.main.async {
                        self.showError("Invalid data format")
                    }
                } else {
                    NSLog("❌ Item is not Dictionary or Data: \(type(of: item))")
                    DispatchQueue.main.async {
                        self.showError("Invalid data format")
                    }
                }
            }
        } else {
            NSLog("❌ No property list type found")
            showError("This extension only works with web pages(!)")
        }
    }
    
    // MARK: - Data Processing
    private func processExtractedData(_ data: [String: Any]) {
        NSLog("📄 Processing extracted data...")

        // Check for error from JavaScript
        if let error = data["error"] as? String {
            NSLog("❌ JavaScript error: \(error)")
            showError(error)
            return
        }

        // Detect page type based on the fields present in the JavaScript results
        // YouTube pages have "pageType" = "youtube"
        // Song/work pages have "title", artist pages have "name"
        if let pageType = data["pageType"] as? String, pageType == "youtube" {
            NSLog("📍 Detected: YouTube page")
            processYouTubeData(data)
        } else if let _ = data["title"] as? String {
            NSLog("📍 Detected: Song/Work page (has 'title' field)")
            processSongData(data)
        } else if let _ = data["name"] as? String {
            NSLog("📍 Detected: Artist page (has 'name' field)")
            processArtistData(data)
        } else {
            NSLog("❌ Could not determine page type from JavaScript results")
            NSLog("   Available keys: \(data.keys.joined(separator: ", "))")
            showError("Could not extract data from this page")
        }
    }
    
    private func processArtistData(_ data: [String: Any]) {
        NSLog("🎵 Processing artist data...")
        
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
        
        NSLog("   Artist: \(artistData.name)")
        NSLog("   MusicBrainz ID: \(artistData.musicbrainzId)")
        
        // Validate that we got at least a name and ID
        guard !artistData.name.isEmpty, !artistData.musicbrainzId.isEmpty else {
            NSLog("❌ Missing required fields - name: '\(artistData.name)', id: '\(artistData.musicbrainzId)'")
            showError("Could not extract artist information from this page")
            return
        }
        
        self.artistData = artistData
        NSLog("✅ Artist data validation passed")
        
        // Check if artist already exists in database
        checkArtistExistence(artistData)
    }
    
    // MARK: - Database Checking
    private func checkArtistExistence(_ artistData: ArtistData) {
        NSLog("🔍 Checking if artist exists in database...")
        
        // Show loading indicator
        showLoadingView()
        
        Task {
            do {
                let result = try await ArtistDatabaseService.shared.checkArtistExists(
                    name: artistData.name,
                    musicbrainzId: artistData.musicbrainzId
                )
                
                await MainActor.run {
                    NSLog("✅ Database check complete")
                    self.handleArtistMatchResult(result, artistData: artistData)
                }
            } catch {
                await MainActor.run {
                    NSLog("⚠️ Database check failed: \(error.localizedDescription)")
                    NSLog("   Proceeding with import anyway...")
                    // If database check fails, just proceed with normal import
                    self.showConfirmationView(with: artistData)
                }
            }
        }
    }
    
    private func handleArtistMatchResult(_ result: ArtistMatchResult, artistData: ArtistData) {
        switch result {
        case .notFound:
            NSLog("ℹ️ Artist not found - showing normal import")
            showConfirmationView(with: artistData)
            
        case .exactMatch(let existingArtist):
            NSLog("ℹ️ Exact match found - artist already exists")
            self.existingArtist = existingArtist
            showExactMatchView(artistData: artistData, existingArtist: existingArtist)
            
        case .nameMatchNoMbid(let existingArtist):
            NSLog("ℹ️ Name match with blank MusicBrainz ID")
            self.existingArtist = existingArtist
            showNameMatchNoMbidView(artistData: artistData, existingArtist: existingArtist)
            
        case .nameMatchDifferentMbid(let existingArtist):
            NSLog("ℹ️ Name match with different MusicBrainz ID")
            self.existingArtist = existingArtist
            showNameMatchDifferentMbidView(artistData: artistData, existingArtist: existingArtist)
        }
    }
    
    // MARK: - Song Processing
    
    private func processSongData(_ data: [String: Any]) {
        NSLog("🎵 Processing song data...")
        NSLog("   Data keys: \(data.keys.joined(separator: ", "))")
        
        // Check if there's an error from JavaScript
        if let error = data["error"] as? String {
            NSLog("❌ JavaScript error: \(error)")
            showError(error)
            return
        }
        
        // Extract required fields
        guard let title = data["title"] as? String,
              !title.isEmpty else {
            NSLog("❌ Missing or empty title")
            showError("Could not extract song title from page")
            return
        }
        
        guard let musicbrainzId = data["musicbrainzId"] as? String,
              !musicbrainzId.isEmpty else {
            NSLog("❌ Missing or empty MusicBrainz ID")
            showError("Could not extract MusicBrainz ID from page")
            return
        }
        
        NSLog("   Title: \(title)")
        NSLog("   MusicBrainz ID: \(musicbrainzId)")
        
        // Extract optional fields
        let composers = data["composers"] as? [String]
        let workType = data["workType"] as? String
        let key = data["key"] as? String
        let annotation = data["annotation"] as? String
        let wikipediaUrl = data["wikipediaUrl"] as? String
        let sourceUrl = data["url"] as? String
        
        // Log optional fields if present
        if let composers = composers, !composers.isEmpty {
            NSLog("   Composers: \(composers.joined(separator: ", "))")
        }
        if let workType = workType {
            NSLog("   Work Type: \(workType)")
        }
        
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
        
        NSLog("✅ Song data validation passed")
        
        // Check if song already exists in database
        showLoadingView()
        checkSongMatch(songData: songData)
    }
    
    private func checkSongMatch(songData: SongData) {
        Task {
            do {
                NSLog("🔍 Checking if song exists in database...")
                let result = try await SongDatabaseService.shared.checkSongExists(
                    title: songData.title,
                    musicbrainzId: songData.musicbrainzId
                )
                
                DispatchQueue.main.async {
                    self.processSongMatch(result: result, songData: songData)
                }
            } catch {
                NSLog("❌ Error checking song: \(error)")
                DispatchQueue.main.async {
                    // If database check fails, just proceed with import
                    NSLog("⚠️ Database check failed, proceeding with import anyway...")
                    self.showSongConfirmationView(with: songData)
                }
            }
        }
    }
    
    private func processSongMatch(result: SongMatchResult, songData: SongData) {
        switch result {
        case .notFound:
            NSLog("✓ Song not found in database - showing import view")
            showSongConfirmationView(with: songData)

        case .exactMatch(let existingSong):
            NSLog("⚠️ Exact match found - song already exists")
            self.existingSong = existingSong
            showSongExactMatchView(songData: songData, existingSong: existingSong)

        case .titleMatchNoMbid(let existingSong):
            NSLog("⚠️ Title match with no MusicBrainz ID")
            self.existingSong = existingSong
            showSongTitleMatchNoMbidView(songData: songData, existingSong: existingSong)

        case .titleMatchDifferentMbid(let existingSong):
            NSLog("⚠️ Title match with different MusicBrainz ID")
            self.existingSong = existingSong
            showSongTitleMatchDifferentMbidView(songData: songData, existingSong: existingSong)
        }
    }

    // MARK: - YouTube Processing

    private func processYouTubeData(_ data: [String: Any]) {
        NSLog("🎬 Processing YouTube data...")
        NSLog("   Data keys: \(data.keys.joined(separator: ", "))")

        // Extract required fields
        guard let videoId = data["videoId"] as? String, !videoId.isEmpty else {
            NSLog("❌ Missing or empty video ID")
            showError("Could not extract video ID from YouTube page")
            return
        }

        guard let title = data["title"] as? String, !title.isEmpty else {
            NSLog("❌ Missing or empty title")
            showError("Could not extract video title from YouTube page")
            return
        }

        guard let url = data["url"] as? String else {
            NSLog("❌ Missing URL")
            showError("Could not get YouTube URL")
            return
        }

        NSLog("   Video ID: \(videoId)")
        NSLog("   Title: \(title)")

        // Extract optional fields
        let channelName = data["channelName"] as? String
        let description = data["description"] as? String

        // Create YouTubeData
        let youtubeData = YouTubeData(
            videoId: videoId,
            title: title,
            url: url,
            channelName: channelName,
            description: description,
            videoType: nil,
            songId: nil,
            recordingId: nil
        )

        self.youtubeData = youtubeData
        self.isYouTubeImport = true

        NSLog("✅ YouTube data validation passed")

        // Show YouTube type selection view
        showYouTubeTypeSelectionView(with: youtubeData)
    }
    
    // MARK: - UI Views
    
    private func showLoadingView() {
        let loadingView = LoadingView()
        replaceCurrentView(with: loadingView)
    }
    
    private func showConfirmationView(with artistData: ArtistData) {
        NSLog("🎨 Showing confirmation view")
        
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
        NSLog("🎨 Showing exact match view")
        
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
        NSLog("🎨 Showing name match (no MBID) view")
        
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
        NSLog("🎨 Showing name match (different MBID) view")
        
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
        NSLog("🎨 Showing song confirmation view")
        
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
        NSLog("🎨 Showing song exact match view")
        
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
        NSLog("🎨 Showing song title match (no MBID) view")
        
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
        NSLog("🎨 Showing song title match (different MBID) view")
        
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

    // MARK: - YouTube UI Views

    private func showYouTubeTypeSelectionView(with youtubeData: YouTubeData) {
        NSLog("🎨 Showing YouTube type selection view")

        let view = YouTubeTypeSelectionView(
            youtubeData: youtubeData,
            onSelectType: { [weak self] selectedType in
                self?.handleYouTubeTypeSelected(youtubeData: youtubeData, type: selectedType)
            },
            onCancel: { [weak self] in
                self?.cancelImport()
            }
        )

        replaceCurrentView(with: view)
    }

    private func handleYouTubeTypeSelected(youtubeData: YouTubeData, type: YouTubeVideoType) {
        NSLog("🎬 YouTube type selected: \(type.rawValue)")

        // Update youtubeData with selected type
        var updatedData = youtubeData
        updatedData.videoType = type

        self.youtubeData = updatedData

        // Save to shared container and open main app for song selection
        SharedYouTubeData.saveSharedData(updatedData, appGroup: appGroupIdentifier)

        // Open main app to continue import (song selection happens there)
        openMainApp(path: "import-youtube")
    }

    private func showError(_ message: String) {
        NSLog("⚠️ Showing error: \(message)")
        
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
    // UPDATED importArtist() using NSLog instead of NSLog()
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

        // Try to open the main app directly
        openMainApp(path: "import-artist")
    }
    
    private func openMainApp(path: String) {
        print("🔗 [ShareExt] Opening main app with path: \(path)")
        NSLog("🔗 Opening main app with path: %@", path)

        guard let url = URL(string: "jazzreference://\(path)") else {
            print("❌ [ShareExt] Invalid URL scheme")
            NSLog("❌ Invalid URL scheme")
            fallbackToManualOpen(path: path)
            return
        }

        print("🔗 [ShareExt] Attempting to open URL: \(url)")
        NSLog("🔗 Attempting to open URL: %@", url.absoluteString)

        // Method 1: Try NSExtensionContext.open (works on iOS 16+ for some extension types)
        if #available(iOS 16.0, *) {
            print("🔗 [ShareExt] Trying extensionContext.open()")
            extensionContext?.open(url) { [weak self] success in
                print("🔗 [ShareExt] extensionContext.open completed, success: \(success)")
                NSLog("🔗 extensionContext.open completed, success: %d", success)

                if success {
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                        self?.extensionContext?.completeRequest(returningItems: nil, completionHandler: nil)
                    }
                } else {
                    // Fall back to responder chain
                    DispatchQueue.main.async {
                        self?.tryResponderChain(url: url, path: path)
                    }
                }
            }
            return
        }

        // For older iOS, go straight to responder chain
        tryResponderChain(url: url, path: path)
    }

    private func tryResponderChain(url: URL, path: String) {
        print("🔗 [ShareExt] Trying responder chain approach")
        NSLog("🔗 Trying responder chain approach")

        var responder: UIResponder? = self

        while let r = responder {
            print("🔗 [ShareExt] Checking responder: \(type(of: r))")

            // Check if this responder is UIApplication (or can open URLs)
            // We need to use the modern open(_:options:completionHandler:) API
            if let application = r as? UIApplication {
                print("✅ [ShareExt] Found UIApplication, using modern open API")
                NSLog("✅ Found UIApplication, using modern open API")

                application.open(url, options: [:]) { [weak self] success in
                    print("🔗 [ShareExt] UIApplication.open completed, success: \(success)")
                    NSLog("🔗 UIApplication.open completed, success: %d", success)

                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                        self?.extensionContext?.completeRequest(returningItems: nil, completionHandler: nil)
                    }
                }
                return
            }
            responder = r.next
        }

        print("⚠️ [ShareExt] Responder chain failed - no UIApplication found")
        NSLog("⚠️ Responder chain approach failed")
        fallbackToManualOpen(path: path)
    }

    private func fallbackToManualOpen(path: String) {
        print("⚠️ [ShareExt] Using fallback manual open")
        NSLog("⚠️ Using fallback manual open")

        DispatchQueue.main.async { [weak self] in
            let alert = UIAlertController(
                title: "Data Saved",
                message: "Open Approach Note to complete the import.",
                preferredStyle: .alert
            )

            alert.addAction(UIAlertAction(title: "OK", style: .default) { [weak self] _ in
                self?.extensionContext?.completeRequest(returningItems: nil, completionHandler: nil)
            })

            self?.present(alert, animated: true)
        }
    }

    @objc private func openURL(_ url: URL) {
        // Placeholder for selector - actual implementation is in UIApplication
    }
    
    private func openArtistInApp(artistId: String) {
        NSLog("🔗 Opening artist in app: \(artistId)")
        openMainApp(path: "artist/\(artistId)")
    }
    
    private func importSong() {
        print("💾 [ShareExt] importSong() called")
        NSLog("💾 importSong() called")

        guard let songData = songData else {
            print("❌ [ShareExt] No song data")
            showError("No song data to import")
            return
        }

        print("💾 [ShareExt] Saving song: \(songData.title)")
        NSLog("💾 Saving song data to shared container: %@", songData.title)
        SharedSongData.saveSharedData(songData, appGroup: appGroupIdentifier)
        print("✅ [ShareExt] Data saved, now opening main app")
        NSLog("✅ Data saved successfully, opening main app")

        // Try to open the main app directly
        openMainApp(path: "import-song")
    }
    
    private func openSongInApp(songId: String) {
        NSLog("🔗 Opening song in app: \(songId)")
        openMainApp(path: "song/\(songId)")
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
        NSLog("❌ User cancelled import")
        extensionContext?.completeRequest(returningItems: nil, completionHandler: nil)
    }
    
    private func showSuccessAndClose() {
        NSLog("✅ Showing success message")
        
        // Show brief success message
        let successView = SuccessView()
        replaceCurrentView(with: successView)
        
        // Close after a brief delay
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) { [weak self] in
            NSLog("👋 Closing extension")
            self?.extensionContext?.completeRequest(returningItems: nil, completionHandler: nil)
        }
    }
}

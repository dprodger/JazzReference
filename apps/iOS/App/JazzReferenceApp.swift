// JazzReferenceApp.swift
// Main app entry point with deep link handling

import SwiftUI
import GoogleSignIn

@main
struct JazzReferenceApp: App {
    @State private var showingArtistCreation = false
    @State private var importedArtistData: ImportedArtistData?
    @Environment(\.scenePhase) var scenePhase
    @State private var showingSongCreation = false
    @State private var importedSongData: ImportedSongData?
    @State private var importedYouTubeData: ImportedYouTubeData?
    @StateObject private var repertoireManager = RepertoireManager()
    @StateObject private var authManager = AuthenticationManager()
    @StateObject private var favoritesManager = FavoritesManager()

    // Password reset state
    @State private var resetPasswordToken: String?

    // Deep link navigation state
    @State private var deepLinkSongId: String?
    @State private var deepLinkArtistId: String?

    // Onboarding state - persisted across launches
    @AppStorage("hasCompletedOnboarding") private var hasCompletedOnboarding = false
    @State private var showingOnboarding = false

    init() {
        // Configure navigation bar fonts from JazzTheme
        JazzTheme.configureNavigationBarAppearance()

        // Restore previous Google Sign-In session (skip in previews)
        #if DEBUG
        if ProcessInfo.processInfo.environment["XCODE_RUNNING_FOR_PREVIEWS"] != "1" {
            GIDSignIn.sharedInstance.restorePreviousSignIn { user, error in
                if error != nil || user == nil {
                    // User is not signed in
                } else {
                    // User is signed in
                }
            }
        }
        #else
        GIDSignIn.sharedInstance.restorePreviousSignIn { user, error in
            if error != nil || user == nil {
                // User is not signed in
            } else {
                // User is signed in
            }
        }
        #endif
    }
    
    var body: some Scene {
        WindowGroup {
            ContentView()
                .onOpenURL { url in
                    NSLog("🔗 Received deep link: \(url)")
                    
                    // Handle password reset: jazzreference://auth/reset-password?token=xyz
                    if url.scheme == "jazzreference" && url.host == "auth" && url.path == "/reset-password" {
                        NSLog("🔑 Password reset deep link detected")
                        
                        // Extract token from query parameters
                        if let components = URLComponents(url: url, resolvingAgainstBaseURL: false),
                           let queryItems = components.queryItems,
                           let tokenItem = queryItems.first(where: { $0.name == "token" }),
                           let token = tokenItem.value {
                            NSLog("✅ Found reset token, showing ResetPasswordView")
                            resetPasswordToken = token
                        } else {
                            NSLog("❌ No token found in reset password deep link")
                        }
                    }
                    // Handle artist import: jazzreference://import-artist
                    else if url.scheme == "jazzreference" && url.host == "import-artist" {
                        NSLog("🎵 Artist import deep link detected")
                        checkForImportedArtist()
                    }
                    // Handle song import: jazzreference://import-song
                    else if url.scheme == "jazzreference" && url.host == "import-song" {
                        NSLog("🎵 Song import deep link detected")
                        checkForImportedSong()
                    }
                    // Handle YouTube import: jazzreference://import-youtube
                    else if url.scheme == "jazzreference" && url.host == "import-youtube" {
                        NSLog("🎬 YouTube import deep link detected")
                        checkForImportedYouTube()
                    }
                    // Handle song view: jazzreference://song/{songId}
                    else if url.scheme == "jazzreference" && url.host == "song" {
                        let songId = url.path.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
                        NSLog("🎵 Song deep link detected: %@", songId)
                        if !songId.isEmpty {
                            // Clear any pending import data to avoid sheet conflicts
                            importedSongData = nil
                            importedArtistData = nil
                            deepLinkSongId = songId
                        }
                    }
                    // Handle artist view: jazzreference://artist/{artistId}
                    else if url.scheme == "jazzreference" && url.host == "artist" {
                        let artistId = url.path.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
                        NSLog("🎵 Artist deep link detected: %@", artistId)
                        if !artistId.isEmpty {
                            // Clear any pending import data to avoid sheet conflicts
                            importedSongData = nil
                            importedArtistData = nil
                            deepLinkArtistId = artistId
                        }
                    }
                    else {
                        NSLog("❓ Unrecognized deep link format: \(url)")
                    }
                }
                .onAppear {
                    // PHASE 5: Connect RepertoireManager to AuthenticationManager
                    repertoireManager.setAuthManager(authManager)
                    print("📚 Connected RepertoireManager to AuthenticationManager")

                    // Connect FavoritesManager to AuthenticationManager
                    favoritesManager.setAuthManager(authManager)
                    print("❤️ Connected FavoritesManager to AuthenticationManager")

                    // Show onboarding on first launch
                    if !hasCompletedOnboarding {
                        showingOnboarding = true
                    }
                }
                .onChange(of: scenePhase) { oldPhase, newPhase in
                    if newPhase == .active {
                        // Only check for imports if we're not handling a direct deep link
                        // This prevents sheet conflicts
                        if deepLinkSongId == nil && deepLinkArtistId == nil {
                            checkForImportedArtist()
                            checkForImportedSong()
                            checkForImportedYouTube()
                        }
                    }
                }
                .onChange(of: authManager.isAuthenticated) { wasAuthenticated, isAuthenticated in
                    // PHASE 5: Update repertoire manager when auth state changes
                    if isAuthenticated {
                        print("📚 User authenticated - loading repertoires")
                        Task {
                            await repertoireManager.loadRepertoires()
                        }
                        print("❤️ User authenticated - loading favorites")
                        Task {
                            await favoritesManager.loadFavorites()
                        }
                    } else {
                        print("📚 User logged out - clearing repertoires")
                        Task {
                            await repertoireManager.loadRepertoires()
                        }
                        print("❤️ User logged out - clearing favorites")
                        favoritesManager.clearFavorites()
                    }
                }
                .sheet(item: $importedArtistData) { data in
                    // CHANGED: Use .sheet(item:) instead of isPresented
                    NavigationStack {
                        ArtistCreationView(importedData: data)
                    }
                }
                .sheet(item: $importedSongData) { data in
                    NavigationStack {
                        SongCreationView(importedData: data)
                    }
                }
                .sheet(item: Binding(
                    get: { resetPasswordToken.map { ResetPasswordData(token: $0) } },
                    set: { resetPasswordToken = $0?.token }
                )) { data in
                    ResetPasswordView(token: data.token)
                        .environmentObject(authManager)
                }
                .sheet(item: Binding(
                    get: { deepLinkSongId.map { DeepLinkSongData(songId: $0) } },
                    set: { deepLinkSongId = $0?.songId }
                )) { data in
                    NavigationStack {
                        SongDetailView(songId: data.songId)
                            .environmentObject(repertoireManager)
                    }
                }
                .sheet(item: Binding(
                    get: { deepLinkArtistId.map { DeepLinkArtistData(artistId: $0) } },
                    set: { deepLinkArtistId = $0?.artistId }
                )) { data in
                    NavigationStack {
                        PerformerDetailView(performerId: data.artistId)
                    }
                }
                .sheet(item: $importedYouTubeData) { data in
                    NavigationStack {
                        YouTubeImportView(youtubeData: data) {
                            // On successful import, clear the data
                            SharedYouTubeDataManager.clearSharedData()
                            importedYouTubeData = nil
                        } onCancel: {
                            SharedYouTubeDataManager.clearSharedData()
                            importedYouTubeData = nil
                        }
                    }
                }
                .fullScreenCover(isPresented: $showingOnboarding) {
                    OnboardingView(isPresented: $showingOnboarding)
                        .onDisappear {
                            // Mark onboarding as completed when dismissed
                            hasCompletedOnboarding = true
                        }
                }
                .ignoresSafeArea()
                .environmentObject(authManager)
                .onOpenURL { url in
                    GIDSignIn.sharedInstance.handle(url)
                }
                .environmentObject(repertoireManager)
                .environmentObject(favoritesManager)
        }
    }
    
    private func checkForImportedArtist() {
        if let data = SharedArtistDataManager.retrieveSharedData() {
            NSLog("📥 Imported artist data detected: %@", data.name)
            importedArtistData = data
            showingArtistCreation = true
        }
    }
    
    private func checkForImportedSong() {
        if let data = SharedSongDataManager.retrieveSharedData() {
            NSLog("📥 Imported song data detected: %@", data.title)
            importedSongData = data
            showingSongCreation = true
        }
    }

    private func checkForImportedYouTube() {
        // Don't check if we already have YouTube data being displayed
        guard importedYouTubeData == nil else {
            NSLog("ℹ️ YouTube import already in progress, skipping check")
            return
        }

        if let data = SharedYouTubeDataManager.retrieveSharedData() {
            NSLog("📥 Imported YouTube data detected: %@", data.title)
            // Clear the shared data immediately to prevent duplicate imports
            SharedYouTubeDataManager.clearSharedData()
            importedYouTubeData = data
        }
    }
    
    // Handle URL for Google Sign In
    func application(_ app: UIApplication,
                    open url: URL,
                    options: [UIApplication.OpenURLOptionsKey: Any] = [:]) -> Bool {
        return GIDSignIn.sharedInstance.handle(url)
    }

}

// MARK: - Helper Structs

// Helper struct for password reset sheet binding
struct ResetPasswordData: Identifiable {
    let id = UUID()
    let token: String
}

// Helper struct for deep link song navigation
struct DeepLinkSongData: Identifiable {
    let id = UUID()
    let songId: String
}

// Helper struct for deep link artist navigation
struct DeepLinkArtistData: Identifiable {
    let id = UUID()
    let artistId: String
}


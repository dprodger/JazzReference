// Jazz Reference iOS App
// SwiftUI application for browsing jazz standards
// UPDATED FOR PHASE 5: Connected AuthenticationManager to RepertoireManager
// UPDATED: Added onboarding flow for first-time users

import SwiftUI
import Combine

import GoogleSignIn


// MARK: - Main View

// MARK: - Main View
// Updated ContentView with Recordings tab

struct ContentView: View {
    @EnvironmentObject var authManager: AuthenticationManager
    
    var body: some View {
        TabView {
            SongsListView()
                .tabItem {
                    Label("Songs", systemImage: "music.note.list")
                }
            
            ArtistsListView()
                .tabItem {
                    Label("Artists", systemImage: "person.2.fill")
                }
            
            RecordingsListView()
                .tabItem {
                    Label("Recordings", systemImage: "opticaldisc")
                }
            
            // Settings Tab (protected)
            Group {
                if authManager.isAuthenticated {
                    SettingsView()
                        .environmentObject(authManager)
                } else {
                    RepertoireLoginPromptView()
                }
            }
            .tabItem {
                Label("Settings", systemImage: "gearshape.fill")
            }

            AboutView()
                .tabItem {
                    Label("About", systemImage: "info.circle")
                }
            
        }
        .onAppear {
            // Set up tab bar appearance with opaque background
            let appearance = UITabBarAppearance()
            appearance.configureWithOpaqueBackground()
            appearance.backgroundColor = UIColor(JazzTheme.backgroundLight)

            // Set unselected item color (light gray)
            appearance.stackedLayoutAppearance.normal.iconColor = UIColor.lightGray
            appearance.stackedLayoutAppearance.normal.titleTextAttributes = [.foregroundColor: UIColor.lightGray]

            // Set selected item color (burgundy)
            appearance.stackedLayoutAppearance.selected.iconColor = UIColor(JazzTheme.burgundy)
            appearance.stackedLayoutAppearance.selected.titleTextAttributes = [.foregroundColor: UIColor(JazzTheme.burgundy)]

            UITabBar.appearance().standardAppearance = appearance
            UITabBar.appearance().scrollEdgeAppearance = appearance
        }
        .tint(JazzTheme.burgundy) // Sets the active tab color
    }
}

// MARK: - Settings View

struct SettingsView: View {
    @EnvironmentObject var authManager: AuthenticationManager
    @AppStorage("preferredStreamingService") private var preferredStreamingService: String = StreamingService.spotify.rawValue

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 24) {
                    // User Info Section
                    VStack(spacing: 16) {
                        // Profile Icon
                        Circle()
                            .fill(JazzTheme.burgundy.gradient)
                            .frame(width: 80, height: 80)
                            .overlay {
                                Image(systemName: "person.fill")
                                    .font(.system(size: 40))
                                    .foregroundColor(.white)
                            }

                        // Name
                        if let displayName = authManager.currentUser?.displayName {
                            Text(displayName)
                                .font(JazzTheme.title2())
                                .fontWeight(.semibold)
                                .foregroundColor(JazzTheme.charcoal)
                        }

                        // Email
                        if let email = authManager.currentUser?.email {
                            Text(email)
                                .font(JazzTheme.body())
                                .foregroundColor(JazzTheme.smokeGray)
                        }
                    }
                    .padding(.top, 32)

                    Divider()
                        .padding(.horizontal)

                    // Playback Settings Section
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Playback")
                            .font(JazzTheme.headline())
                            .foregroundColor(JazzTheme.charcoal)
                            .padding(.horizontal)

                        VStack(spacing: 0) {
                            HStack {
                                Image(systemName: "play.circle.fill")
                                    .foregroundColor(JazzTheme.burgundy)
                                Text("Preferred Service")
                                    .font(JazzTheme.body())
                                    .foregroundColor(JazzTheme.charcoal)
                                Spacer()
                                Picker("", selection: $preferredStreamingService) {
                                    ForEach(StreamingService.allCases) { service in
                                        Text(service.displayName).tag(service.rawValue)
                                    }
                                }
                                .pickerStyle(.menu)
                                .tint(JazzTheme.burgundy)
                            }
                            .padding()
                            .background(JazzTheme.cardBackground)
                            .cornerRadius(8)
                        }
                        .padding(.horizontal)

                        Text("Play buttons will open this service when available")
                            .font(JazzTheme.caption())
                            .foregroundColor(JazzTheme.smokeGray)
                            .padding(.horizontal)
                    }

                    Divider()
                        .padding(.horizontal)

                    // Account Actions
                    VStack(spacing: 0) {
                        // Log Out Button
                        Button(action: {
                            authManager.logout()
                        }) {
                            HStack {
                                Image(systemName: "rectangle.portrait.and.arrow.right")
                                    .foregroundColor(JazzTheme.burgundy)
                                Text("Log Out")
                                    .foregroundColor(JazzTheme.charcoal)
                                Spacer()
                            }
                            .padding()
                            .background(JazzTheme.cardBackground)
                            .cornerRadius(8)
                        }
                        .padding(.horizontal)
                    }

                    Spacer()
                }
            }
            .background(JazzTheme.backgroundLight)
            .jazzNavigationBar(title: "Settings")
        }
    }
}


import SwiftUI

// Add this to JazzReferenceApp.swift in the App struct
// This will verify the URL scheme is properly registered

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

    // Password reset state
    @State private var resetPasswordToken: String?

    // Deep link navigation state
    @State private var deepLinkSongId: String?
    @State private var deepLinkArtistId: String?

    // Onboarding state - persisted across launches
    @AppStorage("hasCompletedOnboarding") private var hasCompletedOnboarding = false
    @State private var showingOnboarding = false

    // ADD THIS INITIALIZER
    init() {
        // Configure navigation bar fonts from JazzTheme
        JazzTheme.configureNavigationBarAppearance()

        // Diagnostic: Check URL scheme registration
        NSLog("========================================")
        NSLog("🔧 MAIN APP URL SCHEME DIAGNOSTICS")
        NSLog("========================================")
        
        // Check if CFBundleURLTypes is in Info.plist
        if let urlTypes = Bundle.main.object(forInfoDictionaryKey: "CFBundleURLTypes") as? [[String: Any]] {
            NSLog("✅ CFBundleURLTypes found in Info.plist")
            NSLog("   Number of URL types: %d", urlTypes.count)
            
            for (index, urlType) in urlTypes.enumerated() {
                NSLog("\n   URL Type %d:", index)
                
                if let name = urlType["CFBundleURLName"] as? String {
                    NSLog("   - Name: %@", name)
                }
                
                if let schemes = urlType["CFBundleURLSchemes"] as? [String] {
                    NSLog("   - Schemes: %@", schemes.joined(separator: ", "))
                    
                    if schemes.contains("jazzreference") {
                        NSLog("   ✅ Contains 'jazzreference'")
                    }
                }
                
                if let role = urlType["CFBundleTypeRole"] as? String {
                    NSLog("   - Role: %@", role)
                }
            }
        } else {
            NSLog("❌ CFBundleURLTypes NOT FOUND in Info.plist")
            NSLog("   URL scheme may be in build settings only")
            NSLog("   Extensions require it in Info.plist!")
        }
        
        NSLog("\nBundle ID: %@", Bundle.main.bundleIdentifier ?? "nil")
        NSLog("========================================\n")
        
        // In your App init or AppDelegate didFinishLaunching
        GIDSignIn.sharedInstance.restorePreviousSignIn { user, error in
            if error != nil || user == nil {
                // User is not signed in
            } else {
                // User is signed in
            }
        }
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
                    checkForImportedArtist()
                    checkForImportedSong()
                    checkForImportedYouTube()

                    // PHASE 5: Connect RepertoireManager to AuthenticationManager
                    repertoireManager.setAuthManager(authManager)
                    print("📚 Connected RepertoireManager to AuthenticationManager")

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
                    } else {
                        print("📚 User logged out - clearing repertoires")
                        Task {
                            await repertoireManager.loadRepertoires()
                        }
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
        }
    }
    
    private func checkForImportedArtist() {
        if let data = SharedArtistDataManager.retrieveSharedData() {
            NSLog("📥 Imported artist data detected: %@", data.name)
            importedArtistData = data
            showingArtistCreation = true
        } else {
            NSLog("ℹ️ No imported artist data found")
        }
    }
    
    private func checkForImportedSong() {
        if let data = SharedSongDataManager.retrieveSharedData() {
            NSLog("📥 Imported song data detected: %@", data.title)
            importedSongData = data
            showingSongCreation = true
        } else {
            NSLog("ℹ️ No imported song data found")
        }
    }

    private func checkForImportedYouTube() {
        if let data = SharedYouTubeDataManager.retrieveSharedData() {
            NSLog("📥 Imported YouTube data detected: %@", data.title)
            importedYouTubeData = data
        } else {
            NSLog("ℹ️ No imported YouTube data found")
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

// MARK: - Preview

#Preview {
    ContentView()
}

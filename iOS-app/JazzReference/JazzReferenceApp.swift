// Jazz Reference iOS App
// SwiftUI application for browsing jazz standards
// UPDATED FOR PHASE 5: Connected AuthenticationManager to RepertoireManager

import SwiftUI
import Combine

import GoogleSignIn


// MARK: - Main View

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
                                .font(.title2)
                                .fontWeight(.semibold)
                                .foregroundColor(JazzTheme.charcoal)
                        }
                        
                        // Email
                        if let email = authManager.currentUser?.email {
                            Text(email)
                                .font(.body)
                                .foregroundColor(JazzTheme.smokeGray)
                        }
                    }
                    .padding(.top, 32)
                    
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
            .navigationTitle("Settings")
            .toolbarBackground(JazzTheme.burgundy, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
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
    @StateObject private var repertoireManager = RepertoireManager()
    @StateObject private var authManager = AuthenticationManager()
    
    // Password reset state
    @State private var resetPasswordToken: String?

    // ADD THIS INITIALIZER
    init() {
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
                    else {
                        NSLog("❓ Unrecognized deep link format: \(url)")
                    }
                }
                .onAppear {
                    checkForImportedArtist()
                    checkForImportedSong()
                    
                    // PHASE 5: Connect RepertoireManager to AuthenticationManager
                    repertoireManager.setAuthManager(authManager)
                    print("📚 Connected RepertoireManager to AuthenticationManager")
                }
                .onChange(of: scenePhase) { oldPhase, newPhase in
                    if newPhase == .active {
                        checkForImportedArtist()
                        checkForImportedSong()
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
            NSLog("🔥 Imported artist data detected: %@", data.name)
            importedArtistData = data
            showingArtistCreation = true
        } else {
            NSLog("ℹ️ No imported artist data found")
        }
    }
    
    private func checkForImportedSong() {
        if let data = SharedSongDataManager.retrieveSharedData() {
            NSLog("🔥 Imported song data detected: %@", data.title)
            importedSongData = data
            showingSongCreation = true
        } else {
            NSLog("ℹ️ No imported song data found")
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

// MARK: - Preview

#Preview {
    ContentView()
}

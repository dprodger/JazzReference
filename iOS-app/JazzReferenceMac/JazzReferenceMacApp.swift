//
//  JazzReferenceMacApp.swift
//  JazzReferenceMac
//
//  macOS app entry point for Jazz Reference
//

import SwiftUI
#if canImport(GoogleSignIn)
import GoogleSignIn
#endif

@main
struct JazzReferenceMacApp: App {
    @StateObject private var authManager = AuthenticationManager()
    @StateObject private var repertoireManager = RepertoireManager()

    // Deep link state for password reset
    @State private var resetPasswordToken: String?
    @State private var showResetPasswordSheet = false

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(authManager)
                .environmentObject(repertoireManager)
                .onAppear {
                    // Connect RepertoireManager to AuthenticationManager
                    repertoireManager.setAuthManager(authManager)

                    #if canImport(GoogleSignIn)
                    // Restore Google Sign-In session if available
                    GIDSignIn.sharedInstance.restorePreviousSignIn { user, error in
                        if let error = error {
                            print("Google Sign-In restore error: \(error.localizedDescription)")
                        }
                    }
                    #endif
                }
                .onChange(of: authManager.isAuthenticated) { _, isAuthenticated in
                    Task {
                        await repertoireManager.loadRepertoires()
                    }
                }
                .onOpenURL { url in
                    handleDeepLink(url)
                }
                .sheet(isPresented: $showResetPasswordSheet) {
                    if let token = resetPasswordToken {
                        MacResetPasswordView(token: token)
                            .environmentObject(authManager)
                    }
                }
        }
        .windowStyle(.automatic)
        .defaultSize(width: 1200, height: 800)
        .commands {
            // Add menu commands
            CommandGroup(replacing: .newItem) { }

            CommandMenu("View") {
                Button("Songs") {
                    NotificationCenter.default.post(name: .navigateToSongs, object: nil)
                }
                .keyboardShortcut("1", modifiers: .command)

                Button("Artists") {
                    NotificationCenter.default.post(name: .navigateToArtists, object: nil)
                }
                .keyboardShortcut("2", modifiers: .command)

                Button("Recordings") {
                    NotificationCenter.default.post(name: .navigateToRecordings, object: nil)
                }
                .keyboardShortcut("3", modifiers: .command)
            }
        }

        #if os(macOS)
        Settings {
            SettingsView()
                .environmentObject(authManager)
        }
        #endif
    }

    // MARK: - Deep Link Handling

    private func handleDeepLink(_ url: URL) {
        print("Received deep link: \(url)")

        // Handle Google Sign-In callback
        #if canImport(GoogleSignIn)
        if GIDSignIn.sharedInstance.handle(url) {
            return
        }
        #endif

        // Handle password reset: jazzreference://auth/reset-password?token=xyz
        guard let components = URLComponents(url: url, resolvingAgainstBaseURL: false) else {
            return
        }

        if components.host == "auth" && components.path == "/reset-password" {
            if let token = components.queryItems?.first(where: { $0.name == "token" })?.value {
                resetPasswordToken = token
                showResetPasswordSheet = true
            }
        }
    }
}

// MARK: - Navigation Notifications

extension Notification.Name {
    static let navigateToSongs = Notification.Name("navigateToSongs")
    static let navigateToArtists = Notification.Name("navigateToArtists")
    static let navigateToRecordings = Notification.Name("navigateToRecordings")
}

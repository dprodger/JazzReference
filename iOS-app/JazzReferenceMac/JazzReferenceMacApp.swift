//
//  JazzReferenceMacApp.swift
//  JazzReferenceMac
//
//  macOS app entry point for Jazz Reference
//

import SwiftUI

@main
struct JazzReferenceMacApp: App {
    @StateObject private var authManager = AuthenticationManager()
    @StateObject private var repertoireManager = RepertoireManager()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(authManager)
                .environmentObject(repertoireManager)
                .onAppear {
                    // Connect RepertoireManager to AuthenticationManager
                    repertoireManager.setAuthManager(authManager)
                }
                .onChange(of: authManager.isAuthenticated) { _, isAuthenticated in
                    if isAuthenticated {
                        Task {
                            await repertoireManager.loadRepertoires()
                        }
                    } else {
                        Task {
                            await repertoireManager.loadRepertoires()
                        }
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
}

// MARK: - Navigation Notifications

extension Notification.Name {
    static let navigateToSongs = Notification.Name("navigateToSongs")
    static let navigateToArtists = Notification.Name("navigateToArtists")
    static let navigateToRecordings = Notification.Name("navigateToRecordings")
}

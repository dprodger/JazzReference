//
//  ContentView.swift
//  JazzReferenceMac
//
//  Main content view with sidebar navigation for macOS
//

import SwiftUI

enum NavigationItem: String, CaseIterable, Identifiable {
    case songs = "Songs"
    case artists = "Artists"
    case recordings = "Recordings"

    var id: String { rawValue }

    var icon: String {
        switch self {
        case .songs: return "music.note.list"
        case .artists: return "person.2.fill"
        case .recordings: return "opticaldisc"
        }
    }
}

struct ContentView: View {
    @State private var selectedItem: NavigationItem? = .songs
    @State private var columnVisibility: NavigationSplitViewVisibility = .all
    @EnvironmentObject var authManager: AuthenticationManager
    @EnvironmentObject var repertoireManager: RepertoireManager

    var body: some View {
        NavigationSplitView(columnVisibility: $columnVisibility) {
            // Sidebar
            List(NavigationItem.allCases, selection: $selectedItem) { item in
                NavigationLink(value: item) {
                    Label(item.rawValue, systemImage: item.icon)
                }
            }
            .listStyle(.sidebar)
            .navigationSplitViewColumnWidth(min: 180, ideal: 200)
            .toolbar {
                ToolbarItem(placement: .automatic) {
                    Button(action: toggleSidebar) {
                        Image(systemName: "sidebar.leading")
                    }
                }
            }

            // User status at bottom of sidebar
            Spacer()

            VStack(alignment: .leading, spacing: 8) {
                Divider()

                if authManager.isAuthenticated {
                    HStack {
                        Image(systemName: "person.circle.fill")
                            .foregroundColor(JazzTheme.burgundy)
                        VStack(alignment: .leading) {
                            Text(authManager.currentUser?.displayName ?? "User")
                                .font(.subheadline)
                                .fontWeight(.medium)
                            Text(authManager.currentUser?.email ?? "")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                    .padding(.horizontal)
                    .padding(.bottom, 8)
                } else {
                    Button("Sign In") {
                        // Show login sheet
                    }
                    .padding(.horizontal)
                    .padding(.bottom, 8)
                }
            }
        } detail: {
            // Main content area
            switch selectedItem {
            case .songs:
                SongsListView()
            case .artists:
                ArtistsListView()
            case .recordings:
                RecordingsListView()
            case .none:
                Text("Select an item from the sidebar")
                    .foregroundColor(.secondary)
            }
        }
        .onReceive(NotificationCenter.default.publisher(for: .navigateToSongs)) { _ in
            selectedItem = .songs
        }
        .onReceive(NotificationCenter.default.publisher(for: .navigateToArtists)) { _ in
            selectedItem = .artists
        }
        .onReceive(NotificationCenter.default.publisher(for: .navigateToRecordings)) { _ in
            selectedItem = .recordings
        }
    }

    private func toggleSidebar() {
        #if os(macOS)
        NSApp.keyWindow?.firstResponder?.tryToPerform(#selector(NSSplitViewController.toggleSidebar(_:)), with: nil)
        #endif
    }
}

// MARK: - Settings View (macOS Preferences)

struct SettingsView: View {
    @EnvironmentObject var authManager: AuthenticationManager

    var body: some View {
        TabView {
            AccountSettingsView()
                .tabItem {
                    Label("Account", systemImage: "person.circle")
                }

            GeneralSettingsView()
                .tabItem {
                    Label("General", systemImage: "gearshape")
                }
        }
        .frame(width: 450, height: 250)
    }
}

struct AccountSettingsView: View {
    @EnvironmentObject var authManager: AuthenticationManager

    var body: some View {
        Form {
            if authManager.isAuthenticated {
                Section {
                    LabeledContent("Name") {
                        Text(authManager.currentUser?.displayName ?? "—")
                    }
                    LabeledContent("Email") {
                        Text(authManager.currentUser?.email ?? "—")
                    }
                }

                Section {
                    Button("Sign Out") {
                        authManager.logout()
                    }
                    .foregroundColor(.red)
                }
            } else {
                Section {
                    Text("Sign in to access your repertoires and sync your data.")
                        .foregroundColor(.secondary)

                    // Login form would go here
                    Text("Login functionality coming soon")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
        }
        .formStyle(.grouped)
        .padding()
    }
}

struct GeneralSettingsView: View {
    var body: some View {
        Form {
            Section("Display") {
                Text("Display settings will appear here")
                    .foregroundColor(.secondary)
            }
        }
        .formStyle(.grouped)
        .padding()
    }
}

#Preview {
    ContentView()
        .environmentObject(AuthenticationManager())
        .environmentObject(RepertoireManager())
}

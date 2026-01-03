//
//  SettingsView.swift
//  JazzReferenceMac
//
//  Settings/Preferences window for Mac app
//

import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var authManager: AuthenticationManager
    @EnvironmentObject var favoritesManager: FavoritesManager
    @State private var showingOnboarding = false

    var body: some View {
        TabView {
            GeneralSettingsView(showingOnboarding: $showingOnboarding)
                .tabItem {
                    Label("General", systemImage: "gear")
                }

            AccountSettingsView()
                .environmentObject(authManager)
                .environmentObject(favoritesManager)
                .tabItem {
                    Label("Account", systemImage: "person.circle")
                }
        }
        .frame(width: 450, height: 300)
        .sheet(isPresented: $showingOnboarding) {
            MacOnboardingView(isPresented: $showingOnboarding)
        }
    }
}

// MARK: - General Settings

struct GeneralSettingsView: View {
    @Binding var showingOnboarding: Bool
    @AppStorage("hasCompletedOnboarding") private var hasCompletedOnboarding = false

    var body: some View {
        Form {
            Section {
                VStack(alignment: .leading, spacing: 16) {
                    Text("Tutorial")
                        .font(JazzTheme.headline())
                        .foregroundColor(JazzTheme.charcoal)

                    HStack {
                        VStack(alignment: .leading, spacing: 4) {
                            Text("View Tutorial")
                                .font(JazzTheme.body())
                            Text("Learn about Songs, Recordings, and Releases")
                                .font(JazzTheme.caption())
                                .foregroundColor(JazzTheme.smokeGray)
                        }

                        Spacer()

                        Button("View Tutorial") {
                            showingOnboarding = true
                        }
                    }
                }
                .padding(.vertical, 8)
            }

            Section {
                VStack(alignment: .leading, spacing: 16) {
                    Text("About")
                        .font(JazzTheme.headline())
                        .foregroundColor(JazzTheme.charcoal)

                    HStack {
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Approach Note")
                                .font(JazzTheme.body())
                            Text("A reference app for jazz standards")
                                .font(JazzTheme.caption())
                                .foregroundColor(JazzTheme.smokeGray)
                        }

                        Spacer()

                        Text("v1.0")
                            .font(JazzTheme.caption())
                            .foregroundColor(JazzTheme.smokeGray)
                    }
                }
                .padding(.vertical, 8)
            }
        }
        .formStyle(.grouped)
        .padding()
    }
}

// MARK: - Account Settings

struct AccountSettingsView: View {
    @EnvironmentObject var authManager: AuthenticationManager
    @EnvironmentObject var favoritesManager: FavoritesManager

    var body: some View {
        Form {
            if authManager.isAuthenticated {
                Section {
                    VStack(alignment: .leading, spacing: 16) {
                        Text("Signed In")
                            .font(JazzTheme.headline())
                            .foregroundColor(JazzTheme.charcoal)

                        HStack {
                            VStack(alignment: .leading, spacing: 4) {
                                if let email = authManager.userEmail {
                                    Text(email)
                                        .font(JazzTheme.body())
                                }
                                Text("Your repertoires and favorites sync across devices")
                                    .font(JazzTheme.caption())
                                    .foregroundColor(JazzTheme.smokeGray)
                            }

                            Spacer()

                            Button("Sign Out") {
                                authManager.logout()
                                favoritesManager.clearLocalFavorites()
                            }
                        }
                    }
                    .padding(.vertical, 8)
                }
            } else {
                Section {
                    VStack(alignment: .leading, spacing: 16) {
                        Text("Account")
                            .font(JazzTheme.headline())
                            .foregroundColor(JazzTheme.charcoal)

                        HStack {
                            VStack(alignment: .leading, spacing: 4) {
                                Text("Not signed in")
                                    .font(JazzTheme.body())
                                Text("Sign in to sync repertoires and favorites")
                                    .font(JazzTheme.caption())
                                    .foregroundColor(JazzTheme.smokeGray)
                            }

                            Spacer()

                            Text("Use the Sign In button in the main window")
                                .font(JazzTheme.caption())
                                .foregroundColor(JazzTheme.smokeGray)
                        }
                    }
                    .padding(.vertical, 8)
                }
            }
        }
        .formStyle(.grouped)
        .padding()
    }
}

#Preview {
    SettingsView()
        .environmentObject(AuthenticationManager())
        .environmentObject(FavoritesManager())
}

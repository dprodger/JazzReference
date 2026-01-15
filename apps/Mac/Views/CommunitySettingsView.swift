//
//  CommunitySettingsView.swift
//  JazzReferenceMac
//
//  Displays the user's community contributions in Settings
//

import SwiftUI

struct CommunitySettingsView: View {
    @EnvironmentObject var authManager: AuthenticationManager

    @State private var contributionStats: NetworkManager.UserContributionStats?
    @State private var isLoading = true
    @State private var errorMessage: String?

    private let networkManager = NetworkManager()

    var body: some View {
        Group {
            if authManager.isAuthenticated {
                authenticatedView
            } else {
                notAuthenticatedView
            }
        }
    }

    // MARK: - Authenticated View

    @ViewBuilder
    private var authenticatedView: some View {
        VStack(spacing: 0) {
            Form {
                Section {
                    // Header with user info
                    HStack(spacing: 12) {
                        Image(systemName: "person.3.fill")
                            .font(.system(size: 32))
                            .foregroundColor(JazzTheme.brass)

                        VStack(alignment: .leading, spacing: 4) {
                            Text("Your Contributions")
                                .font(JazzTheme.headline())
                                .foregroundColor(JazzTheme.charcoal)
                            Text("Thank you for helping improve the community!")
                                .font(JazzTheme.subheadline())
                                .foregroundColor(.secondary)
                        }

                        Spacer()
                    }
                    .padding(.vertical, 8)
                }

                Section("Contribution Statistics") {
                    if isLoading {
                        HStack {
                            Spacer()
                            ProgressView()
                                .scaleEffect(0.8)
                            Text("Loading...")
                                .foregroundColor(JazzTheme.smokeGray)
                            Spacer()
                        }
                        .padding(.vertical, 8)
                    } else if let stats = contributionStats {
                        contributionStatsView(stats: stats)
                    } else if let error = errorMessage {
                        HStack {
                            Image(systemName: "exclamationmark.triangle")
                                .foregroundColor(.orange)
                            Text(error)
                                .foregroundColor(JazzTheme.smokeGray)
                        }
                        .padding(.vertical, 8)
                    }
                }
            }
            .formStyle(.grouped)
        }
        .task {
            await loadContributionStats()
        }
    }

    @ViewBuilder
    private func contributionStatsView(stats: NetworkManager.UserContributionStats) -> some View {
        VStack(spacing: 0) {
            ContributionStatRow(
                icon: "music.note.list",
                iconColor: JazzTheme.burgundy,
                label: "Transcriptions",
                count: stats.transcriptions,
                description: "Solo transcription videos submitted"
            )

            Divider()
                .padding(.leading, 40)

            ContributionStatRow(
                icon: "play.rectangle.fill",
                iconColor: .green,
                label: "Backing Tracks",
                count: stats.backingTracks,
                description: "Practice backing tracks submitted"
            )

            Divider()
                .padding(.leading, 40)

            ContributionStatRow(
                icon: "metronome",
                iconColor: JazzTheme.brass,
                label: "Tempo Markings",
                count: stats.tempoMarkings,
                description: "Recording tempo contributions"
            )

            Divider()
                .padding(.leading, 40)

            ContributionStatRow(
                icon: "mic.fill",
                iconColor: .purple,
                label: "Vocal/Instrumental",
                count: stats.instrumentalVocal,
                description: "Recording type contributions"
            )

            Divider()
                .padding(.leading, 40)

            ContributionStatRow(
                icon: "music.note",
                iconColor: .blue,
                label: "Performance Keys",
                count: stats.keys,
                description: "Recording key contributions"
            )
        }

        // Total contributions summary
        if stats.totalContributions > 0 {
            HStack {
                Spacer()
                Text("Total: \(stats.totalContributions) contribution\(stats.totalContributions == 1 ? "" : "s")")
                    .font(JazzTheme.subheadline())
                    .foregroundColor(JazzTheme.brass)
                    .fontWeight(.medium)
            }
            .padding(.top, 8)
        }
    }

    // MARK: - Not Authenticated View

    @ViewBuilder
    private var notAuthenticatedView: some View {
        VStack(spacing: 24) {
            Spacer()

            Image(systemName: "person.3.fill")
                .font(.system(size: 60))
                .foregroundColor(JazzTheme.smokeGray.opacity(0.5))

            VStack(spacing: 8) {
                Text("Sign In to View Contributions")
                    .font(JazzTheme.headline())
                    .foregroundColor(JazzTheme.charcoal)

                Text("Track your contributions to the community including transcriptions, backing tracks, and recording metadata.")
                    .font(JazzTheme.body())
                    .foregroundColor(JazzTheme.smokeGray)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 40)
            }

            Text("Sign in using the Account tab")
                .font(JazzTheme.subheadline())
                .foregroundColor(JazzTheme.burgundy)

            Spacer()
        }
        .frame(maxWidth: .infinity)
    }

    // MARK: - Data Loading

    private func loadContributionStats() async {
        guard let token = authManager.getAccessToken() else {
            isLoading = false
            errorMessage = "Not authenticated"
            return
        }

        isLoading = true
        errorMessage = nil

        if let stats = await networkManager.fetchUserContributionStats(authToken: token) {
            contributionStats = stats
        } else {
            errorMessage = "Could not load contribution stats"
        }

        isLoading = false
    }
}

// MARK: - Contribution Stat Row

struct ContributionStatRow: View {
    let icon: String
    let iconColor: Color
    let label: String
    let count: Int
    let description: String

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .font(.system(size: 18))
                .foregroundColor(iconColor)
                .frame(width: 28)

            VStack(alignment: .leading, spacing: 2) {
                Text(label)
                    .font(JazzTheme.body())
                    .foregroundColor(JazzTheme.charcoal)

                Text(description)
                    .font(JazzTheme.caption())
                    .foregroundColor(JazzTheme.smokeGray)
            }

            Spacer()

            Text("\(count)")
                .font(JazzTheme.title2())
                .fontWeight(.semibold)
                .foregroundColor(count > 0 ? JazzTheme.charcoal : JazzTheme.smokeGray.opacity(0.5))
        }
        .padding(.vertical, 8)
    }
}

// MARK: - Previews

#Preview("Not Authenticated") {
    CommunitySettingsView()
        .environmentObject(AuthenticationManager())
        .frame(width: 500, height: 400)
}

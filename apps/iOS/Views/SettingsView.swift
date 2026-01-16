// SettingsView.swift
// User settings and profile view

import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var authManager: AuthenticationManager
    @EnvironmentObject var favoritesManager: FavoritesManager
    @AppStorage("preferredStreamingService") private var preferredStreamingService: String = StreamingService.spotify.rawValue

    @State private var contributionStats: NetworkManager.UserContributionStats?
    @State private var isLoadingContributions = false
    @State private var contributionsError: String?

    private let networkManager = NetworkManager()

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

                    // Favorites Section
                    VStack(alignment: .leading, spacing: 12) {
                        HStack {
                            Image(systemName: "heart.fill")
                                .foregroundColor(.red)
                            Text("Favorites")
                                .font(JazzTheme.headline())
                                .foregroundColor(JazzTheme.charcoal)
                        }
                        .padding(.horizontal)

                        if favoritesManager.isLoading {
                            HStack {
                                Spacer()
                                ProgressView()
                                    .tint(JazzTheme.brass)
                                Spacer()
                            }
                            .padding()
                        } else if favoritesManager.favoriteRecordings.isEmpty {
                            Text("No favorite recordings yet")
                                .font(JazzTheme.body())
                                .foregroundColor(JazzTheme.smokeGray)
                                .padding(.horizontal)
                        } else {
                            ScrollView(.horizontal, showsIndicators: false) {
                                HStack(spacing: 16) {
                                    ForEach(favoritesManager.favoriteRecordings, id: \.id) { recording in
                                        NavigationLink(destination: RecordingDetailView(recordingId: recording.id)) {
                                            VStack(spacing: 8) {
                                                // Album art
                                                if let artUrl = recording.bestAlbumArtSmall,
                                                   let url = URL(string: artUrl) {
                                                    CachedAsyncImage(
                                                        url: url,
                                                        content: { image in
                                                            image
                                                                .resizable()
                                                                .aspectRatio(contentMode: .fill)
                                                                .frame(width: 80, height: 80)
                                                                .cornerRadius(8)
                                                        },
                                                        placeholder: {
                                                            Rectangle()
                                                                .fill(JazzTheme.cardBackground)
                                                                .frame(width: 80, height: 80)
                                                                .cornerRadius(8)
                                                        }
                                                    )
                                                } else {
                                                    Rectangle()
                                                        .fill(JazzTheme.cardBackground)
                                                        .frame(width: 80, height: 80)
                                                        .cornerRadius(8)
                                                        .overlay(
                                                            Image(systemName: "opticaldisc")
                                                                .foregroundColor(JazzTheme.smokeGray)
                                                        )
                                                }

                                                // Song title
                                                Text(recording.songTitle ?? "Unknown")
                                                    .font(JazzTheme.caption())
                                                    .fontWeight(.medium)
                                                    .foregroundColor(JazzTheme.charcoal)
                                                    .lineLimit(2)
                                                    .multilineTextAlignment(.center)
                                            }
                                            .frame(width: 80)
                                        }
                                        .buttonStyle(.plain)
                                    }
                                }
                                .padding(.horizontal)
                            }
                        }

                        if favoritesManager.favoriteCount > 0 {
                            Text("\(favoritesManager.favoriteCount) \(favoritesManager.favoriteCount == 1 ? "recording" : "recordings")")
                                .font(JazzTheme.caption())
                                .foregroundColor(JazzTheme.smokeGray)
                                .padding(.horizontal)
                        }
                    }

                    Divider()
                        .padding(.horizontal)

                    // Contributions Section
                    VStack(alignment: .leading, spacing: 12) {
                        HStack {
                            Image(systemName: "person.3.fill")
                                .foregroundColor(JazzTheme.brass)
                            Text("Your Contributions")
                                .font(JazzTheme.headline())
                                .foregroundColor(JazzTheme.charcoal)
                        }
                        .padding(.horizontal)

                        if isLoadingContributions {
                            HStack {
                                Spacer()
                                ProgressView()
                                    .tint(JazzTheme.brass)
                                Spacer()
                            }
                            .padding()
                        } else if let stats = contributionStats {
                            VStack(spacing: 0) {
                                ContributionStatRow(
                                    icon: "music.note.list",
                                    iconColor: JazzTheme.burgundy,
                                    label: "Transcriptions",
                                    count: stats.transcriptions
                                )

                                Divider()
                                    .padding(.leading, 48)

                                ContributionStatRow(
                                    icon: "play.rectangle.fill",
                                    iconColor: .green,
                                    label: "Backing Tracks",
                                    count: stats.backingTracks
                                )

                                Divider()
                                    .padding(.leading, 48)

                                ContributionStatRow(
                                    icon: "metronome",
                                    iconColor: JazzTheme.brass,
                                    label: "Tempo Markings",
                                    count: stats.tempoMarkings
                                )

                                Divider()
                                    .padding(.leading, 48)

                                ContributionStatRow(
                                    icon: "mic.fill",
                                    iconColor: .purple,
                                    label: "Vocal/Instrumental",
                                    count: stats.instrumentalVocal
                                )

                                Divider()
                                    .padding(.leading, 48)

                                ContributionStatRow(
                                    icon: "music.note",
                                    iconColor: .blue,
                                    label: "Performance Keys",
                                    count: stats.keys
                                )
                            }
                            .padding(.horizontal)
                            .background(JazzTheme.cardBackground)
                            .cornerRadius(8)
                            .padding(.horizontal)

                            if stats.totalContributions > 0 {
                                Text("Total: \(stats.totalContributions) contribution\(stats.totalContributions == 1 ? "" : "s")")
                                    .font(JazzTheme.caption())
                                    .foregroundColor(JazzTheme.brass)
                                    .fontWeight(.medium)
                                    .padding(.horizontal)
                            }
                        } else if let error = contributionsError {
                            HStack {
                                Image(systemName: "exclamationmark.triangle")
                                    .foregroundColor(.orange)
                                Text(error)
                                    .font(JazzTheme.body())
                                    .foregroundColor(JazzTheme.smokeGray)
                            }
                            .padding(.horizontal)
                        }

                        Text("Thank you for helping improve the community!")
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
            .task {
                await loadContributionStats()
            }
        }
    }

    // MARK: - Data Loading

    private func loadContributionStats() async {
        guard let token = authManager.getAccessToken() else {
            contributionsError = "Not authenticated"
            return
        }

        isLoadingContributions = true
        contributionsError = nil

        if let stats = await networkManager.fetchUserContributionStats(authToken: token) {
            contributionStats = stats
        } else {
            contributionsError = "Could not load contributions"
        }

        isLoadingContributions = false
    }
}

// MARK: - Contribution Stat Row

private struct ContributionStatRow: View {
    let icon: String
    let iconColor: Color
    let label: String
    let count: Int

    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .font(.system(size: 16))
                .foregroundColor(iconColor)
                .frame(width: 24)

            Text(label)
                .font(JazzTheme.body())
                .foregroundColor(JazzTheme.charcoal)

            Spacer()

            Text("\(count)")
                .font(JazzTheme.title3())
                .fontWeight(.semibold)
                .foregroundColor(count > 0 ? JazzTheme.charcoal : JazzTheme.smokeGray.opacity(0.5))
        }
        .padding(.vertical, 12)
        .padding(.horizontal, 12)
    }
}

#Preview {
    SettingsView()
        .environmentObject(AuthenticationManager())
        .environmentObject(FavoritesManager())
}

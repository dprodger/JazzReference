// SettingsView.swift
// User settings and profile view

import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var authManager: AuthenticationManager
    @EnvironmentObject var favoritesManager: FavoritesManager
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

#Preview {
    SettingsView()
        .environmentObject(AuthenticationManager())
        .environmentObject(FavoritesManager())
}

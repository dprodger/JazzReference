//
//  RecordingRowView.swift
//  JazzReference
//
//  Updated with album artwork and authority badge support
//  UPDATED: Added optional artist name display for year-based sorting
//  UPDATED: Added back cover flip support
//

import SwiftUI

struct RecordingRowView: View {
    let recording: Recording
    var showArtistName: Bool = false

    @State private var showingBackCover = false

    // Extract lead artist from performers
    private var leadArtist: String {
        if let performers = recording.performers {
            // First try to find a performer with "leader" role
            if let leader = performers.first(where: { $0.role?.lowercased() == "leader" }) {
                return leader.name
            }
            // Fall back to first performer if no leader
            if let first = performers.first {
                return first.name
            }
        }
        return "Unknown Artist"
    }

    // Front cover URL
    private var frontCoverUrl: String? {
        recording.bestAlbumArtMedium ?? recording.bestAlbumArtSmall
    }

    // Back cover URL
    private var backCoverUrl: String? {
        recording.backCoverArtMedium ?? recording.backCoverArtSmall
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            // Album artwork with flip support
            ZStack(alignment: .topTrailing) {
                // Album art with card-flip animation
                ZStack {
                    // Front cover
                    if let frontUrl = frontCoverUrl {
                        AsyncImage(url: URL(string: frontUrl)) { phase in
                            switch phase {
                            case .empty:
                                ZStack {
                                    Color(.systemGray5)
                                    ProgressView()
                                        .tint(.secondary)
                                }
                                .frame(width: 150, height: 150)
                            case .success(let image):
                                image
                                    .resizable()
                                    .aspectRatio(contentMode: .fill)
                                    .frame(width: 150, height: 150)
                                    .clipped()
                            case .failure:
                                Image(systemName: "music.note")
                                    .font(.largeTitle)
                                    .foregroundColor(.secondary)
                                    .frame(width: 150, height: 150)
                                    .background(Color(.systemGray5))
                            @unknown default:
                                EmptyView()
                            }
                        }
                        .opacity(showingBackCover ? 0 : 1)
                    } else {
                        Image(systemName: "opticaldisc")
                            .font(.largeTitle)
                            .foregroundColor(.secondary)
                            .frame(width: 150, height: 150)
                            .background(Color(.systemGray5))
                            .opacity(showingBackCover ? 0 : 1)
                    }

                    // Back cover (pre-rotated so it appears correct after flip)
                    if let backUrl = backCoverUrl {
                        AsyncImage(url: URL(string: backUrl)) { phase in
                            switch phase {
                            case .empty:
                                ZStack {
                                    Color(.systemGray5)
                                    ProgressView()
                                        .tint(.secondary)
                                }
                                .frame(width: 150, height: 150)
                            case .success(let image):
                                image
                                    .resizable()
                                    .aspectRatio(contentMode: .fill)
                                    .frame(width: 150, height: 150)
                                    .clipped()
                            case .failure:
                                Image(systemName: "music.note")
                                    .font(.largeTitle)
                                    .foregroundColor(.secondary)
                                    .frame(width: 150, height: 150)
                                    .background(Color(.systemGray5))
                            @unknown default:
                                EmptyView()
                            }
                        }
                        .rotation3DEffect(.degrees(180), axis: (x: 0, y: 1, z: 0))
                        .opacity(showingBackCover ? 1 : 0)
                    }
                }
                .rotation3DEffect(
                    .degrees(showingBackCover ? 180 : 0),
                    axis: (x: 0, y: 1, z: 0)
                )

                // Overlay badges in top-right corner
                VStack(alignment: .trailing, spacing: 4) {
                    // Flip badge (shown when back cover available)
                    if recording.canFlipToBackCover {
                        Button(action: {
                            withAnimation(.easeInOut(duration: 0.4)) {
                                showingBackCover.toggle()
                            }
                        }) {
                            Image(systemName: showingBackCover ? "arrow.uturn.backward" : "arrow.trianglehead.2.clockwise.rotate.90")
                                .foregroundColor(.white)
                                .font(.system(size: 10, weight: .semibold))
                                .padding(6)
                                .background(Color.black.opacity(0.6))
                                .clipShape(Circle())
                        }
                        .buttonStyle(PlainButtonStyle())
                    }

                    // Canonical star badge
                    if recording.isCanonical == true {
                        Image(systemName: "star.fill")
                            .foregroundColor(.yellow)
                            .font(.caption)
                            .padding(6)
                            .background(Color.black.opacity(0.6))
                            .clipShape(Circle())
                    }

                    // Authority badge
                    if recording.hasAuthority, let badgeText = recording.authorityBadgeText {
                        CompactAuthorityBadge(text: badgeText, source: recording.primaryAuthoritySource)
                    }
                }
                .padding(6)
            }
            .cornerRadius(8)
            .frame(width: 150)

            // Artist name (shown when grouping by year)
            if showArtistName {
                Text(leadArtist)
                    .font(.subheadline)
                    .fontWeight(.semibold)
                    .foregroundColor(JazzTheme.brass)
                    .lineLimit(1)
                    .frame(width: 150, alignment: .leading)
            }

            // Album title
            Text(recording.albumTitle ?? "Unknown Album")
                .font(.subheadline)
                .fontWeight(.medium)
                .lineLimit(2)
                .frame(width: 150, alignment: .leading)

            // Year
            if let year = recording.recordingYear {
                Text(String(format: "%d", year))
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .frame(width: 150, alignment: .leading)
            }
        }
        .frame(width: 150)
    }
}

// MARK: - Compact Authority Badge for Recording Row

/// A smaller authority badge designed for the horizontal recording cards
struct CompactAuthorityBadge: View {
    let text: String
    let source: String?

    var body: some View {
        HStack(spacing: 3) {
            Image(systemName: "checkmark.seal.fill")
                .font(.system(size: 8))
            Text(text)
                .font(.system(size: 9, weight: .semibold))
        }
        .foregroundColor(.white)
        .padding(.horizontal, 6)
        .padding(.vertical, 3)
        .background(badgeColor)
        .cornerRadius(4)
    }

    private var badgeColor: Color {
        // Color code by source
        guard let source = source else { return JazzTheme.burgundy }

        switch source.lowercased() {
        case "jazzstandards.com":
            return Color(red: 0.2, green: 0.5, blue: 0.8) // Blue
        case "allmusic":
            return Color(red: 0.8, green: 0.3, blue: 0.3) // Red
        case "discogs":
            return Color(red: 0.4, green: 0.7, blue: 0.4) // Green
        default:
            return JazzTheme.burgundy
        }
    }
}

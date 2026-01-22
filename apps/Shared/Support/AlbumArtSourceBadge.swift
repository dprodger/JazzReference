//
//  AlbumArtSourceBadge.swift
//  JazzReference
//
//  Watermark badge overlay for album art showing the image source
//  with tap-to-view source details and attribution link.
//

import SwiftUI

/// A small badge overlay showing the source of album artwork
/// Tap to see source details and visit the source page
struct AlbumArtSourceBadge: View {
    let source: String?
    let sourceUrl: String?

    @State private var showingDetails = false

    private var displaySource: String {
        guard let source = source else { return "" }
        switch source.lowercased() {
        case "musicbrainz":
            return "Cover Art Archive"
        case "spotify":
            return "Spotify"
        case "apple":
            return "Apple Music"
        case "wikipedia":
            return "Wikipedia"
        case "amazon":
            return "Amazon"
        default:
            return source
        }
    }

    private var sourceIcon: String {
        guard let source = source else { return "photo" }
        switch source.lowercased() {
        case "musicbrainz":
            return "archivebox"  // CAA icon
        case "spotify":
            return "waveform"    // Music streaming icon
        case "apple":
            return "applelogo"
        case "wikipedia":
            return "book"
        case "amazon":
            return "cart"
        default:
            return "photo"
        }
    }

    var body: some View {
        if source != nil {
            Button {
                showingDetails = true
            } label: {
                HStack(spacing: 4) {
                    Image(systemName: sourceIcon)
                        .font(.system(size: 10, weight: .medium))
                    Text(displaySource)
                        .font(.system(size: 10, weight: .medium))
                }
                .foregroundColor(.white)
                .padding(.horizontal, 6)
                .padding(.vertical, 3)
                .background(
                    RoundedRectangle(cornerRadius: 4)
                        .fill(Color.black.opacity(0.65))
                        .shadow(color: .black.opacity(0.3), radius: 2, x: 0, y: 1)
                )
            }
            .buttonStyle(.plain)
            .sheet(isPresented: $showingDetails) {
                AlbumArtSourceSheet(source: displaySource, sourceUrl: sourceUrl)
            }
        }
    }
}

/// Detail sheet showing album art source information
private struct AlbumArtSourceSheet: View {
    let source: String
    let sourceUrl: String?
    @Environment(\.dismiss) var dismiss

    private var licenseInfo: String {
        switch source {
        case "Cover Art Archive":
            return "Images from the Cover Art Archive are typically available under various licenses including CC-BY and CC0. Check the source page for specific licensing."
        case "Spotify":
            return "Album artwork provided by Spotify. For promotional and identification purposes only."
        case "Apple Music":
            return "Album artwork provided by Apple Music. For promotional and identification purposes only."
        default:
            return "For promotional and identification purposes only."
        }
    }

    var body: some View {
        NavigationView {
            VStack(alignment: .leading, spacing: 20) {
                // Source name
                VStack(alignment: .leading, spacing: 4) {
                    Text("Source")
                        .font(JazzTheme.caption())
                        .foregroundColor(JazzTheme.smokeGray)
                    Text(source)
                        .font(JazzTheme.headline())
                        .foregroundColor(JazzTheme.charcoal)
                }

                // License info
                VStack(alignment: .leading, spacing: 4) {
                    Text("Usage")
                        .font(JazzTheme.caption())
                        .foregroundColor(JazzTheme.smokeGray)
                    Text(licenseInfo)
                        .font(JazzTheme.subheadline())
                        .foregroundColor(JazzTheme.charcoal)
                }

                // Source link
                if let urlString = sourceUrl, let url = URL(string: urlString) {
                    Link(destination: url) {
                        HStack {
                            Image(systemName: "arrow.up.right.square")
                            Text("View on \(source)")
                        }
                        .font(JazzTheme.subheadline())
                        .foregroundColor(JazzTheme.brass)
                    }
                    .padding(.top, 8)
                }

                Spacer()
            }
            .padding()
            .navigationTitle("Image Source")
            #if os(iOS)
            .navigationBarTitleDisplayMode(.inline)
            #endif
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                        .foregroundColor(JazzTheme.amber)
                }
            }
        }
        .presentationDetents([.medium])
    }
}

// MARK: - Convenience View Modifier

/// View modifier to add album art source badge to any image view
struct AlbumArtSourceBadgeModifier: ViewModifier {
    let source: String?
    let sourceUrl: String?
    let alignment: Alignment

    func body(content: Content) -> some View {
        content
            .overlay(alignment: alignment) {
                AlbumArtSourceBadge(source: source, sourceUrl: sourceUrl)
                    .padding(6)
            }
    }
}

extension View {
    /// Adds an album art source badge overlay to the view
    /// - Parameters:
    ///   - source: The source name (e.g., "Spotify", "MusicBrainz")
    ///   - sourceUrl: Optional URL to the source page
    ///   - alignment: Where to position the badge (default: bottomLeading)
    func albumArtSourceBadge(
        source: String?,
        sourceUrl: String? = nil,
        alignment: Alignment = .bottomLeading
    ) -> some View {
        modifier(AlbumArtSourceBadgeModifier(
            source: source,
            sourceUrl: sourceUrl,
            alignment: alignment
        ))
    }
}

// MARK: - Preview

#Preview("Badge on Image") {
    VStack(spacing: 20) {
        // Spotify source
        AsyncImage(url: URL(string: "https://picsum.photos/300")) { image in
            image.resizable().aspectRatio(contentMode: .fill)
        } placeholder: {
            Color.gray.opacity(0.3)
        }
        .frame(width: 200, height: 200)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .albumArtSourceBadge(source: "Spotify", sourceUrl: "https://open.spotify.com/album/example")

        // Cover Art Archive source
        AsyncImage(url: URL(string: "https://picsum.photos/301")) { image in
            image.resizable().aspectRatio(contentMode: .fill)
        } placeholder: {
            Color.gray.opacity(0.3)
        }
        .frame(width: 200, height: 200)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .albumArtSourceBadge(source: "MusicBrainz", sourceUrl: "https://coverartarchive.org/release/example")

        // Apple Music source
        AsyncImage(url: URL(string: "https://picsum.photos/302")) { image in
            image.resizable().aspectRatio(contentMode: .fill)
        } placeholder: {
            Color.gray.opacity(0.3)
        }
        .frame(width: 200, height: 200)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .albumArtSourceBadge(source: "Apple", sourceUrl: nil)
    }
    .padding()
}

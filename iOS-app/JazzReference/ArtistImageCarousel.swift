//
//  ArtistImageCarousel.swift
//  JazzReference
//
//  Simple horizontal scrolling image carousel with source watermarks
//

import SwiftUI

struct ArtistImageCarousel: View {
    let images: [ArtistImage]
    @State private var selectedImage: ArtistImage?
    
    private let carouselHeight: CGFloat = 280
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header removed as per requirements
            
            if images.isEmpty {
                Text("No images available")
                    .foregroundColor(JazzTheme.smokeGray)
                    .padding()
            } else {
                // Carousel with border wrapper
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 12) {
                        ForEach(images) { image in
                            ImageThumbnail(image: image)
                                .onTapGesture {
                                    selectedImage = image
                                }
                        }
                    }
                    .padding(.horizontal)
                    .padding(.vertical, 12)
                }
                .frame(height: carouselHeight + 24) // Account for vertical padding
                .background(
                    RoundedRectangle(cornerRadius: 16)
                        .strokeBorder(JazzTheme.smokeGray.opacity(0.3), lineWidth: 1.5)
                        .background(
                            RoundedRectangle(cornerRadius: 16)
                                .fill(Color.white.opacity(0.5))
                        )
                )
                .padding(.horizontal)
            }
        }
        .sheet(item: $selectedImage) { image in
            ImageDetailSheet(image: image)
        }
    }
}

// MARK: - Image Thumbnail

private struct ImageThumbnail: View {
    let image: ArtistImage
    @State private var uiImage: UIImage?
    @State private var isLoading = true
    
    private var cardWidth: CGFloat {
        guard let width = image.width, let height = image.height, height > 0 else {
            return 210 // Default width
        }
        let aspectRatio = CGFloat(width) / CGFloat(height)
        return 280 * aspectRatio
    }
    
    private var sourceName: String {
        switch image.source.lowercased() {
        case "wikimedia": return "Wikimedia Commons"
        case "musicbrainz": return "MusicBrainz"
        case "lastfm": return "Last.fm"
        case "spotify": return "Spotify"
        default: return image.source.capitalized
        }
    }
    
    var body: some View {
        ZStack(alignment: .bottomLeading) {
            // Main image
            Group {
                if let uiImage = uiImage {
                    Image(uiImage: uiImage)
                        .resizable()
                        .aspectRatio(contentMode: .fill)
                        .frame(width: cardWidth, height: 280)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                } else if isLoading {
                    RoundedRectangle(cornerRadius: 12)
                        .fill(Color.gray.opacity(0.2))
                        .frame(width: cardWidth, height: 280)
                        .overlay(ProgressView().tint(JazzTheme.amber))
                } else {
                    RoundedRectangle(cornerRadius: 12)
                        .fill(Color.gray.opacity(0.3))
                        .frame(width: cardWidth, height: 280)
                        .overlay(
                            Image(systemName: "photo")
                                .font(.largeTitle)
                                .foregroundColor(.gray)
                        )
                }
            }
            
            // Source watermark overlay
            if uiImage != nil {
                HStack(spacing: 4) {
                    Image(systemName: "photo.badge.checkmark")
                        .font(.caption2)
                    Text(sourceName)
                        .font(.caption2)
                        .fontWeight(.medium)
                }
                .foregroundColor(.white)
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(
                    RoundedRectangle(cornerRadius: 6)
                        .fill(Color.black.opacity(0.6))
                        .shadow(color: .black.opacity(0.3), radius: 2, x: 0, y: 1)
                )
                .padding(8)
            }
        }
        .frame(width: cardWidth, height: 280)
        .onAppear { loadImage() }
    }
    
    private func loadImage() {
        let imageUrl = image.thumbnailUrl ?? image.url
        guard let url = URL(string: imageUrl) else {
            isLoading = false
            return
        }
        
        URLSession.shared.dataTask(with: url) { data, _, _ in
            DispatchQueue.main.async {
                isLoading = false
                if let data = data, let loadedImage = UIImage(data: data) {
                    self.uiImage = loadedImage
                }
            }
        }.resume()
    }
}

// MARK: - Image Detail Sheet

private struct ImageDetailSheet: View {
    let image: ArtistImage
    @Environment(\.dismiss) var dismiss
    @State private var uiImage: UIImage?
    
    private var sourceName: String {
        switch image.source.lowercased() {
        case "wikimedia": return "Wikimedia Commons"
        case "musicbrainz": return "MusicBrainz"
        case "lastfm": return "Last.fm"
        case "spotify": return "Spotify"
        default: return image.source.capitalized
        }
    }
    
    var body: some View {
        NavigationView {
            ScrollView {
                VStack(spacing: 20) {
                    // Full image
                    if let uiImage = uiImage {
                        Image(uiImage: uiImage)
                            .resizable()
                            .aspectRatio(contentMode: .fit)
                            .cornerRadius(8)
                    } else {
                        ProgressView()
                            .frame(height: 300)
                            .tint(JazzTheme.amber)
                    }
                    
                    // Image info
                    VStack(alignment: .leading, spacing: 16) {
                        InfoRow(title: "Source", value: sourceName)
                        
                        if let license = image.licenseType {
                            InfoRow(title: "License", value: licenseName(license))
                        }
                        
                        if let attribution = image.attribution {
                            VStack(alignment: .leading, spacing: 4) {
                                Text("Attribution")
                                    .font(.caption)
                                    .foregroundColor(JazzTheme.smokeGray)
                                Text(cleanHTML(attribution))
                                    .font(.subheadline)
                                    .foregroundColor(JazzTheme.charcoal)
                            }
                        }
                        
                        if let width = image.width, let height = image.height {
                            InfoRow(title: "Dimensions", value: "\(width) × \(height) pixels")
                        }
                        
                        if let sourcePageUrl = image.sourcePageUrl,
                           let url = URL(string: sourcePageUrl) {
                            Link(destination: url) {
                                HStack {
                                    Text("View on \(sourceName)")
                                        .font(.subheadline)
                                    Image(systemName: "arrow.up.forward.square")
                                        .font(.caption)
                                }
                                .foregroundColor(JazzTheme.brass)
                            }
                        }
                    }
                    .padding()
                    .background(Color(.systemGray6))
                    .cornerRadius(12)
                    .padding(.horizontal)
                }
                .padding(.vertical)
            }
            .navigationTitle("Image Details")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") {
                        dismiss()
                    }
                    .foregroundColor(JazzTheme.brass)
                }
            }
        }
        .onAppear { loadFullImage() }
    }
    
    private func licenseName(_ license: String) -> String {
        switch license.lowercased() {
        case "cc-by-sa": return "Creative Commons Attribution-ShareAlike"
        case "cc-by": return "Creative Commons Attribution"
        case "cc0": return "CC0 (Public Domain)"
        case "public-domain", "pd": return "Public Domain"
        case "fair-use": return "Fair Use"
        default: return license
        }
    }
    
    private func cleanHTML(_ html: String) -> String {
        html.replacingOccurrences(of: "<[^>]+>", with: "", options: .regularExpression)
            .trimmingCharacters(in: .whitespacesAndNewlines)
    }
    
    private func loadFullImage() {
        guard let url = URL(string: image.url) else { return }
        
        URLSession.shared.dataTask(with: url) { data, _, _ in
            DispatchQueue.main.async {
                if let data = data, let loadedImage = UIImage(data: data) {
                    self.uiImage = loadedImage
                }
            }
        }.resume()
    }
}

// MARK: - Helper View

private struct InfoRow: View {
    let title: String
    let value: String
    
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(.caption)
                .foregroundColor(JazzTheme.smokeGray)
            Text(value)
                .font(.subheadline)
                .foregroundColor(JazzTheme.charcoal)
        }
    }
}


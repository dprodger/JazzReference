//
//  ArtistImageCarousel.swift
//  JazzReference
//
//  Simple horizontal scrolling image carousel
//  ADD THIS AS A NEW FILE to your Xcode project
//

import SwiftUI

struct ArtistImageCarousel: View {
    let images: [ArtistImage]
    @State private var selectedImage: ArtistImage?
    
    private let carouselHeight: CGFloat = 280
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Images")
                .font(.title2)
                .bold()
                .foregroundColor(JazzTheme.charcoal)
                .padding(.horizontal)
            
            if images.isEmpty {
                Text("No images available")
                    .foregroundColor(JazzTheme.smokeGray)
                    .padding()
            } else {
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
                }
                .frame(height: carouselHeight)
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
    
    var body: some View {
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
                        
                        // View source button
                        if let sourceUrl = image.sourcePageUrl, let url = URL(string: sourceUrl) {
                            Link(destination: url) {
                                HStack {
                                    Text("View on \(sourceName)")
                                        .foregroundColor(JazzTheme.charcoal)
                                    Spacer()
                                    Image(systemName: "arrow.up.right.square")
                                        .foregroundColor(JazzTheme.burgundy)
                                }
                                .padding()
                                .background(JazzTheme.amber.opacity(0.1))
                                .cornerRadius(8)
                            }
                        }
                    }
                    .padding()
                }
                .padding()
            }
            .background(JazzTheme.backgroundLight)
            .navigationTitle("Image Details")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") {
                        dismiss()
                    }
                    .foregroundColor(JazzTheme.burgundy)
                }
            }
        }
        .onAppear { loadFullImage() }
    }
    
    private var sourceName: String {
        switch image.source.lowercased() {
        case "wikipedia": return "Wikipedia"
        case "discogs": return "Discogs"
        case "musicbrainz": return "MusicBrainz"
        default: return image.source.capitalized
        }
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

//
//  RecordingDetailView.swift
//  JazzReference
//
//  Updated to show releases that contain this recording
//

import SwiftUI

// MARK: - Recording Detail View

struct RecordingDetailView: View {
    let recordingId: String
    @State private var recording: Recording?
    @State private var isLoading = true
    @State private var showAllReleases = false
    
    private let maxReleasesToShow = 5
    
    var body: some View {
        ScrollView {
            if isLoading {
                ProgressView("Loading...")
                    .padding()
            } else if let recording = recording {
                VStack(alignment: .leading, spacing: 20) {
                    // Album Information
                    albumInfoSection(recording)
                    
                    // Performers Section
                    if let performers = recording.performers, !performers.isEmpty {
                        performersSection(performers)
                    }
                    
                    // Releases Section (NEW)
                    if let releases = recording.releases, !releases.isEmpty {
                        releasesSection(releases)
                    }
                    
                    // Authority Recommendations
                    if let recommendations = recording.authorityRecommendations, !recommendations.isEmpty {
                        authoritySection(recommendations)
                    }
                    
                    // External Links
                    externalLinksSection(recording)
                    
                    // Notes
                    if let notes = recording.notes, !notes.isEmpty {
                        notesSection(notes)
                    }
                }
                .padding()
            } else {
                Text("Recording not found")
                    .foregroundColor(.secondary)
                    .padding()
            }
        }
        .navigationTitle(recording?.albumTitle ?? "Recording")
        .navigationBarTitleDisplayMode(.inline)
        .task {
            await loadRecording()
        }
    }
    
    // MARK: - Album Info Section
    
    @ViewBuilder
    private func albumInfoSection(_ recording: Recording) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .top, spacing: 16) {
                // Album Art
                if let artUrl = recording.bestAlbumArtMedium ?? recording.albumArtMedium,
                   let url = URL(string: artUrl) {
                    AsyncImage(url: url) { image in
                        image
                            .resizable()
                            .aspectRatio(contentMode: .fit)
                    } placeholder: {
                        Rectangle()
                            .fill(Color.gray.opacity(0.3))
                    }
                    .frame(width: 120, height: 120)
                    .cornerRadius(8)
                } else {
                    Rectangle()
                        .fill(Color.gray.opacity(0.3))
                        .frame(width: 120, height: 120)
                        .cornerRadius(8)
                        .overlay(
                            Image(systemName: "music.note")
                                .font(.largeTitle)
                                .foregroundColor(.gray)
                        )
                }
                
                VStack(alignment: .leading, spacing: 8) {
                    // Canonical badge
                    if recording.isCanonical == true {
                        HStack(spacing: 4) {
                            Image(systemName: "star.fill")
                                .foregroundColor(.yellow)
                                .font(.caption)
                            Text("Canonical Recording")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                    
                    // Album title
                    Text(recording.albumTitle ?? "Unknown Album")
                        .font(.title2)
                        .fontWeight(.bold)
                    
                    // Song title
                    if let songTitle = recording.songTitle {
                        Text(songTitle)
                            .font(.headline)
                            .foregroundColor(.secondary)
                    }
                    
                    // Year and label
                    HStack {
                        if let year = recording.recordingYear {
                            Text(String(year))
                        }
                        if let label = recording.label {
                            if recording.recordingYear != nil {
                                Text("•")
                            }
                            Text(label)
                        }
                    }
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                }
            }
        }
    }
    
    // MARK: - Performers Section
    
    @ViewBuilder
    private func performersSection(_ performers: [Performer]) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Personnel")
                .font(.headline)
            
            ForEach(performers) { performer in
                NavigationLink(destination: PerformerDetailView(performerId: performer.id)) {
                    HStack {
                        VStack(alignment: .leading, spacing: 2) {
                            HStack(spacing: 6) {
                                Text(performer.name)
                                    .fontWeight(performer.role == "leader" ? .semibold : .regular)
                                
                                if performer.role == "leader" {
                                    Image(systemName: "star.fill")
                                        .font(.caption2)
                                        .foregroundColor(.yellow)
                                }
                            }
                            
                            if let instrument = performer.instrument {
                                Text(instrument)
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                        }
                        
                        Spacer()
                        
                        Image(systemName: "chevron.right")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    .padding(.vertical, 4)
                }
                .buttonStyle(.plain)
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
    
    // MARK: - Releases Section (NEW)
    
    @ViewBuilder
    private func releasesSection(_ releases: [Release]) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Available On")
                    .font(.headline)
                
                Spacer()
                
                // Spotify count badge
                let spotifyCount = releases.filter { $0.hasSpotify }.count
                if spotifyCount > 0 {
                    HStack(spacing: 4) {
                        Image("spotify-icon")
                            .resizable()
                            .frame(width: 16, height: 16)
                        Text("\(spotifyCount)")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
            }
            
            let displayedReleases = showAllReleases ? releases : Array(releases.prefix(maxReleasesToShow))
            
            ForEach(displayedReleases) { release in
                releaseRow(release)
            }
            
            // Show more/less button
            if releases.count > maxReleasesToShow {
                Button {
                    withAnimation {
                        showAllReleases.toggle()
                    }
                } label: {
                    HStack {
                        Text(showAllReleases ? "Show Less" : "Show All \(releases.count) Releases")
                            .font(.subheadline)
                        Image(systemName: showAllReleases ? "chevron.up" : "chevron.down")
                            .font(.caption)
                    }
                    .foregroundColor(.accentColor)
                }
                .padding(.top, 4)
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
    
    @ViewBuilder
    private func releaseRow(_ release: Release) -> some View {
        HStack(alignment: .top, spacing: 12) {
            // Cover art or placeholder
            if let artUrl = release.coverArtSmall, let url = URL(string: artUrl) {
                AsyncImage(url: url) { image in
                    image
                        .resizable()
                        .aspectRatio(contentMode: .fill)
                } placeholder: {
                    Rectangle()
                        .fill(Color.gray.opacity(0.3))
                }
                .frame(width: 50, height: 50)
                .cornerRadius(4)
            } else {
                Rectangle()
                    .fill(Color.gray.opacity(0.2))
                    .frame(width: 50, height: 50)
                    .cornerRadius(4)
                    .overlay(
                        Image(systemName: "opticaldisc")
                            .foregroundColor(.gray)
                    )
            }
            
            VStack(alignment: .leading, spacing: 4) {
                // Release title
                Text(release.title)
                    .font(.subheadline)
                    .fontWeight(.medium)
                    .lineLimit(2)
                
                // Artist and year
                HStack(spacing: 4) {
                    if let artist = release.artistCredit {
                        Text(artist)
                            .lineLimit(1)
                    }
                    if release.releaseYear != nil && release.artistCredit != nil {
                        Text("•")
                    }
                    if let year = release.releaseYear {
                        Text(String(year))
                    }
                }
                .font(.caption)
                .foregroundColor(.secondary)
                
                // Track position
                if let trackPos = release.trackPositionDisplay {
                    Text(trackPos)
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }
                
                // Format badge
                if let format = release.formatName {
                    Text(format)
                        .font(.caption2)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(Color.gray.opacity(0.2))
                        .cornerRadius(4)
                }
            }
            
            Spacer()
            
            // Spotify button
            if let spotifyUrl = release.spotifyTrackUrl ?? release.spotifyAlbumUrl,
               let url = URL(string: spotifyUrl) {
                Link(destination: url) {
                    Image("spotify-icon")
                        .resizable()
                        .frame(width: 24, height: 24)
                }
            }
        }
        .padding(.vertical, 6)
    }
    
    // MARK: - Authority Section
    
    @ViewBuilder
    private func authoritySection(_ recommendations: [AuthorityRecommendation]) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Expert Recommendations")
                .font(.headline)
            
            ForEach(recommendations) { rec in
                HStack(alignment: .top, spacing: 8) {
                    Image(systemName: "checkmark.seal.fill")
                        .foregroundColor(.green)
                        .font(.subheadline)
                    
                    VStack(alignment: .leading, spacing: 4) {
                        if let source = rec.sourceName {
                            if let url = rec.sourceUrl, let linkUrl = URL(string: url) {
                                Link(source, destination: linkUrl)
                                    .font(.subheadline)
                                    .fontWeight(.medium)
                            } else {
                                Text(source)
                                    .font(.subheadline)
                                    .fontWeight(.medium)
                            }
                        }
                        
                        if let text = rec.recommendationText {
                            Text(text)
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                }
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
    
    // MARK: - External Links Section
    
    @ViewBuilder
    private func externalLinksSection(_ recording: Recording) -> some View {
        let hasLinks = recording.bestSpotifyUrl != nil ||
                       recording.youtubeUrl != nil ||
                       recording.appleMusicUrl != nil
        
        if hasLinks {
            VStack(alignment: .leading, spacing: 12) {
                Text("Listen")
                    .font(.headline)
                
                HStack(spacing: 16) {
                    if let spotifyUrl = recording.bestSpotifyUrl, let url = URL(string: spotifyUrl) {
                        Link(destination: url) {
                            HStack {
                                Image("spotify-icon")
                                    .resizable()
                                    .frame(width: 20, height: 20)
                                Text("Spotify")
                            }
                            .padding(.horizontal, 16)
                            .padding(.vertical, 10)
                            .background(Color.green)
                            .foregroundColor(.white)
                            .cornerRadius(20)
                        }
                    }
                    
                    if let youtubeUrl = recording.youtubeUrl, let url = URL(string: youtubeUrl) {
                        Link(destination: url) {
                            HStack {
                                Image(systemName: "play.rectangle.fill")
                                Text("YouTube")
                            }
                            .padding(.horizontal, 16)
                            .padding(.vertical, 10)
                            .background(Color.red)
                            .foregroundColor(.white)
                            .cornerRadius(20)
                        }
                    }
                    
                    if let appleMusicUrl = recording.appleMusicUrl, let url = URL(string: appleMusicUrl) {
                        Link(destination: url) {
                            HStack {
                                Image(systemName: "music.note")
                                Text("Apple Music")
                            }
                            .padding(.horizontal, 16)
                            .padding(.vertical, 10)
                            .background(Color.pink)
                            .foregroundColor(.white)
                            .cornerRadius(20)
                        }
                    }
                }
            }
            .padding()
            .background(Color(.systemGray6))
            .cornerRadius(12)
        }
    }
    
    // MARK: - Notes Section
    
    @ViewBuilder
    private func notesSection(_ notes: String) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Notes")
                .font(.headline)
            
            Text(notes)
                .font(.body)
                .foregroundColor(.secondary)
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
    
    // MARK: - Data Loading
    
    private func loadRecording() async {
        let networkManager = NetworkManager()
        recording = await networkManager.fetchRecordingDetail(id: recordingId)
        isLoading = false
    }
}

// MARK: - Preview

#if DEBUG
struct RecordingDetailView_Previews: PreviewProvider {
    static var previews: some View {
        NavigationStack {
            RecordingDetailView(recordingId: "preview-recording-1")
        }
    }
}
#endif

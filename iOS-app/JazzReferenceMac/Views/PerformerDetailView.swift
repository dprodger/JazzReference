//
//  PerformerDetailView.swift
//  JazzReferenceMac
//
//  macOS-specific performer/artist detail view
//

import SwiftUI

struct PerformerDetailView: View {
    let performerId: String
    @State private var performer: PerformerDetail?
    @State private var isLoading = true

    private let networkManager = NetworkManager()

    var body: some View {
        ScrollView {
            if isLoading {
                ThemedProgressView(message: "Loading...")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .padding(.top, 100)
            } else if let performer = performer {
                VStack(alignment: .leading, spacing: 24) {
                    // Header with image
                    performerHeader(performer)

                    Divider()

                    // Biography
                    if let bio = performer.biography, !bio.isEmpty {
                        biographySection(bio)
                    }

                    // Instruments
                    if let instruments = performer.instruments, !instruments.isEmpty {
                        instrumentsSection(instruments)
                    }

                    // External links
                    if let links = performer.externalLinks, !links.isEmpty {
                        externalLinksSection(links)
                    }

                    // Recordings
                    if let recordings = performer.recordings, !recordings.isEmpty {
                        recordingsSection(recordings)
                    }
                }
                .padding()
            } else {
                Text("Artist not found")
                    .foregroundColor(.secondary)
                    .padding(.top, 100)
            }
        }
        .background(JazzTheme.backgroundLight)
        .task {
            await loadPerformer()
        }
    }

    // MARK: - View Components

    @ViewBuilder
    private func performerHeader(_ performer: PerformerDetail) -> some View {
        HStack(alignment: .top, spacing: 24) {
            // Artist image
            if let image = performer.images?.first {
                AsyncImage(url: URL(string: image.thumbnailUrl ?? image.url)) { img in
                    img
                        .resizable()
                        .aspectRatio(contentMode: .fill)
                } placeholder: {
                    Rectangle()
                        .fill(JazzTheme.cardBackground)
                        .overlay {
                            Image(systemName: "person.fill")
                                .font(.system(size: 40))
                                .foregroundColor(JazzTheme.smokeGray)
                        }
                }
                .frame(width: 150, height: 150)
                .clipShape(RoundedRectangle(cornerRadius: 12))
            } else {
                Rectangle()
                    .fill(JazzTheme.cardBackground)
                    .overlay {
                        Image(systemName: "person.fill")
                            .font(.system(size: 40))
                            .foregroundColor(JazzTheme.smokeGray)
                    }
                    .frame(width: 150, height: 150)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
            }

            VStack(alignment: .leading, spacing: 8) {
                Text(performer.name)
                    .font(.largeTitle)
                    .fontWeight(.bold)
                    .foregroundColor(JazzTheme.charcoal)

                if let birthDate = performer.birthDate {
                    HStack(spacing: 4) {
                        Text(birthDate)
                        if let deathDate = performer.deathDate {
                            Text("–")
                            Text(deathDate)
                        }
                    }
                    .font(.subheadline)
                    .foregroundColor(JazzTheme.smokeGray)
                }

                // Primary instruments
                if let instruments = performer.instruments?.filter({ $0.isPrimary == true }) {
                    let instrumentNames = instruments.map { $0.name }.joined(separator: ", ")
                    if !instrumentNames.isEmpty {
                        Text(instrumentNames)
                            .font(.title3)
                            .foregroundColor(JazzTheme.brass)
                    }
                }
            }

            Spacer()
        }
    }

    @ViewBuilder
    private func biographySection(_ bio: String) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Biography")
                .font(.headline)
                .foregroundColor(JazzTheme.charcoal)

            Text(bio)
                .font(.body)
                .foregroundColor(JazzTheme.charcoal)
                .lineSpacing(4)
        }
    }

    @ViewBuilder
    private func instrumentsSection(_ instruments: [PerformerInstrument]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Instruments")
                .font(.headline)
                .foregroundColor(JazzTheme.charcoal)

            FlowLayout(spacing: 8) {
                ForEach(instruments, id: \.name) { instrument in
                    Text(instrument.name)
                        .font(.caption)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 6)
                        .background(instrument.isPrimary == true ? JazzTheme.burgundy : JazzTheme.cardBackground)
                        .foregroundColor(instrument.isPrimary == true ? .white : JazzTheme.charcoal)
                        .cornerRadius(16)
                }
            }
        }
    }

    @ViewBuilder
    private func externalLinksSection(_ links: [String: String]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("External Links")
                .font(.headline)
                .foregroundColor(JazzTheme.charcoal)

            ForEach(Array(links.keys.sorted()), id: \.self) { key in
                if let urlString = links[key], let url = URL(string: urlString) {
                    Link(destination: url) {
                        HStack {
                            Image(systemName: iconForLink(key))
                                .foregroundColor(JazzTheme.burgundy)
                                .frame(width: 24)
                            Text(displayNameForLink(key))
                                .foregroundColor(JazzTheme.charcoal)
                            Spacer()
                            Image(systemName: "arrow.up.right.square")
                                .foregroundColor(JazzTheme.smokeGray)
                                .font(.caption)
                        }
                        .padding(.vertical, 8)
                        .padding(.horizontal, 12)
                        .background(JazzTheme.cardBackground)
                        .cornerRadius(8)
                    }
                    .buttonStyle(.plain)
                }
            }
        }
    }

    @ViewBuilder
    private func recordingsSection(_ recordings: [PerformerRecording]) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Recordings (\(recordings.count.formatted()))")
                .font(.headline)
                .foregroundColor(JazzTheme.charcoal)

            ForEach(recordings) { recording in
                HStack {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(recording.songTitle)
                            .font(.headline)
                            .foregroundColor(JazzTheme.charcoal)

                        if let album = recording.albumTitle {
                            Text(album)
                                .font(.subheadline)
                                .foregroundColor(JazzTheme.smokeGray)
                        }

                        HStack(spacing: 8) {
                            if let year = recording.recordingYear {
                                Text("\(year)")
                                    .font(.caption)
                                    .foregroundColor(JazzTheme.smokeGray)
                            }

                            if let role = recording.role {
                                Text(role.capitalized)
                                    .font(.caption)
                                    .padding(.horizontal, 6)
                                    .padding(.vertical, 2)
                                    .background(role == "leader" ? JazzTheme.burgundy : JazzTheme.brass.opacity(0.3))
                                    .foregroundColor(role == "leader" ? .white : JazzTheme.charcoal)
                                    .cornerRadius(4)
                            }
                        }
                    }

                    Spacer()

                    if recording.isCanonical == true {
                        Image(systemName: "star.fill")
                            .foregroundColor(JazzTheme.gold)
                    }
                }
                .padding()
                .background(JazzTheme.cardBackground)
                .cornerRadius(8)
            }
        }
    }

    // MARK: - Helpers

    private func iconForLink(_ key: String) -> String {
        switch key.lowercased() {
        case "wikipedia": return "book.fill"
        case "allmusic": return "music.quarternote.3"
        case "discogs": return "opticaldisc"
        case "musicbrainz": return "waveform"
        default: return "link"
        }
    }

    private func displayNameForLink(_ key: String) -> String {
        switch key.lowercased() {
        case "wikipedia": return "Wikipedia"
        case "allmusic": return "AllMusic"
        case "discogs": return "Discogs"
        case "musicbrainz": return "MusicBrainz"
        default: return key.capitalized
        }
    }

    // MARK: - Data Loading

    private func loadPerformer() async {
        isLoading = true
        performer = await networkManager.fetchPerformerDetail(id: performerId)
        isLoading = false
    }
}

// MARK: - Flow Layout for Tags

struct FlowLayout: Layout {
    var spacing: CGFloat = 8

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let result = FlowResult(in: proposal.width ?? 0, subviews: subviews, spacing: spacing)
        return result.size
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let result = FlowResult(in: bounds.width, subviews: subviews, spacing: spacing)
        for (index, subview) in subviews.enumerated() {
            subview.place(at: CGPoint(x: bounds.minX + result.positions[index].x,
                                       y: bounds.minY + result.positions[index].y),
                         proposal: .unspecified)
        }
    }

    struct FlowResult {
        var size: CGSize = .zero
        var positions: [CGPoint] = []

        init(in maxWidth: CGFloat, subviews: Subviews, spacing: CGFloat) {
            var x: CGFloat = 0
            var y: CGFloat = 0
            var rowHeight: CGFloat = 0

            for subview in subviews {
                let size = subview.sizeThatFits(.unspecified)

                if x + size.width > maxWidth && x > 0 {
                    x = 0
                    y += rowHeight + spacing
                    rowHeight = 0
                }

                positions.append(CGPoint(x: x, y: y))
                rowHeight = max(rowHeight, size.height)
                x += size.width + spacing
            }

            self.size = CGSize(width: maxWidth, height: y + rowHeight)
        }
    }
}

#Preview {
    PerformerDetailView(performerId: "preview-id")
}

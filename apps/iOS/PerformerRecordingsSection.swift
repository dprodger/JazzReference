//
//  PerformerRecordingsSection.swift
//  JazzReference
//
//  Recordings section for PerformerDetailView that mirrors the RecordingsSection UI
//  Displays recordings with album art in horizontal scrolling rows, grouped by decade or song title
//

import SwiftUI

// MARK: - Performer Recordings Section
struct PerformerRecordingsSection: View {
    let recordings: [PerformerRecording]
    let performerName: String

    @Binding var sortOrder: PerformerRecordingSortOrder
    @Binding var selectedFilter: RecordingFilter

    var isReloading: Bool = false
    var onSortOrderChanged: ((PerformerRecordingSortOrder) -> Void)?

    @State private var isSectionExpanded: Bool = true
    @State private var searchText: String = ""

    // MARK: - Filtered Recordings
    private var filteredRecordings: [PerformerRecording] {
        var result = recordings

        // Apply role filter
        switch selectedFilter {
        case .all:
            break
        case .leader:
            result = result.filter { $0.role?.lowercased() == "leader" }
        case .sideman:
            result = result.filter { $0.role?.lowercased() == "sideman" }
        }

        // Apply search filter
        if !searchText.isEmpty {
            let query = searchText.lowercased()
            result = result.filter { recording in
                recording.songTitle.lowercased().contains(query) ||
                (recording.albumTitle?.lowercased().contains(query) ?? false)
            }
        }

        return result
    }

    // MARK: - Grouped Recordings
    private var groupedRecordings: [(groupKey: String, recordings: [PerformerRecording])] {
        switch sortOrder {
        case .year:
            return groupByDecade()
        case .name:
            return groupBySongLetter()
        }
    }

    private func groupByDecade() -> [(groupKey: String, recordings: [PerformerRecording])] {
        var decadeOrder: [String] = []
        var decades: [String: [PerformerRecording]] = [:]

        for recording in filteredRecordings {
            let decadeKey: String
            if let year = recording.recordingYear {
                let decade = (year / 10) * 10
                decadeKey = "\(decade)s"
            } else {
                decadeKey = "Unknown Year"
            }

            if decades[decadeKey] == nil {
                decadeOrder.append(decadeKey)
            }
            decades[decadeKey, default: []].append(recording)
        }

        return decadeOrder.compactMap { key in
            guard let recordings = decades[key] else { return nil }
            return (groupKey: key, recordings: recordings)
        }
    }

    private func groupBySongLetter() -> [(groupKey: String, recordings: [PerformerRecording])] {
        var letterOrder: [String] = []
        var letters: [String: [PerformerRecording]] = [:]

        for recording in filteredRecordings {
            let firstChar = recording.songTitle.prefix(1).uppercased()
            let letterKey = firstChar.first?.isLetter == true ? firstChar : "#"

            if letters[letterKey] == nil {
                letterOrder.append(letterKey)
            }
            letters[letterKey, default: []].append(recording)
        }

        // Sort letter order alphabetically
        letterOrder.sort()

        return letterOrder.compactMap { key in
            guard let recordings = letters[key] else { return nil }
            return (groupKey: key, recordings: recordings)
        }
    }

    // MARK: - Body
    var body: some View {
        HStack(spacing: 0) {
            Spacer().frame(width: 16)

            VStack(alignment: .leading, spacing: 0) {
                DisclosureGroup(
                    isExpanded: $isSectionExpanded,
                    content: {
                        VStack(alignment: .leading, spacing: 0) {
                            // Search and Filter Bar
                            filterBar
                                .padding(.vertical, 8)
                                .padding(.horizontal)

                            // Recordings List
                            LazyVStack(alignment: .leading, spacing: 12) {
                                if !filteredRecordings.isEmpty {
                                    ForEach(groupedRecordings, id: \.groupKey) { group in
                                        VStack(alignment: .leading, spacing: 8) {
                                            Text("\(group.groupKey) (\(group.recordings.count))")
                                                .font(JazzTheme.headline())
                                                .foregroundColor(JazzTheme.burgundy)
                                                .padding(.horizontal)
                                                .padding(.top, 8)

                                            ScrollView(.horizontal, showsIndicators: false) {
                                                LazyHStack(alignment: .top, spacing: 0) {
                                                    ForEach(Array(group.recordings.enumerated()), id: \.element.id) { index, recording in
                                                        HStack(alignment: .top, spacing: 0) {
                                                            if index > 0 {
                                                                Rectangle()
                                                                    .fill(JazzTheme.burgundy.opacity(0.4))
                                                                    .frame(width: 2, height: 150)
                                                                    .padding(.horizontal, 8)
                                                            }

                                                            NavigationLink(destination: RecordingDetailView(recordingId: recording.recordingId)) {
                                                                PerformerRecordingCardView(
                                                                    recording: recording,
                                                                    showRole: sortOrder == .year
                                                                )
                                                            }
                                                            .buttonStyle(.plain)
                                                        }
                                                    }
                                                }
                                                .padding(.horizontal)
                                            }
                                        }
                                    }
                                } else {
                                    VStack(spacing: 12) {
                                        Image(systemName: "music.note.slash")
                                            .font(.system(size: 48))
                                            .foregroundColor(JazzTheme.smokeGray.opacity(0.5))
                                        Text("No recordings match the current filters")
                                            .font(JazzTheme.subheadline())
                                            .foregroundColor(JazzTheme.smokeGray)
                                            .multilineTextAlignment(.center)
                                    }
                                    .frame(maxWidth: .infinity)
                                    .padding(.vertical, 40)
                                }
                            }
                            .padding(.top, 8)
                            .overlay(alignment: .top) {
                                if isReloading {
                                    HStack(spacing: 8) {
                                        ProgressView()
                                            .tint(JazzTheme.burgundy)
                                        Text("Reloading...")
                                            .font(JazzTheme.subheadline())
                                            .foregroundColor(JazzTheme.smokeGray)
                                    }
                                    .padding(.horizontal, 16)
                                    .padding(.vertical, 10)
                                    .background(.ultraThinMaterial)
                                    .cornerRadius(8)
                                    .shadow(color: .black.opacity(0.1), radius: 4, y: 2)
                                    .padding(.top, 40)
                                }
                            }
                            .opacity(isReloading ? 0.5 : 1.0)
                            .animation(.easeInOut(duration: 0.2), value: isReloading)
                        }
                    },
                    label: {
                        HStack(alignment: .center) {
                            Image(systemName: "music.note.list")
                                .foregroundColor(JazzTheme.burgundy)

                            Text("Recordings")
                                .font(JazzTheme.title2())
                                .bold()
                                .foregroundColor(JazzTheme.charcoal)

                            Text("(\(filteredRecordings.count))")
                                .font(JazzTheme.subheadline())
                                .foregroundColor(JazzTheme.smokeGray)

                            Spacer()

                            // Sort menu
                            Menu {
                                ForEach(PerformerRecordingSortOrder.allCases) { order in
                                    Button(action: {
                                        if sortOrder != order {
                                            sortOrder = order
                                            onSortOrderChanged?(order)
                                        }
                                    }) {
                                        HStack {
                                            Text(order.displayName)
                                            if sortOrder == order {
                                                Image(systemName: "checkmark")
                                            }
                                        }
                                    }
                                }
                            } label: {
                                HStack(spacing: 3) {
                                    Text(sortOrder.displayName)
                                        .font(JazzTheme.caption())
                                    Image(systemName: "chevron.down")
                                        .font(.caption2)
                                }
                                .foregroundColor(JazzTheme.burgundy)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 5)
                                .background(JazzTheme.burgundy.opacity(0.1))
                                .cornerRadius(6)
                            }
                        }
                        .padding(.vertical, 12)
                    }
                )
                .tint(JazzTheme.burgundy)
            }

            Spacer().frame(width: 16)
        }
        .background(JazzTheme.backgroundLight)
    }

    // MARK: - Filter Bar
    @ViewBuilder
    private var filterBar: some View {
        VStack(spacing: 12) {
            // Search Field
            HStack {
                Image(systemName: "magnifyingglass")
                    .foregroundColor(JazzTheme.smokeGray)
                TextField("Search recordings...", text: $searchText)
                    .textFieldStyle(.plain)
                if !searchText.isEmpty {
                    Button(action: { searchText = "" }) {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundColor(JazzTheme.smokeGray)
                    }
                }
            }
            .padding(10)
            .background(JazzTheme.cardBackground)
            .cornerRadius(8)
            .overlay(
                RoundedRectangle(cornerRadius: 8)
                    .stroke(JazzTheme.smokeGray.opacity(0.3), lineWidth: 1)
            )

            // Role Filter Picker
            Picker("Filter", selection: $selectedFilter) {
                ForEach(RecordingFilter.allCases, id: \.self) { filter in
                    Text(filter.rawValue).tag(filter)
                }
            }
            .pickerStyle(.segmented)
            .tint(JazzTheme.burgundy)
        }
    }
}

// MARK: - Performer Recording Card View (mirrors RecordingRowView)
struct PerformerRecordingCardView: View {
    let recording: PerformerRecording
    var showRole: Bool = false

    private var coverUrl: String? {
        recording.bestCoverArtMedium ?? recording.bestCoverArtSmall
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            // Album artwork
            ZStack(alignment: .topTrailing) {
                if let url = coverUrl {
                    CachedAsyncImage(
                        url: URL(string: url),
                        content: { image in
                            image
                                .resizable()
                                .aspectRatio(contentMode: .fill)
                                .frame(width: 150, height: 150)
                                .clipped()
                        },
                        placeholder: {
                            ZStack {
                                JazzTheme.cardBackground
                                ProgressView()
                                    .tint(JazzTheme.brass)
                            }
                            .frame(width: 150, height: 150)
                        }
                    )
                } else {
                    Image(systemName: "opticaldisc")
                        .font(JazzTheme.largeTitle())
                        .foregroundColor(JazzTheme.smokeGray)
                        .frame(width: 150, height: 150)
                        .background(JazzTheme.cardBackground)
                }

                // Badges
                VStack(alignment: .trailing, spacing: 4) {
                    if recording.isCanonical == true {
                        Image(systemName: "star.fill")
                            .foregroundColor(.yellow)
                            .font(JazzTheme.caption())
                            .padding(6)
                            .background(Color.black.opacity(0.6))
                            .clipShape(Circle())
                    }

                    if showRole, let role = recording.role {
                        Text(role.capitalized)
                            .font(.system(size: 9, weight: .semibold))
                            .foregroundColor(.white)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 3)
                            .background(role.lowercased() == "leader" ? JazzTheme.brass : JazzTheme.smokeGray)
                            .cornerRadius(4)
                    }
                }
                .padding(6)
            }
            .cornerRadius(8)
            .frame(width: 150)

            // Song title
            Text(recording.songTitle)
                .font(JazzTheme.subheadline())
                .fontWeight(.semibold)
                .foregroundColor(JazzTheme.brass)
                .lineLimit(1)
                .frame(width: 150, alignment: .leading)

            // Album title
            Text(recording.albumTitle ?? "Unknown Album")
                .font(JazzTheme.subheadline())
                .fontWeight(.medium)
                .foregroundColor(JazzTheme.charcoal)
                .lineLimit(2)
                .frame(width: 150, alignment: .leading)

            // Year
            if let year = recording.recordingYear {
                Text(String(format: "%d", year))
                    .font(JazzTheme.caption())
                    .foregroundColor(JazzTheme.smokeGray)
                    .frame(width: 150, alignment: .leading)
            }
        }
        .frame(width: 150)
    }
}

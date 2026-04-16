//
//  RecordingsSection.swift
//  Approach Note
//
//  Collapsible section displaying filtered recordings with filter chips + sheet pattern
//  UPDATED: Replaced nested disclosure groups with filter chips and bottom sheet
//  UPDATED: Sort options changed from Authority/Year/Canonical to Name/Year
//  UPDATED: Grouping changes based on sort order (by year or by artist name)
//

import SwiftUI

// Filter enums (SongRecordingFilter, VocalFilter, InstrumentFamily) are in Shared/Support/RecordingFilters.swift

// MARK: - Recordings Section
struct RecordingsSection: View {
    let recordings: [Recording]

    // Binding for sort order (passed from parent)
    @Binding var recordingSortOrder: RecordingSortOrder

    // Loading state for sort order changes
    var isReloading: Bool = false

    // Callback when sort order changes (for parent to reload data)
    var onSortOrderChanged: ((RecordingSortOrder) -> Void)?

    // Callback when community data changes (for parent to reload recordings)
    var onCommunityDataChanged: (() -> Void)?

    // Callback fired when a recording row appears. Forwarded to
    // RecordingRowView's `onVisible` so SongDetailViewModel can drive
    // the shell+hydrate pattern. Nil means "don't hydrate" — useful for
    // any callers that already pass fully-loaded recordings.
    var onRequestHydration: ((String) -> Void)?

    @State private var selectedFilter: SongRecordingFilter = .playable
    @State private var selectedVocalFilter: VocalFilter = .all
    @State private var selectedInstrument: InstrumentFamily? = nil
    @State private var showFilterSheet: Bool = false
    @State private var isSectionExpanded: Bool = true

    var body: some View {
        // HStack with explicit spacers ensures DisclosureGroup chevron is properly inset
        HStack(spacing: 0) {
            Spacer().frame(width: 16)

            VStack(alignment: .leading, spacing: 0) {
                DisclosureGroup(
                    isExpanded: $isSectionExpanded,
                    content: {
                        VStack(alignment: .leading, spacing: 0) {

                            // MARK: - FILTER CHIPS BAR
                            if hasActiveFilters || !availableInstruments.isEmpty {
                                filterChipsBar
                                    .padding(.vertical, 8)
                                    .padding(.horizontal, 4)
                                    .background(JazzTheme.cardBackground)
                                    .cornerRadius(8)
                                    .padding(.horizontal)
                            }

                            // Recordings List (lazy-loaded for performance)
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
                                                            // Divider before item (except first)
                                                            if index > 0 {
                                                                Rectangle()
                                                                    .fill(JazzTheme.burgundy.opacity(0.4))
                                                                    .frame(width: 2, height: 150)
                                                                    .padding(.horizontal, 8)
                                                            }

                                                            NavigationLink(destination: RecordingDetailView(
                                                                recordingId: recording.id,
                                                                onCommunityDataChanged: onCommunityDataChanged
                                                            )) {
                                                                RecordingRowView(
                                                                    recording: recording,
                                                                    showArtistName: recordingSortOrder == .year || group.groupKey == "More Recordings",
                                                                    onVisible: onRequestHydration
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
                                        Image(systemName: "music.note")
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

                            // Recording count in header
                            Text("(\(filteredRecordings.count))")
                                .font(JazzTheme.subheadline())
                                .foregroundColor(JazzTheme.smokeGray)

                            Spacer()

                            // Sort menu
                            Menu {
                                ForEach(RecordingSortOrder.allCases) { sortOrder in
                                    Button(action: {
                                        if recordingSortOrder != sortOrder {
                                            recordingSortOrder = sortOrder
                                            onSortOrderChanged?(sortOrder)
                                        }
                                    }) {
                                        HStack {
                                            Text(sortOrder.displayName)
                                            if recordingSortOrder == sortOrder {
                                                Image(systemName: "checkmark")
                                            }
                                        }
                                    }
                                }
                            } label: {
                                HStack(spacing: 3) {
                                    Text(recordingSortOrder.displayName)
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
        .sheet(isPresented: $showFilterSheet) {
            RecordingFilterSheet(
                selectedFilter: $selectedFilter,
                selectedVocalFilter: $selectedVocalFilter,
                selectedInstrument: $selectedInstrument,
                availableInstruments: availableInstruments
            )
        }
    }

    // MARK: - Filter Chips Bar

    @ViewBuilder
    private var filterChipsBar: some View {
        HStack(spacing: 8) {
            // Active filter chips for streaming service
            if selectedFilter != .all {
                FilterChip(
                    label: selectedFilter.displayName,
                    icon: selectedFilter.icon,
                    iconColor: selectedFilter.iconColor,
                    onRemove: { selectedFilter = .all }
                )
            }

            // Active filter chip for vocal/instrumental
            if selectedVocalFilter != .all {
                FilterChip(
                    label: selectedVocalFilter.displayName,
                    icon: selectedVocalFilter.icon,
                    iconColor: selectedVocalFilter.iconColor,
                    onRemove: { selectedVocalFilter = .all }
                )
            }

            if let instrument = selectedInstrument {
                FilterChip(
                    label: instrument.rawValue,
                    icon: nil,
                    onRemove: { selectedInstrument = nil }
                )
            }

            // Add/Edit Filter button
            Button(action: { showFilterSheet = true }) {
                HStack(spacing: 4) {
                    Image(systemName: hasActiveFilters ? "slider.horizontal.3" : "plus")
                        .font(.caption.weight(.medium))
                    Text(hasActiveFilters ? "Edit" : "Filter")
                        .font(JazzTheme.subheadline())
                }
                .foregroundColor(JazzTheme.burgundy)
                .padding(.horizontal, 10)
                .padding(.vertical, 5)
                .background(JazzTheme.burgundy.opacity(0.15))
                .cornerRadius(14)
            }
            .buttonStyle(.plain)

            Spacer()
        }
    }

    private var hasActiveFilters: Bool {
        selectedFilter != .all || selectedVocalFilter != .all || selectedInstrument != nil
    }

    // MARK: - Computed Properties
    // Filtering and grouping logic lives in Shared/Support/RecordingGrouping.swift
    // so iOS and Mac stay in sync. These wrappers let in-body call sites stay unchanged.

    private var availableInstruments: [InstrumentFamily] {
        RecordingGrouping.availableInstruments(in: recordings)
    }

    private var filteredRecordings: [Recording] {
        RecordingGrouping.filter(
            recordings,
            instrument: selectedInstrument,
            vocal: selectedVocalFilter,
            streaming: selectedFilter
        )
    }

    private var groupedRecordings: [(groupKey: String, recordings: [Recording])] {
        RecordingGrouping.grouped(filteredRecordings, sortOrder: recordingSortOrder)
    }
}

// MARK: - Filter Chip Component

struct FilterChip: View {
    let label: String
    let icon: String?
    var iconColor: Color? = nil
    var backgroundColor: Color? = nil
    let onRemove: () -> Void

    var body: some View {
        HStack(spacing: 4) {
            if let icon = icon {
                Image(systemName: icon)
                    .font(JazzTheme.caption())
                    .foregroundColor(iconColor ?? .white)
            }

            Text(label)
                .font(JazzTheme.subheadline())

            Button(action: onRemove) {
                Image(systemName: "xmark")
                    .font(.caption2.weight(.semibold))
            }
            .buttonStyle(.plain)
        }
        .foregroundColor(.white)
        .padding(.horizontal, 10)
        .padding(.vertical, 6)
        .background(backgroundColor ?? JazzTheme.brass)
        .cornerRadius(16)
    }
}

// MARK: - Previews

#Preview("Recordings Section") {
    struct PreviewWrapper: View {
        @State private var sortOrder: RecordingSortOrder = .year

        var body: some View {
            NavigationStack {
                ScrollView {
                    RecordingsSection(
                        recordings: [.preview1, .preview2, .previewMinimal],
                        recordingSortOrder: $sortOrder
                    )
                }
            }
        }
    }
    return PreviewWrapper()
}

#Preview("Filter Chips") {
    VStack(spacing: 12) {
        FilterChip(label: "Playable", icon: "play.circle", iconColor: JazzTheme.burgundy) {}
        FilterChip(label: "Spotify", icon: "music.note.list", iconColor: .green) {}
        FilterChip(label: "Piano", icon: nil) {}
    }
    .padding()
}

//
//  ArtistsListView.swift
//  JazzReferenceMac
//
//  macOS-specific artists list view with master-detail layout
//

import SwiftUI

struct ArtistsListView: View {
    @StateObject private var networkManager = NetworkManager()
    @State private var searchText = ""
    @State private var searchTask: Task<Void, Never>?
    @State private var selectedPerformerId: String?

    var body: some View {
        HSplitView {
            // Artist list (left pane)
            VStack(spacing: 0) {
                MacSearchBar(
                    text: $searchText,
                    placeholder: "Search artists...",
                    backgroundColor: JazzTheme.amber
                )

                List(selection: $selectedPerformerId) {
                    ForEach(groupedPerformers, id: \.0) { letter, performers in
                        Section(header:
                            HStack {
                                Text(letter)
                                    .font(JazzTheme.headline())
                                    .foregroundColor(.white)
                                Spacer()
                            }
                            .padding(.horizontal, 12)
                            .padding(.vertical, 6)
                            .frame(maxWidth: .infinity)
                            .background(
                                JazzTheme.amber
                                    .padding(.horizontal, -20)
                                    .padding(.vertical, -4)
                            )
                            .listRowInsets(EdgeInsets())
                        ) {
                            ForEach(performers) { performer in
                                ArtistRowView(performer: performer, isSelected: selectedPerformerId == performer.id)
                                    .tag(performer.id)
                                    .listRowBackground(
                                        selectedPerformerId == performer.id
                                            ? JazzTheme.burgundy
                                            : JazzTheme.backgroundLight
                                    )
                            }
                        }
                    }
                }
                .listStyle(.plain)
                .scrollContentBackground(.hidden)
                .background(JazzTheme.backgroundLight)
                .listSectionSeparator(.hidden)
            }
            .frame(minWidth: 200, idealWidth: 250, maxWidth: 300)
            .environment(\.colorScheme, .light)

            // Artist detail (right pane)
            if let performerId = selectedPerformerId {
                PerformerDetailView(performerId: performerId)
                    .frame(minWidth: 400)
            } else {
                VStack {
                    Image(systemName: "person.2")
                        .font(.system(size: 60))
                        .foregroundColor(JazzTheme.smokeGray.opacity(0.5))
                    Text("Select an artist")
                        .font(JazzTheme.title2())
                        .foregroundColor(JazzTheme.smokeGray)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(JazzTheme.backgroundLight)
            }
        }
        .onChange(of: searchText) { _, newValue in
            searchTask?.cancel()
            searchTask = Task {
                try? await Task.sleep(nanoseconds: 300_000_000)
                if !Task.isCancelled {
                    await networkManager.fetchPerformers(searchQuery: newValue)
                }
            }
        }
        .task {
            await networkManager.fetchPerformers()
        }
    }

    // MARK: - Helper Methods

    private var groupedPerformers: [(String, [Performer])] {
        let grouped = Dictionary(grouping: networkManager.performers) { performer in
            let firstChar = performer.name.prefix(1).uppercased()
            return firstChar.rangeOfCharacter(from: .letters) != nil ? firstChar : "#"
        }

        return grouped.sorted { lhs, rhs in
            if lhs.key == "#" { return false }
            if rhs.key == "#" { return true }
            return lhs.key < rhs.key
        }
    }
}

// MARK: - Artist Row View

struct ArtistRowView: View {
    let performer: Performer
    var isSelected: Bool = false

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(performer.name)
                .font(JazzTheme.headline())
                .foregroundStyle(isSelected ? Color.white : JazzTheme.charcoal)
            if let instrument = performer.instrument {
                Text(instrument)
                    .font(JazzTheme.subheadline())
                    .foregroundStyle(isSelected ? Color.white.opacity(0.85) : JazzTheme.smokeGray)
            }
        }
        .padding(.vertical, 4)
        .padding(.horizontal, 8)
    }
}

#Preview {
    ArtistsListView()
}

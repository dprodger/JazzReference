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
                List(selection: $selectedPerformerId) {
                    ForEach(groupedPerformers, id: \.0) { letter, performers in
                        Section(header: Text(letter).font(.headline).foregroundColor(JazzTheme.burgundy)) {
                            ForEach(performers) { performer in
                                ArtistRowView(performer: performer)
                                    .tag(performer.id)
                            }
                        }
                    }
                }
                .listStyle(.inset(alternatesRowBackgrounds: true))
            }
            .frame(minWidth: 300, idealWidth: 350)

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
                        .font(.title2)
                        .foregroundColor(JazzTheme.smokeGray)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(JazzTheme.backgroundLight)
            }
        }
        .searchable(text: $searchText, prompt: "Search artists")
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
        .navigationTitle("Artists (\(networkManager.performers.count.formatted()))")
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

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(performer.name)
                .font(.headline)
                .foregroundColor(JazzTheme.charcoal)
            if let instrument = performer.instrument {
                Text(instrument)
                    .font(.subheadline)
                    .foregroundColor(JazzTheme.smokeGray)
            }
        }
        .padding(.vertical, 4)
    }
}

#Preview {
    ArtistsListView()
}

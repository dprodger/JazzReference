//
//  ArtistListView.swift
//  JazzReference
//
//  Updated with JazzTheme color palette
//

import SwiftUI

struct ArtistsListView: View {
    @StateObject private var networkManager = NetworkManager()
    @State private var searchText = ""
    @State private var searchTask: Task<Void, Never>?
    
    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                if networkManager.isLoading {
                    VStack {
                        Spacer()
                        ProgressView("Loading artists...")
                            .tint(JazzTheme.amber)
                        Spacer()
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .background(JazzTheme.backgroundLight)
                } else if let error = networkManager.errorMessage {
                    VStack(spacing: 16) {
                        Image(systemName: "exclamationmark.triangle")
                            .font(.system(size: 50))
                            .foregroundColor(JazzTheme.amber)
                        Text("Error")
                            .font(.headline)
                            .foregroundColor(JazzTheme.charcoal)
                        Text(error)
                            .font(.subheadline)
                            .foregroundColor(JazzTheme.smokeGray)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal)
                        Button("Retry") {
                            Task {
                                await networkManager.fetchPerformers()
                            }
                        }
                        .buttonStyle(.borderedProminent)
                        .tint(JazzTheme.amber)
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .background(JazzTheme.backgroundLight)
                } else {
                    List(networkManager.performers) { performer in
                        NavigationLink(destination: PerformerDetailView(performerId: performer.id)) {
                            VStack(alignment: .leading, spacing: 4) {
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
                        .listRowBackground(JazzTheme.cardBackground)
                    }
                    .listStyle(.insetGrouped)
                    .scrollContentBackground(.hidden)
                    .background(JazzTheme.backgroundLight)
                }
            }
            .background(JazzTheme.backgroundLight)
            .navigationTitle("Artists")
            .toolbarBackground(JazzTheme.amber, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .searchable(text: $searchText, prompt: "Search artists")
            .onChange(of: searchText) { oldValue, newValue in
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
        .tint(JazzTheme.amber)
    }
}

#Preview {
    ArtistsListView()
}

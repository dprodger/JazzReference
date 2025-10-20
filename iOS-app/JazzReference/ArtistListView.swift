//
//  ArtistListView.swift
//  JazzReference
//
//  Created by Dave Rodger on 10/19/25.
//

import SwiftUI

struct ArtistsListView: View {
    @StateObject private var networkManager = NetworkManager()
    @State private var searchText = ""
    @State private var searchTask: Task<Void, Never>?
    
    var body: some View {
        NavigationStack {
            VStack {
                if networkManager.isLoading {
                    ProgressView("Loading artists...")
                        .padding()
                } else if let error = networkManager.errorMessage {
                    VStack(spacing: 16) {
                        Image(systemName: "exclamationmark.triangle")
                            .font(.system(size: 50))
                            .foregroundColor(.orange)
                        Text("Error")
                            .font(.headline)
                        Text(error)
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal)
                        Button("Retry") {
                            Task {
                                await networkManager.fetchPerformers()
                            }
                        }
                        .buttonStyle(.borderedProminent)
                    }
                    .padding()
                } else {
                    List(networkManager.performers) { performer in
                        NavigationLink(destination: PerformerDetailView(performerId: performer.id)) {
                            VStack(alignment: .leading, spacing: 4) {
                                Text(performer.name)
                                    .font(.headline)
                                
                                if let instrument = performer.instrument {
                                    Text(instrument)
                                        .font(.subheadline)
                                        .foregroundColor(.secondary)
                                }
                            }
                            .padding(.vertical, 4)
                        }
                    }
                    .listStyle(.insetGrouped)
                }
            }
            .navigationTitle("Artists")
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
    }
}

#Preview {
    ArtistsListView()
}

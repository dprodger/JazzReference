//
//  AddToRepertoireSheet.swift
//  JazzReference
//
//  Created by Dave Rodger on 11/12/25.
//

import SwiftUI

struct AddToRepertoireSheet: View {
    let songId: String
    let songTitle: String
    @ObservedObject var repertoireManager: RepertoireManager
    @Binding var isPresented: Bool
    let onSuccess: (String) -> Void
    let onError: (String) -> Void
    
    @State private var isAdding = false
    @State private var isLoadingRepertoires = false
    @State private var networkManager = NetworkManager()
    
    var body: some View {
        NavigationStack {
            Group {
                if isLoadingRepertoires {
                    // Loading state
                    VStack(spacing: 16) {
                        ProgressView()
                            .tint(JazzTheme.burgundy)
                        Text("Loading repertoires...")
                            .foregroundColor(JazzTheme.smokeGray)
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else if repertoireManager.addableRepertoires.isEmpty {
                    // Empty state - no repertoires exist
                    VStack(spacing: 20) {
                        Image(systemName: "music.note.list")
                            .font(.system(size: 60))
                            .foregroundColor(JazzTheme.smokeGray.opacity(0.5))
                        
                        Text("No Repertoires Yet")
                            .font(.title2)
                            .fontWeight(.semibold)
                            .foregroundColor(JazzTheme.charcoal)
                        
                        Text("Create a repertoire first to start organizing your songs.")
                            .font(.subheadline)
                            .foregroundColor(JazzTheme.smokeGray)
                            .multilineTextAlignment(.center)
                            .padding(.horizontal, 40)
                        
                        // TODO: Add "Create Repertoire" button when that feature is implemented
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .background(JazzTheme.backgroundLight)
                } else {
                    // Normal state - show repertoires
                    repertoireList
                }
            }
            .navigationTitle("Add \"\(songTitle)\"")
            .navigationBarTitleDisplayMode(.inline)
            .toolbarBackground(JazzTheme.burgundy, for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Cancel") {
                        isPresented = false
                    }
                    .foregroundColor(.white)
                    .disabled(isAdding)
                }
            }
            .overlay {
                if isAdding {
                    ZStack {
                        Color.black.opacity(0.3)
                            .ignoresSafeArea()
                        
                        VStack(spacing: 16) {
                            ProgressView()
                                .tint(.white)
                                .scaleEffect(1.5)
                            Text("Adding to repertoire...")
                                .foregroundColor(.white)
                                .font(.headline)
                        }
                        .padding(30)
                        .background(JazzTheme.charcoal)
                        .cornerRadius(16)
                    }
                }
            }
            .task {
                // Ensure repertoires are loaded when sheet appears
                if repertoireManager.repertoires.isEmpty ||
                   repertoireManager.addableRepertoires.isEmpty {
                    isLoadingRepertoires = true
                    await repertoireManager.loadRepertoires()
                    isLoadingRepertoires = false
                    
                    // Debug logging
                    print("🎵 Loaded \(repertoireManager.repertoires.count) total repertoires")
                    print("🎵 Addable repertoires: \(repertoireManager.addableRepertoires.count)")
                    for rep in repertoireManager.addableRepertoires {
                        print("   - \(rep.name) (ID: \(rep.id))")
                    }
                }
            }
        }
    }
    
    private var repertoireList: some View {
        List {
            // Quick add to last used (if available)
            if let lastUsed = repertoireManager.lastUsedRepertoire {
                Section {
                    Button(action: {
                        addToRepertoire(lastUsed)
                    }) {
                        HStack {
                            VStack(alignment: .leading, spacing: 4) {
                                Text("Add to \(lastUsed.name)")
                                    .font(.headline)
                                    .foregroundColor(JazzTheme.charcoal)
                                Text("Last used")
                                    .font(.caption)
                                    .foregroundColor(JazzTheme.smokeGray)
                            }
                            Spacer()
                            Image(systemName: "arrow.right.circle.fill")
                                .foregroundColor(JazzTheme.amber)
                                .font(.title2)
                        }
                    }
                    .disabled(isAdding)
                    .listRowBackground(JazzTheme.amber.opacity(0.1))
                } header: {
                    Text("Quick Add")
                }
            }
            
            // All available repertoires
            Section {
                ForEach(repertoireManager.addableRepertoires) { repertoire in
                    Button(action: {
                        addToRepertoire(repertoire)
                    }) {
                        HStack {
                            VStack(alignment: .leading, spacing: 4) {
                                Text(repertoire.name)
                                    .font(.headline)
                                    .foregroundColor(JazzTheme.charcoal)
                                
                                if let description = repertoire.description {
                                    Text(description)
                                        .font(.subheadline)
                                        .foregroundColor(JazzTheme.smokeGray)
                                        .lineLimit(2)
                                }
                                
                                Text("\(repertoire.songCount) songs")
                                    .font(.caption)
                                    .foregroundColor(JazzTheme.burgundy)
                            }
                            Spacer()
                        }
                    }
                    .disabled(isAdding)
                    .listRowBackground(JazzTheme.cardBackground)
                }
            } header: {
                Text("All Repertoires")
            }
        }
        .listStyle(.insetGrouped)
        .scrollContentBackground(.hidden)
        .background(JazzTheme.backgroundLight)
    }
    
    private func addToRepertoire(_ repertoire: Repertoire) {
        isAdding = true
        
        Task {
            let result = await networkManager.addSongToRepertoire(
                songId: songId,
                repertoireId: repertoire.id
            )
            
            await MainActor.run {
                isAdding = false
                
                switch result {
                case .success(let message):
                    // Update last used repertoire
                    repertoireManager.setLastUsedRepertoire(repertoire)
                    
                    isPresented = false
                    onSuccess("Added \"\(songTitle)\" to \(repertoire.name)")
                    
                case .failure(let error):
                    isPresented = false
                    let errorMessage = (error as NSError).localizedDescription
                    onError(errorMessage)
                }
            }
        }
    }
}

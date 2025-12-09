//
//  AddToRepertoireSheet.swift
//  JazzReference
//
//  Created by Dave Rodger on 11/12/25.
//  UPDATED FOR PHASE 5: Added authentication check
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
    
    var body: some View {
        NavigationStack {
            Group {
                // Check authentication first
                if !repertoireManager.isAuthenticated {
                    authRequiredView
                } else if isLoadingRepertoires {
                    loadingView
                } else if repertoireManager.addableRepertoires.isEmpty {
                    emptyRepertoiresView
                } else {
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
                                .font(JazzTheme.headline())
                        }
                        .padding(30)
                        .background(JazzTheme.charcoal)
                        .cornerRadius(16)
                    }
                }
            }
            .task {
                // Only load repertoires if authenticated
                if repertoireManager.isAuthenticated &&
                   (repertoireManager.repertoires.isEmpty ||
                    repertoireManager.addableRepertoires.isEmpty) {
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
    
    // MARK: - Auth Required View
    
    private var authRequiredView: some View {
        VStack(spacing: 24) {
            Image(systemName: "lock.fill")
                .font(.system(size: 60))
                .foregroundColor(JazzTheme.burgundy.opacity(0.6))
            
            Text("Sign In Required")
                .font(JazzTheme.title2())
                .fontWeight(.semibold)
                .foregroundColor(JazzTheme.charcoal)
            
            Text("You need to be signed in to add songs to repertoires")
                .font(JazzTheme.body())
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 32)
            
            Button(action: {
                isPresented = false
            }) {
                Text("Close")
                    .fontWeight(.semibold)
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(JazzTheme.burgundy)
                    .foregroundColor(.white)
                    .cornerRadius(10)
            }
            .padding(.horizontal, 32)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(JazzTheme.backgroundLight)
    }
    
    // MARK: - Loading View
    
    private var loadingView: some View {
        VStack(spacing: 16) {
            ProgressView()
                .tint(JazzTheme.burgundy)
            Text("Loading repertoires...")
                .foregroundColor(JazzTheme.smokeGray)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(JazzTheme.backgroundLight)
    }
    
    // MARK: - Empty Repertoires View
    
    private var emptyRepertoiresView: some View {
        VStack(spacing: 20) {
            Image(systemName: "music.note.list")
                .font(.system(size: 60))
                .foregroundColor(JazzTheme.smokeGray.opacity(0.5))
            
            Text("No Repertoires Yet")
                .font(JazzTheme.title2())
                .fontWeight(.semibold)
                .foregroundColor(JazzTheme.charcoal)
            
            Text("Create a repertoire first to start organizing your songs.")
                .font(JazzTheme.subheadline())
                .foregroundColor(JazzTheme.smokeGray)
                .multilineTextAlignment(.center)
                .padding(.horizontal, 40)
            
            // TODO: Add "Create Repertoire" button when that feature is implemented
            Button(action: {
                isPresented = false
            }) {
                Text("Close")
                    .fontWeight(.semibold)
                    .padding(.horizontal, 24)
                    .padding(.vertical, 12)
                    .background(JazzTheme.burgundy)
                    .foregroundColor(.white)
                    .cornerRadius(10)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(JazzTheme.backgroundLight)
    }
    
    // MARK: - Repertoire List
    
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
                                    .font(JazzTheme.headline())
                                    .foregroundColor(JazzTheme.charcoal)
                                Text("Last used")
                                    .font(JazzTheme.caption())
                                    .foregroundColor(JazzTheme.smokeGray)
                            }
                            Spacer()
                            Image(systemName: "arrow.right.circle.fill")
                                .foregroundColor(JazzTheme.amber)
                                .font(JazzTheme.title2())
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
                                    .font(JazzTheme.headline())
                                    .foregroundColor(JazzTheme.charcoal)
                                
                                if let description = repertoire.description {
                                    Text(description)
                                        .font(JazzTheme.subheadline())
                                        .foregroundColor(JazzTheme.smokeGray)
                                        .lineLimit(2)
                                }
                                
                                Text("\(repertoire.songCount) songs")
                                    .font(JazzTheme.caption())
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
    
    // MARK: - Add to Repertoire Action
    
    private func addToRepertoire(_ repertoire: Repertoire) {
        isAdding = true
        
        Task {
            let success = await repertoireManager.addSongToRepertoire(
                songId: songId,
                repertoireId: repertoire.id
            )
            
            await MainActor.run {
                isAdding = false
                
                if success {
                    // Update last used repertoire
                    repertoireManager.setLastUsedRepertoire(repertoire)
                    
                    isPresented = false
                    onSuccess("Added \"\(songTitle)\" to \(repertoire.name)")
                } else {
                    isPresented = false
                    let errorMessage = repertoireManager.errorMessage ?? "Failed to add song"
                    onError(errorMessage)
                }
            }
        }
    }
}

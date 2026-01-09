//
//  MacAddToRepertoireSheet.swift
//  JazzReferenceMac
//
//  Sheet for adding songs to repertoires on macOS
//

import SwiftUI

struct MacAddToRepertoireSheet: View {
    let songId: String
    let songTitle: String
    @ObservedObject var repertoireManager: RepertoireManager
    @Environment(\.dismiss) var dismiss

    var onSuccess: ((String) -> Void)?
    var onError: ((String) -> Void)?

    @State private var isAdding = false
    @State private var isLoadingRepertoires = false
    @State private var showCreateRepertoire = false

    var body: some View {
        VStack(spacing: 0) {
            // Header
            headerView

            Divider()

            // Content
            Group {
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
        }
        .frame(width: 400, height: 450)
        .overlay {
            if isAdding {
                addingOverlay
            }
        }
        .task {
            if repertoireManager.isAuthenticated &&
               (repertoireManager.repertoires.isEmpty ||
                repertoireManager.addableRepertoires.isEmpty) {
                isLoadingRepertoires = true
                await repertoireManager.loadRepertoires()
                isLoadingRepertoires = false
            }
        }
        .sheet(isPresented: $showCreateRepertoire) {
            MacCreateRepertoireView(repertoireManager: repertoireManager)
        }
    }

    // MARK: - Header

    private var headerView: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text("Add to Repertoire")
                    .font(JazzTheme.headline())
                    .foregroundColor(JazzTheme.charcoal)
                Text(songTitle)
                    .font(JazzTheme.subheadline())
                    .foregroundColor(JazzTheme.charcoal.opacity(0.7))
                    .lineLimit(1)
            }

            Spacer()

            Button(action: { dismiss() }) {
                Text("Cancel")
                    .foregroundColor(JazzTheme.burgundy)
            }
            .buttonStyle(.plain)
            .disabled(isAdding)
        }
        .padding()
        .background(JazzTheme.cardBackground)
    }

    // MARK: - Auth Required View

    private var authRequiredView: some View {
        VStack(spacing: 20) {
            Image(systemName: "lock.fill")
                .font(.system(size: 48))
                .foregroundColor(JazzTheme.burgundy.opacity(0.6))

            Text("Sign In Required")
                .font(JazzTheme.title2())
                .foregroundColor(JazzTheme.charcoal)

            Text("You need to be signed in to add songs to repertoires")
                .font(JazzTheme.body())
                .foregroundColor(JazzTheme.charcoal.opacity(0.7))
                .multilineTextAlignment(.center)
                .padding(.horizontal)

            Button("Close") {
                dismiss()
            }
            .buttonStyle(.borderedProminent)
            .tint(JazzTheme.burgundy)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(JazzTheme.backgroundLight)
    }

    // MARK: - Loading View

    private var loadingView: some View {
        VStack(spacing: 16) {
            ProgressView()
                .controlSize(.large)
            Text("Loading repertoires...")
                .foregroundColor(JazzTheme.charcoal.opacity(0.7))
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(JazzTheme.backgroundLight)
    }

    // MARK: - Empty Repertoires View

    private var emptyRepertoiresView: some View {
        VStack(spacing: 20) {
            Image(systemName: "music.note.list")
                .font(.system(size: 48))
                .foregroundColor(JazzTheme.smokeGray.opacity(0.5))

            Text("No Repertoires Yet")
                .font(JazzTheme.title2())
                .foregroundColor(JazzTheme.charcoal)

            Text("Create a repertoire first to start organizing your songs.")
                .font(JazzTheme.subheadline())
                .foregroundColor(JazzTheme.charcoal.opacity(0.7))
                .multilineTextAlignment(.center)
                .padding(.horizontal)

            Button("Create Repertoire") {
                showCreateRepertoire = true
            }
            .buttonStyle(.borderedProminent)
            .tint(JazzTheme.burgundy)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(JazzTheme.backgroundLight)
    }

    // MARK: - Repertoire List

    private var repertoireList: some View {
        ScrollView {
            VStack(spacing: 0) {
                // Quick add section
                if let lastUsed = repertoireManager.lastUsedRepertoire {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Quick Add")
                            .font(JazzTheme.caption())
                            .foregroundColor(JazzTheme.charcoal.opacity(0.6))
                            .padding(.horizontal)
                            .padding(.top, 12)

                        Button(action: { addToRepertoire(lastUsed) }) {
                            HStack {
                                VStack(alignment: .leading, spacing: 4) {
                                    Text("Add to \(lastUsed.name)")
                                        .font(JazzTheme.headline())
                                        .foregroundColor(JazzTheme.charcoal)
                                    Text("Last used")
                                        .font(JazzTheme.caption())
                                        .foregroundColor(JazzTheme.charcoal.opacity(0.6))
                                }
                                Spacer()
                                Image(systemName: "arrow.right.circle.fill")
                                    .font(.title2)
                                    .foregroundColor(JazzTheme.amber)
                            }
                            .padding()
                            .background(JazzTheme.amber.opacity(0.1))
                            .cornerRadius(8)
                        }
                        .buttonStyle(.plain)
                        .disabled(isAdding)
                        .padding(.horizontal)
                    }
                }

                // All repertoires section
                VStack(alignment: .leading, spacing: 8) {
                    Text("All Repertoires")
                        .font(JazzTheme.caption())
                        .foregroundColor(JazzTheme.charcoal.opacity(0.6))
                        .padding(.horizontal)
                        .padding(.top, 16)

                    ForEach(repertoireManager.addableRepertoires) { repertoire in
                        Button(action: { addToRepertoire(repertoire) }) {
                            HStack {
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(repertoire.name)
                                        .font(JazzTheme.headline())
                                        .foregroundColor(JazzTheme.charcoal)

                                    if let description = repertoire.description, !description.isEmpty {
                                        Text(description)
                                            .font(JazzTheme.subheadline())
                                            .foregroundColor(JazzTheme.charcoal.opacity(0.7))
                                            .lineLimit(2)
                                    }

                                    Text("\(repertoire.songCount) songs")
                                        .font(JazzTheme.caption())
                                        .foregroundColor(JazzTheme.burgundy)
                                }
                                Spacer()
                            }
                            .padding()
                            .background(JazzTheme.cardBackground)
                            .cornerRadius(8)
                        }
                        .buttonStyle(.plain)
                        .disabled(isAdding)
                        .padding(.horizontal)
                    }
                }

                // Create new repertoire button
                Button(action: { showCreateRepertoire = true }) {
                    HStack {
                        Image(systemName: "plus.circle.fill")
                            .foregroundColor(JazzTheme.burgundy)
                        Text("Create New Repertoire")
                            .foregroundColor(JazzTheme.burgundy)
                        Spacer()
                    }
                    .padding()
                }
                .buttonStyle(.plain)
                .padding(.horizontal)
                .padding(.vertical, 8)
            }
            .padding(.bottom)
        }
        .background(JazzTheme.backgroundLight)
    }

    // MARK: - Adding Overlay

    private var addingOverlay: some View {
        ZStack {
            Color.black.opacity(0.3)

            VStack(spacing: 16) {
                ProgressView()
                    .controlSize(.large)
                Text("Adding to repertoire...")
                    .font(JazzTheme.headline())
            }
            .padding(30)
            .background(JazzTheme.cardBackground)
            .cornerRadius(12)
        }
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
                    repertoireManager.setLastUsedRepertoire(repertoire)
                    dismiss()
                    onSuccess?("Added \"\(songTitle)\" to \(repertoire.name)")
                } else {
                    dismiss()
                    let errorMessage = repertoireManager.errorMessage ?? "Failed to add song"
                    onError?(errorMessage)
                }
            }
        }
    }
}

#Preview {
    MacAddToRepertoireSheet(
        songId: "test-id",
        songTitle: "Test Song",
        repertoireManager: RepertoireManager()
    )
}

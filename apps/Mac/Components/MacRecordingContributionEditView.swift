//
//  MacRecordingContributionEditView.swift
//  JazzReferenceMac
//
//  Form for editing user's contribution to recording metadata (key, tempo, instrumental/vocal)
//

import SwiftUI

struct MacRecordingContributionEditView: View {
    let recordingId: String
    let recordingTitle: String
    let currentContribution: UserContribution?
    let onSave: () -> Void

    @Environment(\.dismiss) var dismiss
    @EnvironmentObject var authManager: AuthenticationManager

    @State private var selectedKey: MusicalKey?
    @State private var tempoText: String = ""
    @State private var isInstrumental: Bool?
    @State private var isSaving = false
    @State private var isDeleting = false
    @State private var showError = false
    @State private var errorMessage = ""
    @State private var showDeleteConfirmation = false

    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Text("Contribute Data")
                    .font(JazzTheme.title2())
                    .foregroundColor(JazzTheme.charcoal)
                Spacer()
            }
            .padding()
            .background(JazzTheme.backgroundLight)

            Divider()

            // Form content
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    // Recording info
                    Text(recordingTitle)
                        .font(JazzTheme.headline())
                        .foregroundColor(JazzTheme.smokeGray)

                    // Performance Key Section
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Performance Key")
                            .font(JazzTheme.subheadline(weight: .medium))
                            .foregroundColor(JazzTheme.charcoal)

                        Picker("Key", selection: $selectedKey) {
                            Text("Not set").tag(nil as MusicalKey?)
                            ForEach(MusicalKey.allCases) { key in
                                Text(key.displayName).tag(key as MusicalKey?)
                            }
                        }
                        .labelsHidden()
                        .frame(maxWidth: .infinity, alignment: .leading)

                        Text("The key this performance is played in (may differ from the original composed key)")
                            .font(JazzTheme.caption())
                            .foregroundColor(JazzTheme.smokeGray)
                    }

                    // Tempo Section
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Tempo")
                            .font(JazzTheme.subheadline(weight: .medium))
                            .foregroundColor(JazzTheme.charcoal)

                        HStack {
                            TextField("BPM", text: $tempoText)
                                .textFieldStyle(.roundedBorder)
                                .frame(width: 100)

                            if !tempoText.isEmpty {
                                Button {
                                    tempoText = ""
                                } label: {
                                    Image(systemName: "xmark.circle.fill")
                                        .foregroundColor(JazzTheme.smokeGray)
                                }
                                .buttonStyle(.plain)
                            }
                        }

                        Text("Beats per minute (40-400). Typical jazz: ballad ~60, medium swing ~120, up-tempo ~200+")
                            .font(JazzTheme.caption())
                            .foregroundColor(JazzTheme.smokeGray)
                    }

                    // Instrumental/Vocal Section
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Instrumental or Vocal")
                            .font(JazzTheme.subheadline(weight: .medium))
                            .foregroundColor(JazzTheme.charcoal)

                        Picker("Type", selection: $isInstrumental) {
                            Text("Not set").tag(nil as Bool?)
                            Text("Instrumental").tag(true as Bool?)
                            Text("Vocal").tag(false as Bool?)
                        }
                        .pickerStyle(.segmented)
                        .labelsHidden()
                        .frame(maxWidth: 300)

                        Text("Is this an instrumental recording or does it include vocals?")
                            .font(JazzTheme.caption())
                            .foregroundColor(JazzTheme.smokeGray)
                    }

                    // Info text
                    if !hasChanges {
                        Text("Enter at least one value above to save")
                            .font(JazzTheme.caption())
                            .foregroundColor(JazzTheme.smokeGray)
                    } else {
                        Text("You can contribute just one field or all three - any contribution helps!")
                            .font(JazzTheme.caption())
                            .foregroundColor(JazzTheme.brass)
                    }
                }
                .padding()
            }

            Divider()

            // Footer buttons
            HStack {
                // Delete button (if has existing contribution)
                if currentContribution != nil {
                    Button(role: .destructive) {
                        showDeleteConfirmation = true
                    } label: {
                        if isDeleting {
                            ProgressView()
                                .controlSize(.small)
                        } else {
                            Text("Delete My Contribution")
                        }
                    }
                    .disabled(isDeleting || isSaving)
                }

                Spacer()

                Button("Cancel") {
                    dismiss()
                }
                .keyboardShortcut(.cancelAction)
                .disabled(isSaving || isDeleting)

                Button {
                    saveContribution()
                } label: {
                    if isSaving {
                        ProgressView()
                            .controlSize(.small)
                    } else {
                        Text("Save")
                    }
                }
                .keyboardShortcut(.defaultAction)
                .buttonStyle(.borderedProminent)
                .tint(JazzTheme.burgundy)
                .disabled(isSaving || isDeleting || !hasChanges)
            }
            .padding()
            .background(JazzTheme.backgroundLight)
        }
        .frame(width: 450, height: 500)
        .background(JazzTheme.backgroundLight)
        .onAppear {
            loadCurrentValues()
        }
        .alert("Error", isPresented: $showError) {
            Button("OK", role: .cancel) { }
        } message: {
            Text(errorMessage)
        }
        .confirmationDialog(
            "Delete Contribution",
            isPresented: $showDeleteConfirmation,
            titleVisibility: .visible
        ) {
            Button("Delete", role: .destructive) {
                deleteContribution()
            }
            Button("Cancel", role: .cancel) { }
        } message: {
            Text("Are you sure you want to delete your contribution for this recording?")
        }
    }

    private var hasChanges: Bool {
        selectedKey != nil || !tempoText.isEmpty || isInstrumental != nil
    }

    private func loadCurrentValues() {
        if let contrib = currentContribution {
            if let key = contrib.performanceKey {
                selectedKey = MusicalKey(rawValue: key)
            }
            if let tempo = contrib.tempoBpm {
                tempoText = String(tempo)
            }
            isInstrumental = contrib.isInstrumental
        }
    }

    private func saveContribution() {
        // Validate tempo if provided
        var tempoBpm: Int? = nil
        if !tempoText.isEmpty {
            guard let tempo = Int(tempoText), tempo >= 40 && tempo <= 400 else {
                errorMessage = "Tempo must be between 40 and 400 BPM"
                showError = true
                return
            }
            tempoBpm = tempo
        }

        // Check if at least one field has a value
        if selectedKey == nil && tempoBpm == nil && isInstrumental == nil {
            errorMessage = "Please provide at least one value"
            showError = true
            return
        }

        isSaving = true

        Task {
            do {
                // Build request body
                var body: [String: Any] = [:]
                if let key = selectedKey?.rawValue { body["performance_key"] = key }
                if let tempo = tempoBpm { body["tempo_bpm"] = tempo }
                if let instrumental = isInstrumental { body["is_instrumental"] = instrumental }

                let bodyData = try JSONSerialization.data(withJSONObject: body)

                guard let url = URL(string: "\(NetworkManager.baseURL)/recordings/\(recordingId)/contribution") else {
                    throw URLError(.badURL)
                }

                _ = try await authManager.makeAuthenticatedRequest(
                    url: url,
                    method: "PUT",
                    body: bodyData,
                    contentType: "application/json"
                )

                await MainActor.run {
                    isSaving = false
                    onSave()
                    dismiss()
                }
            } catch {
                await MainActor.run {
                    isSaving = false
                    if (error as? URLError)?.code == .userAuthenticationRequired {
                        errorMessage = "Not authenticated. Please sign in again."
                    } else {
                        errorMessage = "Failed to save contribution. Please try again."
                    }
                    showError = true
                }
            }
        }
    }

    private func deleteContribution() {
        isDeleting = true

        Task {
            do {
                guard let url = URL(string: "\(NetworkManager.baseURL)/recordings/\(recordingId)/contribution") else {
                    throw URLError(.badURL)
                }

                _ = try await authManager.makeAuthenticatedRequest(
                    url: url,
                    method: "DELETE"
                )

                await MainActor.run {
                    isDeleting = false
                    onSave()
                    dismiss()
                }
            } catch {
                await MainActor.run {
                    isDeleting = false
                    if (error as? URLError)?.code == .userAuthenticationRequired {
                        errorMessage = "Not authenticated. Please sign in again."
                    } else {
                        errorMessage = "Failed to delete contribution. Please try again."
                    }
                    showError = true
                }
            }
        }
    }
}

// MARK: - Previews

#Preview("New Contribution") {
    MacRecordingContributionEditView(
        recordingId: "preview-1",
        recordingTitle: "Take Five - Time Out",
        currentContribution: nil,
        onSave: {}
    )
    .environmentObject(AuthenticationManager())
}

#Preview("Edit Contribution") {
    MacRecordingContributionEditView(
        recordingId: "preview-2",
        recordingTitle: "Take Five - Time Out",
        currentContribution: UserContribution.preview,
        onSave: {}
    )
    .environmentObject(AuthenticationManager())
}

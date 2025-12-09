//
//  RecordingFilterSheet.swift
//  JazzReference
//
//  Bottom sheet for filtering recordings by availability and instrument
//

import SwiftUI

struct RecordingFilterSheet: View {
    @Binding var selectedFilter: SongRecordingFilter
    @Binding var selectedInstrument: InstrumentFamily?
    let availableInstruments: [InstrumentFamily]

    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {

                    // MARK: - Availability Section
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Availability")
                            .font(JazzTheme.headline())
                            .foregroundColor(JazzTheme.charcoal)

                        VStack(spacing: 0) {
                            availabilityRow(
                                title: "All recordings",
                                subtitle: "Show all recordings",
                                isSelected: selectedFilter == .all
                            ) {
                                selectedFilter = .all
                            }

                            Divider()
                                .padding(.leading, 44)

                            availabilityRow(
                                title: "With Spotify",
                                subtitle: "Only recordings you can play",
                                isSelected: selectedFilter == .withSpotify
                            ) {
                                selectedFilter = .withSpotify
                            }
                        }
                        .background(Color(.systemBackground))
                        .cornerRadius(10)
                    }

                    // MARK: - Instrument Section
                    if !availableInstruments.isEmpty {
                        VStack(alignment: .leading, spacing: 12) {
                            Text("By Instrument")
                                .font(JazzTheme.headline())
                                .foregroundColor(JazzTheme.charcoal)

                            Text("Filter to recordings featuring a specific instrument")
                                .font(JazzTheme.subheadline())
                                .foregroundColor(JazzTheme.smokeGray)

                            LazyVGrid(columns: [
                                GridItem(.flexible()),
                                GridItem(.flexible()),
                                GridItem(.flexible())
                            ], spacing: 10) {
                                ForEach(availableInstruments, id: \.self) { family in
                                    instrumentButton(family)
                                }
                            }
                        }
                    }

                    Spacer(minLength: 40)
                }
                .padding()
            }
            .background(JazzTheme.backgroundLight)
            .navigationTitle("Filter Recordings")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    if hasActiveFilters {
                        Button("Clear All") {
                            clearAllFilters()
                        }
                        .foregroundColor(JazzTheme.burgundy)
                    }
                }

                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") {
                        dismiss()
                    }
                    .fontWeight(.semibold)
                    .foregroundColor(JazzTheme.burgundy)
                }
            }
        }
        .presentationDetents([.medium, .large])
        .presentationDragIndicator(.visible)
    }

    // MARK: - Helper Views

    @ViewBuilder
    private func availabilityRow(
        title: String,
        subtitle: String,
        isSelected: Bool,
        action: @escaping () -> Void
    ) -> some View {
        Button(action: action) {
            HStack(spacing: 12) {
                Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                    .font(JazzTheme.title2())
                    .foregroundColor(isSelected ? JazzTheme.burgundy : JazzTheme.smokeGray.opacity(0.5))

                VStack(alignment: .leading, spacing: 2) {
                    Text(title)
                        .font(JazzTheme.body())
                        .foregroundColor(JazzTheme.charcoal)
                    Text(subtitle)
                        .font(JazzTheme.caption())
                        .foregroundColor(JazzTheme.smokeGray)
                }

                Spacer()
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }

    @ViewBuilder
    private func instrumentButton(_ family: InstrumentFamily) -> some View {
        let isSelected = selectedInstrument == family

        Button(action: {
            if selectedInstrument == family {
                selectedInstrument = nil
            } else {
                selectedInstrument = family
            }
        }) {
            HStack(spacing: 6) {
                Image(systemName: iconForInstrument(family))
                    .font(JazzTheme.caption())
                Text(family.rawValue)
                    .font(JazzTheme.subheadline())
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 10)
            .padding(.horizontal, 8)
            .background(isSelected ? JazzTheme.brass : Color(.systemBackground))
            .foregroundColor(isSelected ? .white : JazzTheme.charcoal)
            .cornerRadius(8)
            .overlay(
                RoundedRectangle(cornerRadius: 8)
                    .stroke(isSelected ? Color.clear : JazzTheme.smokeGray.opacity(0.3), lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
    }

    // MARK: - Helpers

    private var hasActiveFilters: Bool {
        selectedFilter == .withSpotify || selectedInstrument != nil
    }

    private func clearAllFilters() {
        selectedFilter = .all  // Reset to no filters
        selectedInstrument = nil
    }

    private func iconForInstrument(_ family: InstrumentFamily) -> String {
        switch family {
        case .guitar: return "guitars"
        case .saxophone: return "music.note"
        case .trumpet: return "music.note"
        case .trombone: return "music.note"
        case .piano: return "pianokeys"
        case .organ: return "pianokeys"
        case .bass: return "music.note"
        case .drums: return "drum"
        case .clarinet: return "music.note"
        case .flute: return "music.note"
        case .vibraphone: return "music.note"
        case .vocals: return "mic"
        }
    }
}

// MARK: - Preview

#Preview {
    RecordingFilterSheet(
        selectedFilter: .constant(.withSpotify),
        selectedInstrument: .constant(nil),
        availableInstruments: [.guitar, .saxophone, .trumpet, .piano, .bass, .drums]
    )
}

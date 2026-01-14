//
//  CommunityDataSection.swift
//  JazzReference
//
//  Displays community-contributed metadata for a recording (key, tempo, instrumental/vocal)
//  Shows consensus values calculated from all user contributions
//

import SwiftUI

struct CommunityDataSection: View {
    let recordingId: String
    let communityData: CommunityData?
    let userContribution: UserContribution?
    let isAuthenticated: Bool
    let onEditTapped: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Divider()
                .padding(.horizontal)
                .padding(.top, 16)

            HStack(spacing: 0) {
                Spacer().frame(width: 16)

                VStack(alignment: .leading, spacing: 12) {
                    // Header
                    HStack {
                        Image(systemName: "person.3.fill")
                            .foregroundColor(JazzTheme.brass)
                        Text("Community Data")
                            .font(JazzTheme.title2())
                            .bold()
                            .foregroundColor(JazzTheme.charcoal)

                        Spacer()

                        // Edit/Contribute button
                        if isAuthenticated {
                            Button {
                                onEditTapped()
                            } label: {
                                HStack(spacing: 4) {
                                    Image(systemName: userContribution != nil ? "pencil" : "plus")
                                    Text(userContribution != nil ? "Edit" : "Contribute")
                                }
                                .font(JazzTheme.caption())
                                .foregroundColor(JazzTheme.burgundy)
                                .padding(.horizontal, 10)
                                .padding(.vertical, 6)
                                .background(JazzTheme.burgundy.opacity(0.1))
                                .cornerRadius(6)
                            }
                        }
                    }
                    .padding(.top, 12)

                    // Data rows
                    if let data = communityData, hasAnyData(data) {
                        VStack(spacing: 10) {
                            // Performance Key
                            CommunityDataRow(
                                icon: "music.note",
                                label: "Key",
                                value: data.consensus.performanceKey ?? "Not set",
                                count: data.counts.key,
                                userValue: userContribution?.performanceKey,
                                isEmpty: data.consensus.performanceKey == nil
                            )

                            // Tempo
                            CommunityDataRow(
                                icon: "metronome",
                                label: "Tempo",
                                value: data.consensus.tempoMarking ?? "Not set",
                                count: data.counts.tempo,
                                userValue: userContribution?.tempoMarking,
                                isEmpty: data.consensus.tempoMarking == nil,
                                subtitleText: data.consensus.tempoMarking.flatMap { TempoMarking(rawValue: $0)?.bpmRange }.map { "\($0) BPM" }
                            )

                            // Instrumental/Vocal
                            CommunityDataRow(
                                icon: data.consensus.isInstrumental == true ? "pianokeys" : "mic",
                                label: "Type",
                                value: formatInstrumental(data.consensus.isInstrumental),
                                count: data.counts.instrumental,
                                userValue: userContribution?.isInstrumental.map { formatInstrumentalValue($0) },
                                isEmpty: data.consensus.isInstrumental == nil
                            )
                        }
                    } else {
                        // No data yet
                        VStack(alignment: .center, spacing: 8) {
                            Text("No community data yet")
                                .font(JazzTheme.body())
                                .foregroundColor(JazzTheme.smokeGray)

                            if isAuthenticated {
                                Text("Be the first to contribute!")
                                    .font(JazzTheme.caption())
                                    .foregroundColor(JazzTheme.brass)
                            } else {
                                Text("Sign in to contribute data")
                                    .font(JazzTheme.caption())
                                    .foregroundColor(JazzTheme.burgundy)
                            }
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 16)
                    }
                }
                .padding(.bottom, 12)

                Spacer().frame(width: 16)
            }
        }
        .background(JazzTheme.backgroundLight)
    }

    private func hasAnyData(_ data: CommunityData) -> Bool {
        data.counts.key > 0 || data.counts.tempo > 0 || data.counts.instrumental > 0
    }

    private func formatInstrumental(_ value: Bool?) -> String {
        switch value {
        case true: return "Instrumental"
        case false: return "Vocal"
        case nil: return "Not set"
        }
    }

    private func formatInstrumentalValue(_ value: Bool) -> String {
        value ? "Instrumental" : "Vocal"
    }
}

// MARK: - Data Row Component

struct CommunityDataRow: View {
    let icon: String
    let label: String
    let value: String
    let count: Int
    let userValue: String?
    let isEmpty: Bool
    var subtitleText: String? = nil

    var body: some View {
        HStack(alignment: .center, spacing: 12) {
            Image(systemName: icon)
                .foregroundColor(isEmpty ? JazzTheme.smokeGray.opacity(0.5) : JazzTheme.brass)
                .frame(width: 24)

            Text(label)
                .font(JazzTheme.subheadline())
                .foregroundColor(JazzTheme.smokeGray)
                .frame(width: 50, alignment: .leading)

            Spacer()

            VStack(alignment: .trailing, spacing: 2) {
                Text(value)
                    .font(JazzTheme.body())
                    .fontWeight(isEmpty ? .regular : .medium)
                    .foregroundColor(isEmpty ? JazzTheme.smokeGray.opacity(0.5) : JazzTheme.charcoal)

                if let subtitle = subtitleText {
                    Text(subtitle)
                        .font(JazzTheme.caption2())
                        .foregroundColor(JazzTheme.smokeGray)
                }

                if count > 0 {
                    Text("\(count) \(count == 1 ? "vote" : "votes")")
                        .font(JazzTheme.caption2())
                        .foregroundColor(JazzTheme.smokeGray)
                }

                // Show user's value if different from consensus
                if let userVal = userValue, !isEmpty, userVal != value {
                    Text("You: \(userVal)")
                        .font(JazzTheme.caption2())
                        .foregroundColor(JazzTheme.burgundy)
                }
            }
        }
        .padding(.vertical, 4)
    }
}

// MARK: - Previews

#Preview("With Data") {
    ScrollView {
        CommunityDataSection(
            recordingId: "preview-1",
            communityData: CommunityData.preview,
            userContribution: UserContribution.preview,
            isAuthenticated: true,
            onEditTapped: {}
        )
    }
}

#Preview("Empty Data - Authenticated") {
    ScrollView {
        CommunityDataSection(
            recordingId: "preview-2",
            communityData: CommunityData.previewEmpty,
            userContribution: nil,
            isAuthenticated: true,
            onEditTapped: {}
        )
    }
}

#Preview("Empty Data - Not Authenticated") {
    ScrollView {
        CommunityDataSection(
            recordingId: "preview-3",
            communityData: nil,
            userContribution: nil,
            isAuthenticated: false,
            onEditTapped: {}
        )
    }
}

#Preview("Partial Data") {
    ScrollView {
        CommunityDataSection(
            recordingId: "preview-4",
            communityData: CommunityData(
                consensus: CommunityConsensus.previewPartial,
                counts: ContributionCounts(key: 2, tempo: 0, instrumental: 0)
            ),
            userContribution: nil,
            isAuthenticated: true,
            onEditTapped: {}
        )
    }
}

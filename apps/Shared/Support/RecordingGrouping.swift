//
//  RecordingGrouping.swift
//  Approach Note
//
//  Shared filtering, sorting, and grouping logic for recordings lists.
//  Used by iOS RecordingsSection and Mac SongDetailView to keep their
//  recording-grid behavior in sync.
//

import Foundation

enum RecordingGrouping {

    // MARK: - Shell ↔ hydrated field helpers
    //
    // For instrument filter / vocal filter: shell rows carry dedicated
    // top-level fields (`instrumentsPresent`, `isInstrumentalConsensus`)
    // while hydrated rows expose the same info via `performers[]` and
    // `communityData.consensus`. The helpers below pick whichever is
    // available so filters work before, during, and after hydration —
    // without the caller having to know which shape a row is in.

    /// All instrument names appearing anywhere on a recording (leader +
    /// sidemen). Prefers the shell's pre-computed flat array when
    /// present; falls back to scanning `performers[].instrument`.
    private static func instrumentNames(for recording: Recording) -> [String] {
        if let shellList = recording.instrumentsPresent {
            return shellList
        }
        return recording.performers?.compactMap(\.instrument) ?? []
    }

    /// The community-consensus "is this an instrumental track" value.
    /// Prefers the shell's flat bool when present; falls back to the
    /// hydrated `community_data.consensus.is_instrumental` path.
    private static func consensusIsInstrumental(for recording: Recording) -> Bool? {
        if let shellBool = recording.isInstrumentalConsensus {
            return shellBool
        }
        return recording.communityData?.consensus.isInstrumental
    }

    /// The artist label that RecordingRowView (iOS) and RecordingCard (Mac)
    /// show on the card: `artist_credit` if present, else the leader's
    /// display name, else the first performer's name. Kept in sync with
    /// both card views so the "More Recordings" section sorts in the same
    /// order the user reads.
    private static func displayArtistName(for recording: Recording) -> String {
        if let credit = recording.artistCredit, !credit.isEmpty {
            return credit
        }
        if let performers = recording.performers {
            if let leader = performers.first(where: { $0.role?.lowercased() == "leader" }) {
                return leader.name
            }
            if let first = performers.first {
                return first.name
            }
        }
        return "Unknown Artist"
    }

    // MARK: - Available Instruments

    /// Distinct instrument families present across the given recordings,
    /// sorted by `InstrumentFamily.rawValue`.
    static func availableInstruments(in recordings: [Recording]) -> [InstrumentFamily] {
        var families = Set<InstrumentFamily>()
        for recording in recordings {
            for instrument in instrumentNames(for: recording) {
                if let family = InstrumentFamily.family(for: instrument) {
                    families.insert(family)
                }
            }
        }
        return families.sorted { $0.rawValue < $1.rawValue }
    }

    // MARK: - Filter

    /// Apply instrument / vocal / streaming filters to a recording list.
    /// Filter order is irrelevant to the resulting set, but follows
    /// instrument → vocal → streaming for readability.
    static func filter(
        _ recordings: [Recording],
        instrument: InstrumentFamily?,
        vocal: VocalFilter,
        streaming: SongRecordingFilter
    ) -> [Recording] {
        var result = recordings

        if let family = instrument {
            result = result.filter { recording in
                instrumentNames(for: recording).contains { name in
                    InstrumentFamily.family(for: name) == family
                }
            }
        }

        switch vocal {
        case .all:
            break
        case .instrumental:
            result = result.filter { consensusIsInstrumental(for: $0) == true }
        case .vocal:
            result = result.filter { consensusIsInstrumental(for: $0) == false }
        }

        switch streaming {
        case .all:
            break
        case .playable:
            result = result.filter { $0.isPlayable }
        case .withSpotify:
            result = result.filter { $0.hasSpotifyAvailable }
        case .withAppleMusic:
            result = result.filter { $0.hasAppleMusicAvailable }
        case .withYoutube:
            result = result.filter { $0.hasYoutubeAvailable }
        }

        return result
    }

    // MARK: - Group

    /// Group recordings according to the sort order.
    /// - `.year`: grouped by decade ("1960s", "1970s", …, "Unknown Year").
    /// - `.name`: artists with ≥2 recordings each get their own group; single
    ///   recordings consolidate into "More Recordings" sorted alphabetically
    ///   by leader sort-name.
    static func grouped(
        _ recordings: [Recording],
        sortOrder: RecordingSortOrder
    ) -> [(groupKey: String, recordings: [Recording])] {
        switch sortOrder {
        case .year:
            return groupByDecade(recordings)
        case .name:
            return groupByArtistWithConsolidation(recordings)
        }
    }

    // MARK: - Decade Grouping (for Year sort)

    private static func groupByDecade(
        _ recordings: [Recording]
    ) -> [(groupKey: String, recordings: [Recording])] {
        var decadeOrder: [String] = []
        var decades: [String: [Recording]] = [:]

        for recording in recordings {
            let decadeKey: String
            if let year = recording.recordingYear {
                let decade = (year / 10) * 10
                decadeKey = "\(decade)s"
            } else {
                decadeKey = "Unknown Year"
            }

            if decades[decadeKey] == nil {
                decadeOrder.append(decadeKey)
            }
            decades[decadeKey, default: []].append(recording)
        }

        return decadeOrder.compactMap { key in
            guard let recs = decades[key] else { return nil }
            return (groupKey: key, recordings: recs)
        }
    }

    // MARK: - Artist Grouping with Consolidation (for Name sort)

    private static func groupByArtistWithConsolidation(
        _ recordings: [Recording]
    ) -> [(groupKey: String, recordings: [Recording])] {
        // First pass: count recordings per artist.
        var artistCounts: [String: Int] = [:]
        for recording in recordings {
            let artist = recording.performers?.first { $0.role == "leader" }?.name ?? "Unknown"
            artistCounts[artist, default: 0] += 1
        }

        // Second pass: separate featured artists (≥2 recordings) from singles.
        var featuredOrder: [String] = []
        var featuredGroups: [String: [Recording]] = [:]
        var moreRecordings: [Recording] = []

        for recording in recordings {
            let artist = recording.performers?.first { $0.role == "leader" }?.name ?? "Unknown"

            if artistCounts[artist, default: 0] >= 2 {
                if featuredGroups[artist] == nil {
                    featuredOrder.append(artist)
                }
                featuredGroups[artist, default: []].append(recording)
            } else {
                moreRecordings.append(recording)
            }
        }

        // Build result: featured artists first (in original order, which
        // follows the server's sort=name ORDER BY leader sort-name), then
        // a "More Recordings" group of singles sorted alphabetically by
        // the same artist label the card displays.
        var result: [(groupKey: String, recordings: [Recording])] = []

        for artist in featuredOrder {
            if let recs = featuredGroups[artist] {
                result.append((groupKey: artist, recordings: recs))
            }
        }

        if !moreRecordings.isEmpty {
            // Sort by the artist label the card actually shows — otherwise
            // the user sees cards labeled "Nat King Cole" / "Tommy Dorsey"
            // arranged in last-name order, which reads as unsorted (#93).
            let sortedMore = moreRecordings.sorted { rec1, rec2 in
                let key1 = displayArtistName(for: rec1)
                let key2 = displayArtistName(for: rec2)
                return key1.localizedCaseInsensitiveCompare(key2) == .orderedAscending
            }
            result.append((groupKey: "More Recordings", recordings: sortedMore))
        }

        return result
    }
}

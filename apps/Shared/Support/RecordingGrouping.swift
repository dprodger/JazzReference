//
//  RecordingGrouping.swift
//  JazzReference
//
//  Shared filtering, sorting, and grouping logic for recordings lists.
//  Used by iOS RecordingsSection and Mac SongDetailView to keep their
//  recording-grid behavior in sync.
//

import Foundation

enum RecordingGrouping {

    // MARK: - Available Instruments

    /// Distinct instrument families present in the given recordings' performers,
    /// sorted by `InstrumentFamily.rawValue`.
    static func availableInstruments(in recordings: [Recording]) -> [InstrumentFamily] {
        var families = Set<InstrumentFamily>()
        for recording in recordings {
            if let performers = recording.performers {
                for performer in performers {
                    if let instrument = performer.instrument,
                       let family = InstrumentFamily.family(for: instrument) {
                        families.insert(family)
                    }
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
                guard let performers = recording.performers else { return false }
                return performers.contains { performer in
                    guard let instrument = performer.instrument else { return false }
                    return InstrumentFamily.family(for: instrument) == family
                }
            }
        }

        switch vocal {
        case .all:
            break
        case .instrumental:
            result = result.filter { recording in
                recording.communityData?.consensus.isInstrumental == true
            }
        case .vocal:
            result = result.filter { recording in
                recording.communityData?.consensus.isInstrumental == false
            }
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

        // Build result: featured artists first (in original order), then
        // a "More Recordings" group of singles sorted alphabetically by
        // leader sort-name.
        var result: [(groupKey: String, recordings: [Recording])] = []

        for artist in featuredOrder {
            if let recs = featuredGroups[artist] {
                result.append((groupKey: artist, recordings: recs))
            }
        }

        if !moreRecordings.isEmpty {
            let sortedMore = moreRecordings.sorted { rec1, rec2 in
                let leader1 = rec1.performers?.first { $0.role == "leader" }
                let leader2 = rec2.performers?.first { $0.role == "leader" }
                let sortKey1 = leader1?.sortName ?? leader1?.name ?? "Unknown"
                let sortKey2 = leader2?.sortName ?? leader2?.name ?? "Unknown"
                return sortKey1.localizedCaseInsensitiveCompare(sortKey2) == .orderedAscending
            }
            result.append((groupKey: "More Recordings", recordings: sortedMore))
        }

        return result
    }
}

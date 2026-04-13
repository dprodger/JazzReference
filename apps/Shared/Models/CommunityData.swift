import Foundation

// MARK: - Community Data Models

/// Consensus values computed from all user contributions
struct CommunityConsensus: Codable {
    let performanceKey: String?
    let tempoMarking: String?
    let isInstrumental: Bool?

    enum CodingKeys: String, CodingKey {
        case performanceKey = "performance_key"
        case tempoMarking = "tempo_marking"
        case isInstrumental = "is_instrumental"
    }
}

/// Contribution counts per field
/// Note: key and tempo are optional because the recordings list endpoint
/// only returns the instrumental count (lightweight query for filtering).
/// The full counts are available from the recording detail endpoint.
struct ContributionCounts: Codable {
    let key: Int?
    let tempo: Int?
    let instrumental: Int
}

/// Container for all community-contributed data
struct CommunityData: Codable {
    let consensus: CommunityConsensus
    let counts: ContributionCounts
}

/// User's own contribution for a recording
struct UserContribution: Codable {
    let performanceKey: String?
    let tempoMarking: String?
    let isInstrumental: Bool?
    let updatedAt: String?

    enum CodingKeys: String, CodingKey {
        case performanceKey = "performance_key"
        case tempoMarking = "tempo_marking"
        case isInstrumental = "is_instrumental"
        case updatedAt = "updated_at"
    }
}

/// Musical key options for contribution form (major and minor)
enum MusicalKey: String, CaseIterable, Identifiable {
    case c = "C"
    case db = "Db"
    case d = "D"
    case eb = "Eb"
    case e = "E"
    case f = "F"
    case gb = "Gb"
    case g = "G"
    case ab = "Ab"
    case a = "A"
    case bb = "Bb"
    case b = "B"
    case cm = "Cm"
    case dbm = "Dbm"
    case dm = "Dm"
    case ebm = "Ebm"
    case em = "Em"
    case fm = "Fm"
    case gbm = "Gbm"
    case gm = "Gm"
    case abm = "Abm"
    case am = "Am"
    case bbm = "Bbm"
    case bm = "Bm"

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .c: return "C Major"
        case .db: return "D\u{266D} Major"
        case .d: return "D Major"
        case .eb: return "E\u{266D} Major"
        case .e: return "E Major"
        case .f: return "F Major"
        case .gb: return "G\u{266D} Major"
        case .g: return "G Major"
        case .ab: return "A\u{266D} Major"
        case .a: return "A Major"
        case .bb: return "B\u{266D} Major"
        case .b: return "B Major"
        case .cm: return "C Minor"
        case .dbm: return "D\u{266D} Minor"
        case .dm: return "D Minor"
        case .ebm: return "E\u{266D} Minor"
        case .em: return "E Minor"
        case .fm: return "F Minor"
        case .gbm: return "G\u{266D} Minor"
        case .gm: return "G Minor"
        case .abm: return "A\u{266D} Minor"
        case .am: return "A Minor"
        case .bbm: return "B\u{266D} Minor"
        case .bm: return "B Minor"
        }
    }

    var isMinor: Bool {
        rawValue.hasSuffix("m")
    }

    var shortName: String { rawValue }
}

/// Tempo marking options for contribution form (standard jazz terms)
enum TempoMarking: String, CaseIterable, Identifiable {
    case ballad = "Ballad"
    case slow = "Slow"
    case medium = "Medium"
    case mediumUp = "Medium-Up"
    case upTempo = "Up-Tempo"
    case fast = "Fast"
    case burning = "Burning"

    var id: String { rawValue }
    var displayName: String { rawValue }

    var bpmRange: String {
        switch self {
        case .ballad: return "~50-72"
        case .slow: return "~72-108"
        case .medium: return "~108-144"
        case .mediumUp: return "~144-184"
        case .upTempo: return "~184-224"
        case .fast: return "~224-280"
        case .burning: return "280+"
        }
    }
}

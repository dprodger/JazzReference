//
//  HelperViews.swift
//  JazzReference
//
//  Updated with JazzTheme color palette
//

import SwiftUI
import Combine

// MARK: - Helper Views

struct DetailRow: View {
    let icon: String
    let label: String
    let value: String
    
    var body: some View {
        HStack {
            Label {
                Text(label)
                    .font(JazzTheme.subheadline())
                    .foregroundColor(JazzTheme.smokeGray)
            } icon: {
                Image(systemName: icon)
                    .foregroundColor(JazzTheme.brass)
            }
            Spacer()
            Text(value)
                .font(JazzTheme.subheadline())
                .bold()
                .foregroundColor(JazzTheme.charcoal)
        }
    }
}

struct StreamingButton: View {
    let icon: String
    let color: Color
    let label: String
    
    var body: some View {
        VStack(spacing: 8) {
            Image(systemName: icon)
                .font(JazzTheme.title2())
                .foregroundColor(JazzTheme.cream)
                .frame(width: 60, height: 60)
                .background(color)
                .clipShape(Circle())
            
            Text(label)
                .font(JazzTheme.caption())
                .foregroundColor(JazzTheme.smokeGray)
        }
    }
}

struct PerformerRowView: View {
    let performer: Performer
    
    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text(performer.name)
                    .font(JazzTheme.headline())
                    .foregroundColor(JazzTheme.charcoal)
                
                if let instrument = performer.instrument {
                    Text(instrument)
                        .font(JazzTheme.subheadline())
                        .foregroundColor(JazzTheme.smokeGray)
                }
            }
            
            Spacer()
            
            if let role = performer.role {
                Text(role.capitalized)
                    .font(JazzTheme.caption())
                    .foregroundColor(JazzTheme.cream)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(role == "leader" ? JazzTheme.burgundy : JazzTheme.brass.opacity(0.7))
                    .cornerRadius(8)
            }
        }
        .padding()
        .background(JazzTheme.cardBackground)
        .cornerRadius(10)
        .padding(.horizontal)
    }
}

// MARK: - NEW COMPONENTS

// External Reference Row Component
struct ExternalReferenceRow: View {
    let reference: ExternalReference
    
    var body: some View {
        Link(destination: URL(string: reference.url)!) {
            HStack(spacing: 12) {
                // Icon
                Image(systemName: reference.iconName)
                    .font(JazzTheme.title3())
                    .foregroundColor(JazzTheme.burgundy)
                    .frame(width: 32)
                
                // Source name
                Text(reference.displayName)
                    .font(JazzTheme.subheadline())
                    .foregroundColor(JazzTheme.charcoal)
                
                Spacer()
                
                // External link indicator
                Image(systemName: "arrow.up.right.square")
                    .font(JazzTheme.caption())
                    .foregroundColor(JazzTheme.smokeGray)
            }
            .padding(.horizontal)
            .padding(.vertical, 12)
            .background(JazzTheme.cardBackground)
            .cornerRadius(8)
            .padding(.horizontal)
        }
    }
}

// Enhanced Recording Row with Authority Badge
struct AuthorityRecordingRow: View {
    let recording: Recording
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 6) {
                    // Title with canonical indicator
                    HStack(spacing: 8) {
                        if recording.isCanonical == true {
                            Image(systemName: "star.fill")
                                .foregroundColor(.yellow)
                                .font(JazzTheme.caption())
                        }
                        
                        Text(recording.albumTitle ?? "Unknown Album")
                            .font(JazzTheme.headline())
                            .foregroundColor(JazzTheme.charcoal)
                    }
                    
                    // Year and label
                    HStack(spacing: 8) {
                        if let year = recording.recordingYear {
                            Text("\(year)")
                                .font(JazzTheme.subheadline())
                                .foregroundColor(JazzTheme.smokeGray)
                        }
                        
                        if let label = recording.label {
                            Text("•")
                                .foregroundColor(JazzTheme.smokeGray)
                            Text(label)
                                .font(JazzTheme.caption())
                                .foregroundColor(JazzTheme.smokeGray)
                        }
                    }
                }
                
                Spacer()
                
                // Authority badge (if present)
                if recording.hasAuthority, let badgeText = recording.authorityBadgeText {
                    AuthorityBadge(text: badgeText, source: recording.primaryAuthoritySource)
                }
            }
        }
        .padding()
        .background(JazzTheme.cardBackground)
        .cornerRadius(10)
        .padding(.horizontal)
    }
}

// Authority Badge Component
struct AuthorityBadge: View {
    let text: String
    let source: String?
    
    var body: some View {
        HStack(spacing: 4) {
            Image(systemName: "checkmark.seal.fill")
                .font(JazzTheme.caption2())
            Text(text)
                .font(JazzTheme.caption2())
                .fontWeight(.semibold)
        }
        .foregroundColor(.white)
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(badgeColor)
        .cornerRadius(6)
    }
    
    private var badgeColor: Color {
        // Color code by source
        guard let source = source else { return JazzTheme.burgundy }
        
        switch source.lowercased() {
        case "jazzstandards.com":
            return Color(red: 0.2, green: 0.5, blue: 0.8) // Blue
        case "allmusic":
            return Color(red: 0.8, green: 0.3, blue: 0.3) // Red
        case "discogs":
            return Color(red: 0.4, green: 0.7, blue: 0.4) // Green
        default:
            return JazzTheme.burgundy
        }
    }
}

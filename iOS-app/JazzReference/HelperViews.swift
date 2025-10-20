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
                    .font(.subheadline)
                    .foregroundColor(JazzTheme.smokeGray)
            } icon: {
                Image(systemName: icon)
                    .foregroundColor(JazzTheme.brass)
            }
            Spacer()
            Text(value)
                .font(.subheadline)
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
                .font(.title2)
                .foregroundColor(JazzTheme.cream)
                .frame(width: 60, height: 60)
                .background(color)
                .clipShape(Circle())
            
            Text(label)
                .font(.caption)
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
                    .font(.headline)
                    .foregroundColor(JazzTheme.charcoal)
                
                if let instrument = performer.instrument {
                    Text(instrument)
                        .font(.subheadline)
                        .foregroundColor(JazzTheme.smokeGray)
                }
            }
            
            Spacer()
            
            if let role = performer.role {
                Text(role.capitalized)
                    .font(.caption)
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

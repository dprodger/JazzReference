//
//  HelperViews.swift
//  JazzReference
//
//  Created by Dave Rodger on 10/8/25.
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
                    .foregroundColor(.secondary)
            } icon: {
                Image(systemName: icon)
                    .foregroundColor(.blue)
            }
            Spacer()
            Text(value)
                .font(.subheadline)
                .bold()
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
                .foregroundColor(.white)
                .frame(width: 60, height: 60)
                .background(color)
                .clipShape(Circle())
            
            Text(label)
                .font(.caption)
                .foregroundColor(.secondary)
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
                
                if let instrument = performer.instrument {
                    Text(instrument)
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                }
            }
            
            Spacer()
            
            if let role = performer.role {
                Text(role.capitalized)
                    .font(.caption)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(role == "leader" ? Color.blue.opacity(0.2) : Color.gray.opacity(0.2))
                    .cornerRadius(8)
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(10)
        .padding(.horizontal)
    }
}

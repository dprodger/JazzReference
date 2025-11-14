//
//  RepertoireLoginPromptView.swift
//  JazzReference
//
//  Created by Dave Rodger on 11/14/25.
//  Prompt shown when unauthenticated users try to access Repertoire
//

import SwiftUI

struct RepertoireLoginPromptView: View {
    @State private var showingLogin = false
    
    var body: some View {
        VStack(spacing: 32) {
            Spacer()
            
            // Icon
            Image(systemName: "music.note.list")
                .font(.system(size: 80))
                .foregroundColor(JazzTheme.burgundy)
            
            // Title and description
            VStack(spacing: 12) {
                Text("Build Your Repertoire")
                    .font(.title)
                    .fontWeight(.bold)
                    .foregroundColor(JazzTheme.charcoal)
                
                Text("Sign in to save songs, track your practice, and build your personal jazz repertoire.")
                    .font(.body)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 32)
            }
            
            // Features list
            VStack(alignment: .leading, spacing: 16) {
                FeatureRow(icon: "bookmark.fill", text: "Save your favorite standards")
                FeatureRow(icon: "chart.line.uptrend.xyaxis", text: "Track your practice progress")
                FeatureRow(icon: "music.note", text: "Organize by learning status")
                FeatureRow(icon: "pencil", text: "Add private notes")
            }
            .padding(.horizontal, 48)
            
            Spacer()
            
            // Sign in button
            Button(action: {
                showingLogin = true
            }) {
                Text("Sign In or Create Account")
                    .fontWeight(.semibold)
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(JazzTheme.burgundy)
                    .foregroundColor(.white)
                    .cornerRadius(10)
            }
            .padding(.horizontal, 32)
            .padding(.bottom, 32)
        }
        .sheet(isPresented: $showingLogin) {
            LoginView()
        }
    }
}

struct FeatureRow: View {
    let icon: String
    let text: String
    
    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .font(.title3)
                .foregroundColor(JazzTheme.burgundy)
                .frame(width: 24)
            
            Text(text)
                .font(.subheadline)
                .foregroundColor(JazzTheme.charcoal)
            
            Spacer()
        }
    }
}

#Preview {
    RepertoireLoginPromptView()
}

//
//  RepertoireLoginPromptView.swift
//  Approach Note
//
//  Created by Dave Rodger on 11/14/25.
//  Inline login prompt shown when unauthenticated users access the
//  Repertoire tab. Reuses LoginFormBody for the form itself so the
//  auth surface stays in one place.
//

import SwiftUI

struct RepertoireLoginPromptView: View {
    @EnvironmentObject var authManager: AuthenticationManager

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                // Header
                VStack(spacing: 12) {
                    Image(systemName: "music.note.list")
                        .font(.system(size: 60))
                        .foregroundColor(ApproachNoteTheme.burgundy)

                    Text("Build Your Repertoire")
                        .font(.title)
                        .fontWeight(.bold)
                        .foregroundColor(ApproachNoteTheme.charcoal)

                    Text("Sign in to save songs and track your practice")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                }
                .padding(.top, 32)

                // Inline presenter — the parent reacts to
                // authManager.isAuthenticated flipping, so we don't need
                // an onAuthenticated dismiss callback.
                LoginFormBody()

                Spacer()
            }
            .padding(.horizontal, 32)
        }
    }
}

#Preview {
    RepertoireLoginPromptView()
        .environmentObject(AuthenticationManager())
}

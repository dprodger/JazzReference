//
//  MacSearchBar.swift
//  Approach Note
//
//  Reusable search bar component for Mac list views
//

import SwiftUI

struct MacSearchBar: View {
    @Binding var text: String
    let placeholder: String
    let backgroundColor: Color

    var body: some View {
        HStack {
            Image(systemName: "magnifyingglass")
                .foregroundColor(ApproachNoteTheme.smokeGray)
            TextField(placeholder, text: $text)
                .textFieldStyle(.plain)
                .font(ApproachNoteTheme.body())
                .foregroundColor(ApproachNoteTheme.charcoal)
            if !text.isEmpty {
                Button(action: { text = "" }) {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundColor(ApproachNoteTheme.smokeGray)
                }
                .buttonStyle(.plain)
            }
        }
        .padding(8)
        .background(Color.white)
        .cornerRadius(8)
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(ApproachNoteTheme.smokeGray.opacity(0.3), lineWidth: 1)
        )
        .padding(.horizontal)
        .padding(.vertical, 12)
        .background(backgroundColor)
    }
}

#Preview {
    VStack(spacing: 0) {
        MacSearchBar(
            text: .constant(""),
            placeholder: "Search songs...",
            backgroundColor: ApproachNoteTheme.burgundy
        )
        MacSearchBar(
            text: .constant("test"),
            placeholder: "Search artists...",
            backgroundColor: ApproachNoteTheme.amber
        )
        MacSearchBar(
            text: .constant(""),
            placeholder: "Search recordings...",
            backgroundColor: ApproachNoteTheme.brass
        )
    }
}

//
//  ReportLinkIssueView.swift
//  JazzReference
//
//  Created by Dave Rodger on 10/24/25.
//
import SwiftUI

struct ReportLinkIssueView: View {
    let entityType: String
    let entityId: String
    let entityName: String
    let externalSource: String
    let externalUrl: String
    let onSubmit: (String) -> Void
    let onCancel: () -> Void
    
    @State private var explanation: String = ""
    @Environment(\.dismiss) var dismiss
    
    var body: some View {
        NavigationView {
            Form {
                Section {
                    Text("Report a problem with this external reference link")
                        .font(.subheadline)
                        .foregroundColor(JazzTheme.smokeGray)
                }
                
                Section(header: Text("Entity Information")) {
                    LabeledContent("Type", value: entityType)
                    LabeledContent("Name", value: entityName)
                    LabeledContent("ID", value: entityId)
                        .font(.caption)
                        .foregroundColor(JazzTheme.smokeGray)
                }
                
                Section(header: Text("External Reference")) {
                    LabeledContent("Source", value: externalSource)
                    VStack(alignment: .leading, spacing: 4) {
                        Text("URL")
                            .font(.caption)
                            .foregroundColor(JazzTheme.smokeGray)
                        Text(externalUrl)
                            .font(.caption)
                            .foregroundColor(JazzTheme.smokeGray)
                            .lineLimit(3)
                    }
                }
                
                Section(header: Text("Issue Description")) {
                    TextEditor(text: $explanation)
                        .frame(minHeight: 100)
                        .font(.body)
                    
                    Text("Please describe the issue with this link (e.g., broken link, incorrect information, wrong page)")
                        .font(.caption)
                        .foregroundColor(JazzTheme.smokeGray)
                }
            }
            .navigationTitle("Report Link Issue")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Cancel") {
                        onCancel()
                    }
                }
                
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Submit") {
                        onSubmit(explanation)
                    }
                    .disabled(explanation.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
            }
        }
    }
}

#Preview {
    ReportLinkIssueView(
        entityType: "Song",
        entityId: "preview-song-1",
        entityName: "Take Five",
        externalSource: "Wikipedia",
        externalUrl: "https://en.wikipedia.org/wiki/Take_Five",
        onSubmit: { explanation in
            print("Submitted: \(explanation)")
        },
        onCancel: {
            print("Cancelled")
        }
    )
}

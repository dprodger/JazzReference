//
//  PerformerDetailView.swift
//  JazzReference
//
//  Created by Dave Rodger on 10/19/25.
//

import SwiftUI

enum RecordingFilter: String, CaseIterable {
    case all = "All"
    case leader = "Leader"
    case sideman = "Sideman"
}

struct PerformerDetailView: View {
    let performerId: String
    @State private var performer: PerformerDetail?
    @State private var isLoading = true
    @State private var selectedFilter: RecordingFilter = .all
    
    private var filteredRecordings: [PerformerRecording] {
        guard let recordings = performer?.recordings else { return [] }
        
        switch selectedFilter {
        case .all:
            return recordings
        case .leader:
            return recordings.filter { $0.role?.lowercased() == "leader" }
        case .sideman:
            return recordings.filter { $0.role?.lowercased() == "sideman" }
        }
    }
    
    var body: some View {
        ScrollView {
            if isLoading {
                ProgressView("Loading...")
                    .padding()
            } else if let performer = performer {
                VStack(alignment: .leading, spacing: 0) {
                    // Styled Header
                    HStack {
                        Image(systemName: "person.fill")
                            .font(.title2)
                            .foregroundColor(.white)
                        Text("ARTIST")
                            .font(.headline)
                            .fontWeight(.semibold)
                            .foregroundColor(.white)
                        Spacer()
                    }
                    .padding()
                    .background(
                        LinearGradient(
                            gradient: Gradient(colors: [Color.orange, Color.orange.opacity(0.8)]),
                            startPoint: .leading,
                            endPoint: .trailing
                        )
                    )
                    
                    VStack(alignment: .leading, spacing: 20) {
                        // Performer Information
                        VStack(alignment: .leading, spacing: 12) {
                            Text(performer.name)
                                .font(.largeTitle)
                                .bold()
                            
                            // Birth and Death Dates
                            if performer.birthDate != nil || performer.deathDate != nil {
                                HStack {
                                    if let birthDate = performer.birthDate {
                                        Text("Born: \(birthDate)")
                                            .font(.subheadline)
                                            .foregroundColor(.secondary)
                                    }
                                    
                                    if performer.birthDate != nil && performer.deathDate != nil {
                                        Text("•")
                                            .foregroundColor(.secondary)
                                    }
                                    
                                    if let deathDate = performer.deathDate {
                                        Text("Died: \(deathDate)")
                                            .font(.subheadline)
                                            .foregroundColor(.secondary)
                                    }
                                }
                            }
                            
                            // Instruments
                            if let instruments = performer.instruments, !instruments.isEmpty {
                                HStack {
                                    Image(systemName: "music.note")
                                        .foregroundColor(.blue)
                                    Text(instruments.map { $0.name }.joined(separator: ", "))
                                        .font(.subheadline)
                                        .foregroundColor(.secondary)
                                }
                            }
                            
                            // Biography
                            if let biography = performer.biography {
                                VStack(alignment: .leading, spacing: 8) {
                                    Text("Biography")
                                        .font(.headline)
                                    Text(biography)
                                        .font(.body)
                                        .foregroundColor(.secondary)
                                }
                                .padding()
                                .background(Color(.systemGray6))
                                .cornerRadius(10)
                            }
                        }
                        .padding()
                        
                        Divider()
                        
                        // Recordings Section
                        VStack(alignment: .leading, spacing: 12) {
                            Text("Recordings (\(filteredRecordings.count))")
                                .font(.title2)
                                .bold()
                                .padding(.horizontal)
                            
                            // Filter Picker
                            Picker("Filter", selection: $selectedFilter) {
                                ForEach(RecordingFilter.allCases, id: \.self) { filter in
                                    Text(filter.rawValue).tag(filter)
                                }
                            }
                            .pickerStyle(.segmented)
                            .padding(.horizontal)
                            
                            if !filteredRecordings.isEmpty {
                                ForEach(filteredRecordings) { recording in
                                    NavigationLink(destination: RecordingDetailView(recordingId: recording.recordingId)) {
                                        PerformerRecordingRowView(recording: recording)
                                    }
                                    .buttonStyle(.plain)
                                }
                            } else {
                                Text("No recordings found")
                                    .foregroundColor(.secondary)
                                    .padding()
                            }
                        }
                    }
                }
                .padding(.vertical)
            } else {
                Text("Performer not found")
                    .foregroundColor(.secondary)
                    .padding()
            }
        }
        .navigationBarTitleDisplayMode(.inline)
        .task {
            #if DEBUG
            if ProcessInfo.processInfo.environment["XCODE_RUNNING_FOR_PREVIEWS"] == "1" {
                // Use mock data for previews
                let networkManager = NetworkManager()
                performer = networkManager.fetchPerformerDetailSync(id: performerId)
                isLoading = false
                return
            }
            #endif
            
            // Real network call for production
            let networkManager = NetworkManager()
            performer = await networkManager.fetchPerformerDetail(id: performerId)
            isLoading = false
        }
    }
}

struct PerformerRecordingRowView: View {
    let recording: PerformerRecording
    
    var body: some View {
        HStack(spacing: 12) {
            // Canonical indicator
            if recording.isCanonical == true {
                Image(systemName: "star.fill")
                    .foregroundColor(.yellow)
                    .font(.subheadline)
                    .frame(width: 20)
            } else {
                Spacer()
                    .frame(width: 20)
            }
            
            // Recording info
            VStack(alignment: .leading, spacing: 4) {
                // Song title
                Text(recording.songTitle)
                    .font(.headline)
                    .lineLimit(1)
                
                // Album name
                if let albumTitle = recording.albumTitle {
                    Text(albumTitle)
                        .font(.subheadline)
                        .foregroundColor(.primary)
                        .lineLimit(1)
                }
                
                // Role
                if let role = recording.role {
                    Text(role.capitalized)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
            
            Spacer()
            
            // Year
            if let year = recording.recordingYear {
                Text(String(year))
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .frame(minWidth: 40, alignment: .trailing)
            }
        }
        .padding(.vertical, 12)
        .padding(.horizontal, 16)
        .background(Color(.systemGray6))
        .cornerRadius(8)
        .padding(.horizontal)
    }
}

#Preview("Performer - Full Details") {
    NavigationStack {
        PerformerDetailView(performerId: "preview-performer-detail-1")
    }
}

#Preview("Performer - Minimal") {
    NavigationStack {
        PerformerDetailView(performerId: "preview-performer-detail-2")
    }
}

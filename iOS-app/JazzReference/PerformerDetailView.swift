//
//  PerformerDetailView.swift
//  JazzReference
//
//  Updated with JazzTheme color palette and ExternalReferencesPanel
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
                VStack {
                    Spacer()
                    ProgressView("Loading...")
                        .tint(JazzTheme.amber)
                    Spacer()
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(JazzTheme.backgroundLight)
            } else if let performer = performer {
                VStack(alignment: .leading, spacing: 0) {
                    // Styled Header with Jazz Theme
                    HStack {
                        Image(systemName: "person.fill")
                            .font(.title2)
                            .foregroundColor(JazzTheme.cream)
                        Text("ARTIST")
                            .font(.headline)
                            .fontWeight(.semibold)
                            .foregroundColor(JazzTheme.cream)
                        Spacer()
                    }
                    .padding()
                    .background(JazzTheme.amberGradient)
                    
                    VStack(alignment: .leading, spacing: 20) {
                        // Artist Name - MOVED TO TOP
                        Text(performer.name)
                            .font(.largeTitle)
                            .bold()
                            .foregroundColor(JazzTheme.charcoal)
                            .padding(.horizontal)
                            .padding(.top, 12)
                        
                        // Image Carousel - MOVED AFTER NAME
                        if let images = performer.images, !images.isEmpty {
                            ArtistImageCarousel(images: images)
                                .padding(.top, 8)
                        }
                        
                        // Performer Information - REST OF THE INFO
                        VStack(alignment: .leading, spacing: 12) {
                            if let birthDate = performer.birthDate {
                                HStack {
                                    Image(systemName: "calendar")
                                        .foregroundColor(JazzTheme.brass)
                                    Text("Born: \(birthDate.formatAsDate())")  // ← Added .formatAsDate()
                                        .font(.subheadline)
                                        .foregroundColor(JazzTheme.smokeGray)
                                }
                            }

                            if let deathDate = performer.deathDate {
                                HStack {
                                    Image(systemName: "calendar")
                                        .foregroundColor(JazzTheme.brass)
                                    Text("Died: \(deathDate.formatAsDate())")  // ← Added .formatAsDate()
                                        .font(.subheadline)
                                        .foregroundColor(JazzTheme.smokeGray)
                                }
                            }
                            if let biography = performer.biography {
                                VStack(alignment: .leading, spacing: 8) {
                                    Text("Biography")
                                        .font(.headline)
                                        .foregroundColor(JazzTheme.charcoal)
                                    Text(biography)
                                        .font(.body)
                                        .foregroundColor(JazzTheme.smokeGray)
                                }
                                .padding()
                                .background(JazzTheme.cardBackground)
                                .cornerRadius(10)
                            }
                            
                            if let instruments = performer.instruments, !instruments.isEmpty {
                                VStack(alignment: .leading, spacing: 8) {
                                    Text("Instruments")
                                        .font(.headline)
                                        .foregroundColor(JazzTheme.charcoal)
                                    
                                    ForEach(instruments, id: \.name) { instrument in
                                        HStack {
                                            Image(systemName: "music.note")
                                                .foregroundColor(JazzTheme.brass)
                                            Text(instrument.name)
                                                .font(.subheadline)
                                                .foregroundColor(JazzTheme.charcoal)
                                            if instrument.isPrimary == true {
                                                Text("(Primary)")
                                                    .font(.caption)
                                                    .foregroundColor(JazzTheme.smokeGray)
                                            }
                                        }
                                    }
                                }
                                .padding()
                                .background(JazzTheme.cardBackground)
                                .cornerRadius(10)
                            }
                            
                            // External References Panel
                            ExternalReferencesPanel(
                                externalLinks: performer.externalLinks,
                                entityId: performer.id,
                                entityName: performer.name
                            )
                        }
                        .padding()
                        
                        Divider()
                        
                        // Recordings Section
                        VStack(alignment: .leading, spacing: 12) {
                            Text("Recordings (\(filteredRecordings.count))")
                                .font(.title2)
                                .bold()
                                .foregroundColor(JazzTheme.charcoal)
                                .padding(.horizontal)
                            
                            // Filter Picker - styled with Jazz Theme
                            Picker("Filter", selection: $selectedFilter) {
                                ForEach(RecordingFilter.allCases, id: \.self) { filter in
                                    Text(filter.rawValue).tag(filter)
                                }
                            }
                            .pickerStyle(.segmented)
                            .padding(.horizontal)
                            .tint(JazzTheme.burgundy)
                            
                            if !filteredRecordings.isEmpty {
                                ForEach(filteredRecordings) { recording in
                                    NavigationLink(destination: RecordingDetailView(recordingId: recording.recordingId)) {
                                        PerformerRecordingRowView(recording: recording)
                                    }
                                    .buttonStyle(.plain)
                                }
                            } else {
                                Text("No recordings found")
                                    .foregroundColor(JazzTheme.smokeGray)
                                    .padding()
                            }
                        }
                    }
                }
                .padding(.vertical)
            } else {
                VStack {
                    Spacer()
                    Text("Performer not found")
                        .foregroundColor(JazzTheme.smokeGray)
                    Spacer()
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(JazzTheme.backgroundLight)
            }
        }
        .background(JazzTheme.backgroundLight)
        .navigationBarTitleDisplayMode(.inline)
        .toolbarBackground(JazzTheme.amber, for: .navigationBar)
        .toolbarBackground(.visible, for: .navigationBar)
        .toolbarColorScheme(.dark, for: .navigationBar)
        .task {
            #if DEBUG
            if ProcessInfo.processInfo.environment["XCODE_RUNNING_FOR_PREVIEWS"] == "1" {
                let networkManager = NetworkManager()
                performer = networkManager.fetchPerformerDetailSync(id: performerId)
                isLoading = false
                return
            }
            #endif
            
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
                    .foregroundColor(JazzTheme.gold)
                    .font(.subheadline)
                    .frame(width: 20)
            } else {
                Spacer()
                    .frame(width: 20)
            }
            
            VStack(alignment: .leading, spacing: 4) {
                // Song title
                Text(recording.songTitle)
                    .font(.headline)
                    .foregroundColor(JazzTheme.charcoal)
                    .lineLimit(1)
                
                // Album name
                if let albumTitle = recording.albumTitle {
                    Text(albumTitle)
                        .font(.subheadline)
                        .foregroundColor(JazzTheme.smokeGray)
                        .lineLimit(1)
                }
                
                // Role
                if let role = recording.role {
                    Text(role.capitalized)
                        .font(.caption)
                        .foregroundColor(JazzTheme.smokeGray)
                }
            }
            
            Spacer()
            
            // Year
            if let year = recording.recordingYear {
                Text(String(year))
                    .font(.subheadline)
                    .foregroundColor(JazzTheme.smokeGray)
                    .frame(minWidth: 40, alignment: .trailing)
            }
        }
        .padding(.vertical, 12)
        .padding(.horizontal, 16)
        .background(JazzTheme.cardBackground)
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

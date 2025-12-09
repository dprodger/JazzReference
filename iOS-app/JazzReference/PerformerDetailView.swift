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
    @State private var isBiographicalInfoExpanded = false
    @State private var searchText = ""
    
    private var filteredRecordings: [PerformerRecording] {
        guard let recordings = performer?.recordings else { return [] }
        
        var result: [PerformerRecording]
        
        switch selectedFilter {
        case .all:
            result = recordings
        case .leader:
            result = recordings.filter { $0.role?.lowercased() == "leader" }
        case .sideman:
            result = recordings.filter { $0.role?.lowercased() == "sideman" }
        }
        
        // Apply search filter
        if !searchText.isEmpty {
            let query = searchText.lowercased()
            result = result.filter { recording in
                recording.songTitle.lowercased().contains(query) ||
                (recording.albumTitle?.lowercased().contains(query) ?? false)
            }
        }
        
        return result
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
                            .font(JazzTheme.title2())
                            .foregroundColor(JazzTheme.cream)
                        Text("ARTIST")
                            .font(JazzTheme.headline())
                            .fontWeight(.semibold)
                            .foregroundColor(JazzTheme.cream)
                        Spacer()
                    }
                    .padding()
                    .background(JazzTheme.amberGradient)
                    
                    VStack(alignment: .leading, spacing: 20) {
                        // Artist Name - MOVED TO TOP
                        Text(performer.name)
                            .font(JazzTheme.largeTitle())
                            .bold()
                            .foregroundColor(JazzTheme.charcoal)
                            .padding(.horizontal)
                            .padding(.top, 12)
                        
                        // Image Carousel - MOVED AFTER NAME
                        if let images = performer.images, !images.isEmpty {
                            ArtistImageCarousel(images: images)
                                .padding(.top, 8)
                        }
                        
                        // Biographical Information Section - Expandable
                        VStack(alignment: .leading, spacing: 0) {
                            Button(action: {
                                withAnimation {
                                    isBiographicalInfoExpanded.toggle()
                                }
                            }) {
                                HStack {
                                    Text("Biographical Information")
                                        .font(JazzTheme.title2())
                                        .bold()
                                        .foregroundColor(JazzTheme.charcoal)
                                    Spacer()
                                    Image(systemName: isBiographicalInfoExpanded ? "chevron.up" : "chevron.down")
                                        .foregroundColor(JazzTheme.brass)
                                }
                                .padding()
                                .background(JazzTheme.cardBackground)
                            }
                            .buttonStyle(.plain)
                            
                            VStack(alignment: .leading, spacing: 12) {
                                // Always show biography preview
                                if let biography = performer.biography {
                                    let paragraphs = biography.components(separatedBy: "\n\n").filter { !$0.isEmpty }
                                    VStack(alignment: .leading, spacing: 12) {
                                        ForEach(Array(paragraphs.enumerated()), id: \.offset) { _, paragraph in
                                            Text(paragraph)
                                                .font(JazzTheme.body())
                                                .foregroundColor(JazzTheme.smokeGray)
                                        }
                                    }
                                    .lineLimit(isBiographicalInfoExpanded ? nil : 3)
                                    .padding(.horizontal)
                                    .padding(.top, 8)
                                }
                                
                                // Show details when expanded
                                if isBiographicalInfoExpanded {
                                    VStack(alignment: .leading, spacing: 12) {
                                        if let birthDate = performer.birthDate {
                                            HStack {
                                                Image(systemName: "calendar")
                                                    .foregroundColor(JazzTheme.brass)
                                                Text("Born: \(birthDate)")
                                                    .font(JazzTheme.subheadline())
                                                    .foregroundColor(JazzTheme.smokeGray)
                                            }
                                        }

                                        if let deathDate = performer.deathDate {
                                            HStack {
                                                Image(systemName: "calendar")
                                                    .foregroundColor(JazzTheme.brass)
                                                Text("Died: \(deathDate)")
                                                    .font(JazzTheme.subheadline())
                                                    .foregroundColor(JazzTheme.smokeGray)
                                            }
                                        }
                                        
                                        if let instruments = performer.instruments, !instruments.isEmpty {
                                            VStack(alignment: .leading, spacing: 8) {
                                                Text("Instruments")
                                                    .font(JazzTheme.headline())
                                                    .foregroundColor(JazzTheme.charcoal)
                                                
                                                ForEach(instruments, id: \.name) { instrument in
                                                    HStack {
                                                        Image(systemName: "music.note")
                                                            .foregroundColor(JazzTheme.brass)
                                                        Text(instrument.name)
                                                            .font(JazzTheme.subheadline())
                                                            .foregroundColor(JazzTheme.charcoal)
                                                        if instrument.isPrimary == true {
                                                            Text("(Primary)")
                                                                .font(JazzTheme.caption())
                                                                .foregroundColor(JazzTheme.smokeGray)
                                                        }
                                                    }
                                                }
                                            }
                                            .padding(.top, 8)
                                        }
                                        
                                        ExternalReferencesPanel(
                                            wikipediaUrl: performer.wikipediaUrl,
                                            musicbrainzId: performer.musicbrainzId,
                                            externalLinks: performer.externalLinks,
                                            entityId: performer.id,
                                            entityName: performer.name,
                                            isArtist: true
                                        )
                                        .padding(.top, 8)
                                    }
                                    .padding(.horizontal)
                                    .padding(.bottom, 12)
                                }
                            }
                        }
                        .background(JazzTheme.cardBackground)
                        .cornerRadius(10)
                        .padding(.horizontal)
                        .padding(.top, 8)
                        
                        Divider()
                        
                        // Recordings Section
                        VStack(alignment: .leading, spacing: 12) {
                            Text("Recordings (\(filteredRecordings.count))")
                                .font(JazzTheme.title2())
                                .bold()
                                .foregroundColor(JazzTheme.charcoal)
                                .padding(.horizontal)
                            
                            // Search Field
                            HStack {
                                Image(systemName: "magnifyingglass")
                                    .foregroundColor(JazzTheme.smokeGray)
                                TextField("Search recordings...", text: $searchText)
                                    .textFieldStyle(.plain)
                                if !searchText.isEmpty {
                                    Button(action: { searchText = "" }) {
                                        Image(systemName: "xmark.circle.fill")
                                            .foregroundColor(JazzTheme.smokeGray)
                                    }
                                }
                            }
                            .padding(10)
                            .background(JazzTheme.cardBackground)
                            .cornerRadius(8)
                            .overlay(
                                RoundedRectangle(cornerRadius: 8)
                                    .stroke(JazzTheme.smokeGray.opacity(0.3), lineWidth: 1)
                            )
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
        .jazzNavigationBar(title: performer?.name ?? "", color: JazzTheme.amber)
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
                    .font(JazzTheme.subheadline())
                    .frame(width: 20)
            } else {
                Spacer()
                    .frame(width: 20)
            }
            
            VStack(alignment: .leading, spacing: 4) {
                // Song title
                Text(recording.songTitle)
                    .font(JazzTheme.headline())
                    .foregroundColor(JazzTheme.charcoal)
                    .lineLimit(1)
                
                // Album name
                if let albumTitle = recording.albumTitle {
                    Text(albumTitle)
                        .font(JazzTheme.subheadline())
                        .foregroundColor(JazzTheme.smokeGray)
                        .lineLimit(1)
                }
                
                // Role
                if let role = recording.role {
                    Text(role.capitalized)
                        .font(JazzTheme.caption())
                        .foregroundColor(JazzTheme.smokeGray)
                }
            }
            
            Spacer()
            
            // Year
            if let year = recording.recordingYear {
                Text(String(year))
                    .font(JazzTheme.subheadline())
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

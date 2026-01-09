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
    @State private var recordingSortOrder: PerformerRecordingSortOrder = .year
    @State private var isRecordingsReloading = false

    // Two-phase loading: summary loads first (fast), then recordings load in background
    @State private var isRecordingsLoading: Bool = true
    
    var body: some View {
        ScrollView {
            if isLoading {
                VStack {
                    Spacer()
                    ThemedProgressView(message: "Loading...", tintColor: JazzTheme.amber)
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

                        // Recordings Section (mirrors SongDetailView layout)
                        PerformerRecordingsSection(
                            recordings: performer.recordings ?? [],
                            performerName: performer.name,
                            sortOrder: $recordingSortOrder,
                            selectedFilter: $selectedFilter,
                            isReloading: isRecordingsReloading || isRecordingsLoading,
                            onSortOrderChanged: { newOrder in
                                Task {
                                    isRecordingsReloading = true
                                    let networkManager = NetworkManager()
                                    if let recordings = await networkManager.fetchPerformerRecordings(id: performerId, sortBy: newOrder) {
                                        self.performer?.recordings = recordings
                                    }
                                    isRecordingsReloading = false
                                }
                            }
                        )
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
                isRecordingsLoading = false
                return
            }
            #endif

            let networkManager = NetworkManager()

            // Phase 1: Load summary (fast) - includes performer metadata, bio, instruments, images
            let fetchedPerformer = await networkManager.fetchPerformerSummary(id: performerId)
            await MainActor.run {
                performer = fetchedPerformer
                isLoading = false
            }

            // Phase 2: Load all recordings in background
            if let recordings = await networkManager.fetchPerformerRecordings(id: performerId, sortBy: recordingSortOrder) {
                await MainActor.run {
                    self.performer?.recordings = recordings
                    isRecordingsLoading = false
                }
            } else {
                await MainActor.run {
                    isRecordingsLoading = false
                }
            }
        }
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

//
//  AboutView.swift
//  JazzReference
//
//  About screen with splash screen background and visible navigation bar
//

import SwiftUI

struct AboutView: View {
    @State private var queueSize: Int = 0
    @State private var workerActive: Bool = false
    @State private var currentSongName: String? = nil
    @State private var progress: ResearchProgress? = nil
    @State private var isLoadingQueue: Bool = true
    @State private var isRefreshing: Bool = false
    @State private var rotationAngle: Double = 0
    
    let networkManager = NetworkManager()
    
    var body: some View {
        ZStack {
            // Background image
            Image("LaunchImage")
                .resizable()
                .scaledToFill()
                .ignoresSafeArea()
            
            // Vignette gradient overlay - darker at top and bottom for toolbar visibility
            LinearGradient(
                gradient: Gradient(colors: [
                    Color.black.opacity(0.75),  // Darker at top for navigation bar
                    Color.black.opacity(0.3),   // Lighter in middle
                    Color.black.opacity(0.85)   // Darkest at bottom for tab bar
                ]),
                startPoint: .top,
                endPoint: .bottom
            )
            .ignoresSafeArea()
            
            // Content
            VStack(spacing: 20) {
                Spacer()
                
                Text("Jazz Liner Notes")
                    .font(.system(size: 48, weight: .bold))
                    .foregroundColor(.white)
                    .shadow(color: .black.opacity(0.7), radius: 10, x: 0, y: 5)
                
                Text("Your comprehensive guide to jazz recordings")
                    .font(.title3)
                    .foregroundColor(.white)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 40)
                    .shadow(color: .black.opacity(0.7), radius: 5, x: 0, y: 2)
                
                Spacer()
                
                VStack(spacing: 12) {
                    Text("Explore thousands of jazz standards")
                        .font(.body)
                        .foregroundColor(.white)
                    
                    Text("Discover legendary artists and recordings")
                        .font(.body)
                        .foregroundColor(.white)
                    
                    Text("Build your jazz knowledge")
                        .font(.body)
                        .foregroundColor(.white)
                }
                .padding(.horizontal, 40)
                .shadow(color: .black.opacity(0.7), radius: 5, x: 0, y: 2)
                
                Spacer()
                
                // Research Queue Status
                VStack(spacing: 8) {
                    if isLoadingQueue && !isRefreshing {
                        ProgressView()
                            .tint(.white)
                    } else {
                        HStack(spacing: 6) {
                            Image(systemName: workerActive ? "arrow.triangle.2.circlepath" : "clock")
                                .foregroundColor(.white.opacity(0.9))
                                .font(.body)
                                .rotationEffect(.degrees(isRefreshing ? rotationAngle : 0))
                            
                            Text("Research Queue: \(queueSize)")
                                .font(.body)
                                .foregroundColor(.white.opacity(0.9))
                            
                            if isRefreshing {
                                ProgressView()
                                    .tint(.white)
                                    .scaleEffect(0.7)
                            }
                        }
                        
                        if workerActive && queueSize > 0 {
                            if let songName = currentSongName {
                                Text("Processing: \(songName)")
                                    .font(.caption)
                                    .foregroundColor(.white.opacity(0.9))
                                    .fontWeight(.medium)
                            } else {
                                Text("Processing...")
                                    .font(.caption)
                                    .foregroundColor(.white.opacity(0.7))
                                    .italic()
                            }
                            
                            // Progress indicator
                            if let progress = progress {
                                VStack(spacing: 4) {
                                    // Phase label with progress count
                                    HStack(spacing: 4) {
                                        Text(progress.phaseLabel)
                                            .font(.caption2)
                                            .foregroundColor(.white.opacity(0.7))
                                        
                                        Text("\(progress.current)/\(progress.total)")
                                            .font(.caption2)
                                            .foregroundColor(.white.opacity(0.9))
                                            .fontWeight(.medium)
                                    }
                                    
                                    // Progress bar
                                    GeometryReader { geometry in
                                        ZStack(alignment: .leading) {
                                            // Background track
                                            RoundedRectangle(cornerRadius: 2)
                                                .fill(Color.white.opacity(0.2))
                                                .frame(height: 4)
                                            
                                            // Progress fill
                                            RoundedRectangle(cornerRadius: 2)
                                                .fill(Color.white.opacity(0.8))
                                                .frame(width: geometry.size.width * progress.progressFraction, height: 4)
                                        }
                                    }
                                    .frame(height: 4)
                                }
                                .padding(.top, 4)
                            }
                        }
                        
                        // Tap to refresh hint
                        Text("Tap to refresh")
                            .font(.caption2)
                            .foregroundColor(.white.opacity(0.5))
                            .padding(.top, 2)
                    }
                }
                .padding(.vertical, 16)
                .padding(.horizontal, 24)
                .background(
                    RoundedRectangle(cornerRadius: 12)
                        .fill(Color.black.opacity(0.3))
                )
                .overlay(
                    RoundedRectangle(cornerRadius: 12)
                        .stroke(Color.white.opacity(0.2), lineWidth: 1)
                )
                .shadow(color: .black.opacity(0.5), radius: 5, x: 0, y: 2)
                .onTapGesture {
                    Task {
                        await refreshQueueStatus()
                    }
                }
                
                Spacer()
                
                Text("Version 1.0")
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.8))
                    .padding(.bottom, 10)

                Text("Written by Dave Rodger")
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.8))
                    .padding(.bottom, 10)
                
                Link("www.linernotesjazz.com", destination: URL(string: "https://www.linernotesjazz.com")!)
                    .font(.caption)
                    .tint(.white.opacity(0.8))
                    .padding(.bottom, 40)
            }
        }
        .navigationBarTitleDisplayMode(.inline)
        .toolbarBackground(JazzTheme.burgundy, for: .navigationBar)
        .toolbarBackground(.visible, for: .navigationBar)
        .toolbarColorScheme(.dark, for: .navigationBar)
        .task {
            await loadQueueStatus()
        }
    }
    
    private func loadQueueStatus() async {
        if let status = await networkManager.fetchQueueStatus() {
            queueSize = status.queueSize
            workerActive = status.workerActive
            currentSongName = status.currentSong?.songName
            progress = status.progress
        }
        isLoadingQueue = false
    }
    
    private func refreshQueueStatus() async {
        guard !isRefreshing else { return }
        
        isRefreshing = true
        
        // Start rotation animation
        withAnimation(.linear(duration: 1).repeatForever(autoreverses: false)) {
            rotationAngle = 360
        }
        
        if let status = await networkManager.fetchQueueStatus() {
            queueSize = status.queueSize
            workerActive = status.workerActive
            currentSongName = status.currentSong?.songName
            progress = status.progress
        }
        
        // Stop animation
        withAnimation(.linear(duration: 0.1)) {
            rotationAngle = 0
        }
        isRefreshing = false
    }
}

#Preview {
    NavigationStack {
        AboutView()
    }
}

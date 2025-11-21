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
    @State private var isLoadingQueue: Bool = true
    
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
                    if isLoadingQueue {
                        ProgressView()
                            .tint(.white)
                    } else {
                        HStack(spacing: 6) {
                            Image(systemName: workerActive ? "arrow.triangle.2.circlepath" : "clock")
                                .foregroundColor(.white.opacity(0.9))
                                .font(.body)
                            
                            Text("Research Queue: \(queueSize)")
                                .font(.body)
                                .foregroundColor(.white.opacity(0.9))
                        }
                        
                        if workerActive && queueSize > 0 {
                            Text("Processing...")
                                .font(.caption)
                                .foregroundColor(.white.opacity(0.7))
                                .italic()
                        }
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
        }
        isLoadingQueue = false
    }
}

#Preview {
    NavigationStack {
        AboutView()
    }
}

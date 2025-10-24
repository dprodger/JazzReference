//
//  AboutView.swift
//  JazzReference
//
//  About screen with splash screen background and visible navigation bar
//

import SwiftUI

struct AboutView: View {
    var body: some View {
        ZStack {
            // Background image
            Image("LaunchImage")
                .resizable()
                .scaledToFill()
                .ignoresSafeArea()
            
            // Semi-transparent overlay for better text readability
            Color.black.opacity(0.4)
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
                
                Text("Version 1.0")
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.8))
                    .padding(.bottom, 40)

                Text("Written by Dave Rodger")
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.8))
                    .padding(.bottom, 10)
                
                Link("www.linernotesjazz.com", destination: URL(string: "linernotesjazz.com")!)
                    .font(.caption)
                    .tint(.white.opacity(0.8))
                    .padding(.bottom, 40)

            }
        }
        .navigationBarTitleDisplayMode(.inline)
        .toolbarBackground(JazzTheme.burgundy, for: .navigationBar)
        .toolbarBackground(.visible, for: .navigationBar)
        .toolbarColorScheme(.dark, for: .navigationBar)
    }
}

#Preview {
    NavigationStack {
        AboutView()
    }
}

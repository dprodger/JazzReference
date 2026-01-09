//
//  OnboardingView.swift
//  JazzReference
//
//  Created by Dave Rodger on 12/4/25.
//  Onboarding flow for first-time users explaining Songs, Recordings, and Releases
//

import SwiftUI

struct OnboardingView: View {
    @Binding var isPresented: Bool
    @State private var currentPage = 0

    private let totalPages = 5

    var body: some View {
        ZStack {
            // Background
            JazzTheme.backgroundLight
                .ignoresSafeArea()

            VStack(spacing: 0) {
                // Page content
                TabView(selection: $currentPage) {
                    OnboardingWelcomePage()
                        .tag(0)

                    OnboardingSongPage()
                        .tag(1)

                    OnboardingRecordingPage()
                        .tag(2)

                    OnboardingReleasesPage()
                        .tag(3)

                    OnboardingCompletionPage(onFinish: { isPresented = false })
                        .tag(4)
                }
                .tabViewStyle(.page(indexDisplayMode: .never))
                .animation(.easeInOut, value: currentPage)

                // Navigation controls
                VStack(spacing: 16) {
                    // Page indicators
                    HStack(spacing: 8) {
                        ForEach(0..<totalPages, id: \.self) { index in
                            Circle()
                                .fill(index == currentPage ? JazzTheme.burgundy : JazzTheme.smokeGray.opacity(0.4))
                                .frame(width: 8, height: 8)
                        }
                    }
                    .padding(.bottom, 8)

                    // Navigation buttons
                    HStack {
                        if currentPage > 0 {
                            Button(action: {
                                withAnimation {
                                    currentPage -= 1
                                }
                            }) {
                                HStack {
                                    Image(systemName: "chevron.left")
                                    Text("Back")
                                }
                                .foregroundColor(JazzTheme.smokeGray)
                            }
                        } else {
                            Spacer()
                                .frame(width: 80)
                        }

                        Spacer()

                        if currentPage < totalPages - 1 {
                            Button(action: {
                                withAnimation {
                                    currentPage += 1
                                }
                            }) {
                                HStack {
                                    Text("Next")
                                    Image(systemName: "chevron.right")
                                }
                                .foregroundColor(JazzTheme.burgundy)
                                .fontWeight(.semibold)
                            }
                        } else {
                            Spacer()
                                .frame(width: 80)
                        }
                    }
                    .padding(.horizontal, 32)
                }
                .padding(.bottom, 40)
            }

            // Skip button (top right)
            VStack {
                HStack {
                    Spacer()
                    Button("Skip") {
                        isPresented = false
                    }
                    .foregroundColor(JazzTheme.smokeGray)
                    .padding()
                }
                Spacer()
            }
        }
    }
}

// MARK: - Preview

#Preview {
    OnboardingView(isPresented: .constant(true))
}

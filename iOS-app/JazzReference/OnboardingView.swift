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
                    WelcomePage()
                        .tag(0)
                    
                    SongPage()
                        .tag(1)
                    
                    RecordingPage()
                        .tag(2)
                    
                    ReleasesPage()
                        .tag(3)
                    
                    CompletionPage(onFinish: { isPresented = false })
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

// MARK: - Page 1: Welcome

private struct WelcomePage: View {
    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                Spacer()
                    .frame(height: 60)
                
                // Icon
                Image(systemName: "music.note.list")
                    .font(.system(size: 60))
                    .foregroundColor(JazzTheme.burgundy)
                
                Text("Welcome!")
                    .font(.largeTitle)
                    .fontWeight(.bold)
                    .foregroundColor(JazzTheme.charcoal)
                
                VStack(spacing: 16) {
                    Text("Thanks for checking out Approach Note.")
                        .font(.title3)
                        .multilineTextAlignment(.center)
                    
                    Text("I'm going to give you a brief description of what is available here so you can get yourself oriented.")
                        .multilineTextAlignment(.center)
                    
                    Text("You can always re-run this tutorial by going to the About section and tapping \"View Tutorial\".")
                        .font(.callout)
                        .foregroundColor(JazzTheme.smokeGray)
                        .multilineTextAlignment(.center)
                }
                .foregroundColor(JazzTheme.charcoal)
                .padding(.horizontal, 32)
                
                Spacer()
                    .frame(height: 40)
                
                // Decorative element
                VStack(spacing: 12) {
                    Image(systemName: "info.circle")
                        .font(.title2)
                        .foregroundColor(JazzTheme.amber)
                    
                    Text("When it comes to music, the data are complicated.\nI'll walk you through the definitions.")
                        .font(.body)
                        .italic()
                        .multilineTextAlignment(.center)
                        .foregroundColor(JazzTheme.smokeGray)
                }
                .padding(.horizontal, 32)
                
                Spacer()
            }
        }
    }
}

// MARK: - Page 2: Songs

private struct SongPage: View {
    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                Spacer()
                    .frame(height: 60)
                
                // Icon with label
                VStack(spacing: 8) {
                    Image(systemName: "music.note")
                        .font(.system(size: 50))
                        .foregroundColor(JazzTheme.burgundy)
                    
                    Text("Song")
                        .font(.largeTitle)
                        .fontWeight(.bold)
                        .foregroundColor(JazzTheme.charcoal)
                }
                
                VStack(alignment: .leading, spacing: 16) {
                    Text("When Gerald Marks and Seymour Simons sat down in 1932 to write ")
                    + Text("All of Me")
                        .italic()
                    + Text(", they were creating a ")
                    + Text("Song")
                        .fontWeight(.semibold)
                    + Text(".")
                    
                    Text("This can sometimes be called a Work, or a Composition.")
                        .foregroundColor(JazzTheme.smokeGray)
                    
                    Text("But it's the basic chords, melody, and (if appropriate) lyrics of a particular written piece of music.")
                }
                .font(.body)
                .foregroundColor(JazzTheme.charcoal)
                .multilineTextAlignment(.leading)
                .padding(.horizontal, 32)
                
                Spacer()
                    .frame(height: 40)
                
                // Visual representation
                VStack(spacing: 8) {
                    HStack(spacing: 12) {
                        Image(systemName: "pianokeys")
                        Image(systemName: "plus")
                            .font(.caption)
                        Image(systemName: "waveform")
                        Image(systemName: "plus")
                            .font(.caption)
                        Image(systemName: "text.alignleft")
                    }
                    .font(.title2)
                    .foregroundColor(JazzTheme.brass)
                    
                    Text("Chords + Melody + Lyrics")
                        .font(.caption)
                        .foregroundColor(JazzTheme.smokeGray)
                }
                .padding()
                .background(
                    RoundedRectangle(cornerRadius: 12)
                        .fill(JazzTheme.cardBackground)
                )
                .padding(.horizontal, 32)
                
                Spacer()
            }
        }
    }
}

// MARK: - Page 3: Recordings

private struct RecordingPage: View {
    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                Spacer()
                    .frame(height: 60)
                
                // Icon with label
                VStack(spacing: 8) {
                    Image(systemName: "opticaldisc")
                        .font(.system(size: 50))
                        .foregroundColor(JazzTheme.brass)
                    
                    Text("Recording")
                        .font(.largeTitle)
                        .fontWeight(.bold)
                        .foregroundColor(JazzTheme.charcoal)
                }
                
                VStack(alignment: .leading, spacing: 16) {
                    Text("When Count Basie and his orchestra got together in November 1941 to play this song and commit it to media, that generated this ")
                    + Text("Recording")
                        .fontWeight(.semibold)
                    + Text(".")
                    
                    Text("The lineup for this recording is what it was on that date & time.")
                        .foregroundColor(JazzTheme.smokeGray)
                }
                .font(.body)
                .foregroundColor(JazzTheme.charcoal)
                .multilineTextAlignment(.leading)
                .padding(.horizontal, 32)
                
                Spacer()
                    .frame(height: 40)
                
                // Visual representation
                VStack(spacing: 12) {
                    HStack {
                        Image(systemName: "person.3.fill")
                            .foregroundColor(JazzTheme.amber)
                        Text("+")
                            .foregroundColor(JazzTheme.smokeGray)
                        Image(systemName: "music.note")
                            .foregroundColor(JazzTheme.burgundy)
                        Text("+")
                            .foregroundColor(JazzTheme.smokeGray)
                        Image(systemName: "calendar")
                            .foregroundColor(JazzTheme.teal)
                    }
                    .font(.title2)
                    
                    Text("Artists + Song + Date")
                        .font(.caption)
                        .foregroundColor(JazzTheme.smokeGray)
                }
                .padding()
                .background(
                    RoundedRectangle(cornerRadius: 12)
                        .fill(JazzTheme.cardBackground)
                )
                .padding(.horizontal, 32)
                
                Spacer()
            }
        }
    }
}

// MARK: - Page 4: Releases

private struct ReleasesPage: View {
    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                Spacer()
                    .frame(height: 40)
                
                // Icon with label
                VStack(spacing: 8) {
                    Image(systemName: "shippingbox")
                        .font(.system(size: 50))
                        .foregroundColor(JazzTheme.teal)
                    
                    Text("Releases")
                        .font(.largeTitle)
                        .fontWeight(.bold)
                        .foregroundColor(JazzTheme.charcoal)
                }
                
                VStack(alignment: .leading, spacing: 16) {
                    Text("The music industry being what it is, here's where it gets complicated.")
                        .foregroundColor(JazzTheme.smokeGray)
                    
                    Text("That recording was issued to the public on a ")
                    + Text("Release")
                        .fontWeight(.semibold)
                    + Text(". The release is a piece of commercial product (vinyl, CD, cassette, streaming) that was put into the world by a label.")
                    
                    Text("The same piece of audio often appears on multiple releases.")
                        .fontWeight(.medium)
                }
                .font(.body)
                .foregroundColor(JazzTheme.charcoal)
                .multilineTextAlignment(.leading)
                .padding(.horizontal, 32)
                
                // Formats visualization
                HStack(spacing: 16) {
                    ForEach(["opticaldisc", "record.circle", "play.rectangle.fill"], id: \.self) { icon in
                        Image(systemName: icon)
                            .font(.title)
                            .foregroundColor(JazzTheme.teal)
                    }
                }
                .padding(.vertical, 8)
                
                VStack(alignment: .leading, spacing: 12) {
                    Text("If you care about hearing the specific version (or Recording) of that song, it doesn't matter too much what Release it's on — they should sound the same.")
                        .font(.callout)
                    
                    Text("(Remastering, etc., may be counted as a separate release or may not.)")
                        .font(.caption)
                        .foregroundColor(JazzTheme.smokeGray)
                    
                    Text("Oftentimes, releases are restricted by geographic region; or they may no longer be available at all.")
                        .font(.callout)
                }
                .foregroundColor(JazzTheme.charcoal)
                .padding(.horizontal, 32)
                
                // Key insight box
                VStack(spacing: 8) {
                    Image(systemName: "lightbulb.fill")
                        .foregroundColor(JazzTheme.gold)
                    
                    Text("For our purposes, if we can find any Release of the same Recording, we can treat them interchangeably from a playback and lineup perspective.")
                        .font(.callout)
                        .italic()
                        .multilineTextAlignment(.center)
                        .foregroundColor(JazzTheme.charcoal)
                }
                .padding()
                .background(
                    RoundedRectangle(cornerRadius: 12)
                        .fill(JazzTheme.cardBackground)
                )
                .padding(.horizontal, 32)
                
                Spacer()
            }
        }
    }
}

// MARK: - Page 5: Completion

private struct CompletionPage: View {
    let onFinish: () -> Void
    
    var body: some View {
        VStack(spacing: 32) {
            Spacer()
            
            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 80))
                .foregroundColor(JazzTheme.burgundy)
            
            Text("You're All Set!")
                .font(.largeTitle)
                .fontWeight(.bold)
                .foregroundColor(JazzTheme.charcoal)
            
            Text("So, there you have it in a nutshell.")
                .font(.title3)
                .foregroundColor(JazzTheme.charcoal)
            
            Text("Enjoy!")
                .font(.title2)
                .fontWeight(.semibold)
                .foregroundColor(JazzTheme.burgundy)
            
            Spacer()
            
            Button(action: onFinish) {
                Text("Get Started")
                    .font(.headline)
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(JazzTheme.burgundy)
                    .cornerRadius(12)
            }
            .padding(.horizontal, 32)
            
            Spacer()
                .frame(height: 60)
        }
    }
}

// MARK: - Preview

#Preview {
    OnboardingView(isPresented: .constant(true))
}

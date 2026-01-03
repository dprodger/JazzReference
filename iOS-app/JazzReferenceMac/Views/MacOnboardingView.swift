//
//  MacOnboardingView.swift
//  JazzReferenceMac
//
//  Onboarding flow for first-time Mac users explaining Songs, Recordings, and Releases
//

import SwiftUI

struct MacOnboardingView: View {
    @Binding var isPresented: Bool
    @State private var currentPage = 0

    private let totalPages = 5

    var body: some View {
        VStack(spacing: 0) {
            // Page content
            Group {
                switch currentPage {
                case 0:
                    WelcomePage()
                case 1:
                    SongPage()
                case 2:
                    RecordingPage()
                case 3:
                    ReleasesPage()
                case 4:
                    CompletionPage(onFinish: { isPresented = false })
                default:
                    EmptyView()
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)

            Divider()

            // Navigation controls
            HStack {
                // Back button
                Button(action: {
                    withAnimation {
                        currentPage -= 1
                    }
                }) {
                    HStack(spacing: 4) {
                        Image(systemName: "chevron.left")
                        Text("Back")
                    }
                }
                .buttonStyle(.plain)
                .foregroundColor(JazzTheme.smokeGray)
                .opacity(currentPage > 0 ? 1 : 0)
                .disabled(currentPage == 0)

                Spacer()

                // Page indicators
                HStack(spacing: 8) {
                    ForEach(0..<totalPages, id: \.self) { index in
                        Circle()
                            .fill(index == currentPage ? JazzTheme.burgundy : JazzTheme.smokeGray.opacity(0.4))
                            .frame(width: 8, height: 8)
                    }
                }

                Spacer()

                // Next/Skip button
                if currentPage < totalPages - 1 {
                    Button(action: {
                        withAnimation {
                            currentPage += 1
                        }
                    }) {
                        HStack(spacing: 4) {
                            Text("Next")
                            Image(systemName: "chevron.right")
                        }
                    }
                    .buttonStyle(.plain)
                    .foregroundColor(JazzTheme.burgundy)
                    .fontWeight(.semibold)
                } else {
                    // Invisible placeholder to balance layout
                    Text("Next")
                        .opacity(0)
                }
            }
            .padding(.horizontal, 24)
            .padding(.vertical, 16)
            .background(JazzTheme.cardBackground)
        }
        .frame(width: 600, height: 500)
        .background(JazzTheme.backgroundLight)
        .toolbar {
            ToolbarItem(placement: .cancellationAction) {
                Button("Skip") {
                    isPresented = false
                }
            }
        }
    }
}

// MARK: - Page 1: Welcome

private struct WelcomePage: View {
    var body: some View {
        VStack(spacing: 24) {
            Spacer()

            // Icon
            Image(systemName: "music.note.list")
                .font(.system(size: 60))
                .foregroundColor(JazzTheme.burgundy)

            Text("Welcome!")
                .font(JazzTheme.largeTitle())
                .foregroundColor(JazzTheme.charcoal)

            VStack(spacing: 16) {
                Text("Thanks for checking out Approach Note.")
                    .font(JazzTheme.title3())
                    .multilineTextAlignment(.center)

                Text("I'm going to give you a brief description of what is available here so you can get yourself oriented.")
                    .font(JazzTheme.body())
                    .foregroundColor(JazzTheme.smokeGray)
                    .multilineTextAlignment(.center)

                Text("You can always re-run this tutorial from Settings.")
                    .font(JazzTheme.body())
                    .foregroundColor(JazzTheme.smokeGray)
                    .multilineTextAlignment(.center)
            }
            .foregroundColor(JazzTheme.charcoal)
            .padding(.horizontal, 48)

            Spacer()

            // Decorative element
            VStack(spacing: 12) {
                Image(systemName: "info.circle")
                    .font(JazzTheme.title2())
                    .foregroundColor(JazzTheme.amber)

                Text("When it comes to music, the data are complicated.\nI'll walk you through the definitions.")
                    .font(JazzTheme.body())
                    .italic()
                    .multilineTextAlignment(.center)
                    .foregroundColor(JazzTheme.smokeGray)
            }
            .padding(.horizontal, 48)

            Spacer()
        }
        .padding()
    }
}

// MARK: - Page 2: Songs

private struct SongPage: View {
    var body: some View {
        VStack(spacing: 24) {
            Spacer()

            // Icon with label
            VStack(spacing: 8) {
                Image(systemName: "music.note")
                    .font(.system(size: 50))
                    .foregroundColor(JazzTheme.burgundy)

                Text("Song")
                    .font(JazzTheme.largeTitle())
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
                    .foregroundColor(JazzTheme.smokeGray)
            }
            .font(JazzTheme.body())
            .foregroundColor(JazzTheme.charcoal)
            .multilineTextAlignment(.leading)
            .padding(.horizontal, 48)

            Spacer()

            // Visual representation
            VStack(spacing: 8) {
                HStack(spacing: 12) {
                    Image(systemName: "pianokeys")
                    Image(systemName: "plus")
                        .font(JazzTheme.caption())
                    Image(systemName: "waveform")
                    Image(systemName: "plus")
                        .font(JazzTheme.caption())
                    Image(systemName: "text.alignleft")
                }
                .font(JazzTheme.title2())
                .foregroundColor(JazzTheme.brass)

                Text("Chords + Melody + Lyrics")
                    .font(JazzTheme.caption())
                    .foregroundColor(JazzTheme.smokeGray)
            }
            .padding()
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(JazzTheme.cardBackground)
            )

            Spacer()
        }
        .padding()
    }
}

// MARK: - Page 3: Recordings

private struct RecordingPage: View {
    var body: some View {
        VStack(spacing: 24) {
            Spacer()

            // Icon with label
            VStack(spacing: 8) {
                Image(systemName: "opticaldisc")
                    .font(.system(size: 50))
                    .foregroundColor(JazzTheme.brass)

                Text("Recording")
                    .font(JazzTheme.largeTitle())
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
            .font(JazzTheme.body())
            .foregroundColor(JazzTheme.charcoal)
            .multilineTextAlignment(.leading)
            .padding(.horizontal, 48)

            Spacer()

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
                .font(JazzTheme.title2())

                Text("Artists + Song + Date")
                    .font(JazzTheme.caption())
                    .foregroundColor(JazzTheme.smokeGray)
            }
            .padding()
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(JazzTheme.cardBackground)
            )

            Spacer()
        }
        .padding()
    }
}

// MARK: - Page 4: Releases

private struct ReleasesPage: View {
    var body: some View {
        VStack(spacing: 20) {
            Spacer()

            // Icon with label
            VStack(spacing: 8) {
                Image(systemName: "shippingbox")
                    .font(.system(size: 50))
                    .foregroundColor(JazzTheme.teal)

                Text("Releases")
                    .font(JazzTheme.largeTitle())
                    .foregroundColor(JazzTheme.charcoal)
            }

            VStack(alignment: .leading, spacing: 12) {
                Text("The music industry being what it is, here's where it gets complicated.")

                Text("That recording was issued to the public on a ")
                + Text("Release")
                    .fontWeight(.semibold)
                + Text(". The release is a piece of commercial product (vinyl, CD, cassette, streaming) that was put into the world by a label.")

                Text("The same piece of audio often appears on multiple releases.")
            }
            .font(JazzTheme.body())
            .foregroundColor(JazzTheme.smokeGray)
            .multilineTextAlignment(.leading)
            .padding(.horizontal, 48)

            // Formats visualization
            HStack(spacing: 16) {
                ForEach(["opticaldisc", "record.circle", "play.rectangle.fill"], id: \.self) { icon in
                    Image(systemName: icon)
                        .font(JazzTheme.title())
                        .foregroundColor(JazzTheme.teal)
                }
            }

            // Key insight box
            VStack(spacing: 8) {
                Image(systemName: "lightbulb.fill")
                    .foregroundColor(JazzTheme.gold)

                Text("For our purposes, if we can find any Release of the same Recording, we can treat them interchangeably from a playback and lineup perspective.")
                    .font(JazzTheme.callout())
                    .italic()
                    .multilineTextAlignment(.center)
                    .foregroundColor(JazzTheme.charcoal)
            }
            .padding()
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(JazzTheme.cardBackground)
            )
            .padding(.horizontal, 48)

            Spacer()
        }
        .padding()
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
                .font(JazzTheme.largeTitle())
                .foregroundColor(JazzTheme.charcoal)

            Text("So, there you have it in a nutshell.")
                .font(JazzTheme.title3())
                .foregroundColor(JazzTheme.charcoal)

            Text("Enjoy!")
                .font(JazzTheme.title2())
                .foregroundColor(JazzTheme.burgundy)

            Spacer()

            Button(action: onFinish) {
                Text("Get Started")
                    .font(JazzTheme.headline())
                    .foregroundColor(.white)
                    .frame(width: 200)
                    .padding()
                    .background(JazzTheme.burgundy)
                    .cornerRadius(12)
            }
            .buttonStyle(.plain)

            Spacer()
        }
        .padding()
    }
}

// MARK: - Preview

#Preview {
    MacOnboardingView(isPresented: .constant(true))
}

//
//  JazzTheme.swift
//  JazzReference
//
//  Centralized color theme inspired by jazz nightclubs and speakeasies
//

import SwiftUI

struct JazzTheme {
    // MARK: - Primary Colors
    
    /// Deep burgundy - main accent color
    static let burgundy = Color(red: 0.45, green: 0.15, blue: 0.15) // #731A1A
    
    /// Warm amber - secondary accent
    static let amber = Color(red: 0.85, green: 0.55, blue: 0.25) // #D98C3F
    
    /// Smoky brass - tertiary accent
    static let brass = Color(red: 0.65, green: 0.50, blue: 0.30) // #A67F4D
    
    /// Deep teal - cool accent
    static let teal = Color(red: 0.20, green: 0.35, blue: 0.40) // #335966
    
    // MARK: - Neutrals
    
    /// Rich charcoal - primary text on light backgrounds
    static let charcoal = Color(red: 0.15, green: 0.15, blue: 0.15) // #262626
    
    /// Warm cream - text on dark backgrounds
    static let cream = Color(red: 0.95, green: 0.93, blue: 0.88) // #F2EDE0
    
    /// Muted gray - secondary text
    static let smokeGray = Color(red: 0.55, green: 0.52, blue: 0.48) // #8C857A
    
    // MARK: - Special
    
    /// Gold star - for canonical recordings
    static let gold = Color(red: 0.85, green: 0.65, blue: 0.13) // #D9A521
    
    // MARK: - Gradients
    
    static let burgundyGradient = LinearGradient(
        gradient: Gradient(colors: [burgundy, burgundy.opacity(0.8)]),
        startPoint: .leading,
        endPoint: .trailing
    )
    
    static let amberGradient = LinearGradient(
        gradient: Gradient(colors: [amber, amber.opacity(0.8)]),
        startPoint: .leading,
        endPoint: .trailing
    )
    
    static let brassGradient = LinearGradient(
        gradient: Gradient(colors: [brass, brass.opacity(0.8)]),
        startPoint: .leading,
        endPoint: .trailing
    )
    
    static let tealGradient = LinearGradient(
        gradient: Gradient(colors: [teal, teal.opacity(0.8)]),
        startPoint: .leading,
        endPoint: .trailing
    )
    
    // MARK: - Background Colors
    
    /// Light warm background
    static let backgroundLight = Color(red: 0.97, green: 0.95, blue: 0.92) // #F7F2EB
    
    /// Card background
    static let cardBackground = Color(red: 0.93, green: 0.91, blue: 0.87) // #EDE8DD
    
    // MARK: - Section Headers by Type
    
    struct SectionHeader {
        let gradient: LinearGradient
        let icon: String
        
        static let song = SectionHeader(
            gradient: burgundyGradient,
            icon: "music.note"
        )
        
        static let recording = SectionHeader(
            gradient: brassGradient,
            icon: "opticaldisc"
        )
        
        static let artist = SectionHeader(
            gradient: amberGradient,
            icon: "person.fill"
        )
    }
}

// MARK: - View Extension for Easy Access

extension View {
    func jazzThemedSectionHeader(title: String, type: JazzTheme.SectionHeader) -> some View {
        HStack {
            Image(systemName: type.icon)
                .font(.title2)
                .foregroundColor(JazzTheme.cream)
            Text(title)
                .font(.headline)
                .fontWeight(.semibold)
                .foregroundColor(JazzTheme.cream)
            Spacer()
        }
        .padding()
        .background(type.gradient)
    }
}

// MARK: - Usage Examples

struct JazzThemePreview: View {
    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                // Song Header
                VStack {
                    Text("SONG")
                        .font(.headline)
                        .fontWeight(.semibold)
                        .foregroundColor(JazzTheme.cream)
                }
                .frame(maxWidth: .infinity)
                .padding()
                .background(JazzTheme.SectionHeader.song.gradient)
                
                // Recording Header
                VStack {
                    Text("RECORDING")
                        .font(.headline)
                        .fontWeight(.semibold)
                        .foregroundColor(JazzTheme.cream)
                }
                .frame(maxWidth: .infinity)
                .padding()
                .background(JazzTheme.SectionHeader.recording.gradient)
                
                // Artist Header
                VStack {
                    Text("ARTIST")
                        .font(.headline)
                        .fontWeight(.semibold)
                        .foregroundColor(JazzTheme.cream)
                }
                .frame(maxWidth: .infinity)
                .padding()
                .background(JazzTheme.SectionHeader.artist.gradient)
                
                // Color Swatches
                VStack(alignment: .leading, spacing: 16) {
                    Text("Color Palette")
                        .font(.title2)
                        .bold()
                    
                    ColorSwatch(name: "Burgundy", color: JazzTheme.burgundy)
                    ColorSwatch(name: "Amber", color: JazzTheme.amber)
                    ColorSwatch(name: "Brass", color: JazzTheme.brass)
                    ColorSwatch(name: "Teal", color: JazzTheme.teal)
                    ColorSwatch(name: "Gold (Star)", color: JazzTheme.gold)
                    ColorSwatch(name: "Charcoal", color: JazzTheme.charcoal)
                    ColorSwatch(name: "Cream", color: JazzTheme.cream, darkBackground: true)
                    ColorSwatch(name: "Smoke Gray", color: JazzTheme.smokeGray)
                }
                .padding()
            }
        }
        .background(JazzTheme.backgroundLight)
    }
}

struct ColorSwatch: View {
    let name: String
    let color: Color
    var darkBackground: Bool = false
    
    var body: some View {
        HStack {
            RoundedRectangle(cornerRadius: 8)
                .fill(color)
                .frame(width: 60, height: 60)
                .overlay(
                    RoundedRectangle(cornerRadius: 8)
                        .stroke(Color.gray.opacity(0.3), lineWidth: 1)
                )
            
            VStack(alignment: .leading) {
                Text(name)
                    .font(.headline)
                Text(darkBackground ? "For dark backgrounds" : "Primary use")
                    .font(.caption)
                    .foregroundColor(JazzTheme.smokeGray)
            }
            Spacer()
        }
    }
}

#Preview {
    JazzThemePreview()
}

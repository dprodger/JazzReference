# JazzReferenceMac - Future Enhancements

Potential improvements for the macOS app.

## UI Polish

- [ ] **App Icon** - Add icon images to `Assets.xcassets/AppIcon.appiconset` (sizes: 16, 32, 128, 256, 512 @1x and @2x)

## macOS-Specific Features

- [ ] **Keyboard Navigation** - List selection already works with arrow keys; consider adding more shortcuts

- [ ] **Touch Bar Support** - Quick controls for MacBook Pro with Touch Bar

- [ ] **Menu Bar Extras** - Quick access to search or recent items from the menu bar

- [ ] **Spotlight Integration** - Index songs/artists for system-wide search using Core Spotlight

- [ ] **Multiple Windows** - Allow opening songs/artists in separate windows (`@Environment(\.openWindow)`)

- [ ] **Drag & Drop** - Drag songs to create playlists or export data

## Authentication

- [ ] **Login UI** - Implement macOS-native login/register views (framework is in place via shared AuthenticationManager)

- [ ] **Google Sign-In for macOS** - Add macOS-specific Google authentication if needed

- [ ] **Keychain Integration** - Already working; consider adding Keychain Access Group for sharing with iOS

## Data & Sync

- [ ] **Offline Support** - Cache songs/recordings for offline browsing

- [ ] **iCloud Sync** - Sync repertoires across devices via CloudKit

## Distribution

- [ ] **Notarization** - Required for distribution outside Mac App Store

- [ ] **Mac App Store** - Prepare for App Store submission (screenshots, metadata)

- [ ] **Sparkle Updates** - Add auto-update framework for direct distribution

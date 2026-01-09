# iOS/Mac Code Sharing Assessment

**Date:** 2026-01-03

This document assesses the current code sharing between the iOS and Mac apps and outlines strategies for potential refactoring.

## Current Architecture

### Project Structure

Single Xcode project with multiple targets:
- `Approach Note` (iOS app) - 44 Swift files
- `Approach Note Mac` (macOS app) - 18 Swift files
- `MusicBrainzImporter` (share extension)

```
apps/
├── iOS/                     # iOS app source + shared files
│   ├── Support_Files/       # Shared: Models, NetworkManager, JazzTheme
│   ├── Auth/                # Shared managers, iOS-specific views
│   └── *.swift              # iOS views and managers
├── Mac/                     # Mac app source
│   └── Views/               # Mac-specific views
├── Shared/                  # Currently empty (placeholder)
└── MusicBrainzImporter/     # Share extension
```

### What's Already Shared

| File | Purpose |
|------|---------|
| `Models.swift` | All data structures (Song, Recording, Artist, etc.) |
| `NetworkManager.swift` | API client with async/await |
| `JazzTheme.swift` | Colors, fonts, styling constants |
| `AuthenticationManager.swift` | JWT auth, login/register logic |
| `KeychainHelper.swift` | Secure credential storage |
| `RepertoireManager.swift` | Repertoire state management |
| `FavoritesManager.swift` | Favorites management |

### What's Duplicated

| Area | iOS | Mac | Similarity |
|------|-----|-----|------------|
| Auth Views | 4 files (~600 lines) | 4 files (~600 lines) | ~95% |
| Detail Views | ~1,900 lines | ~1,772 lines | ~60-70% |
| List Views | Multiple files | Simpler versions | ~50% |
| Repertoire Sheets | 2 files | 2 files | ~80% |

#### Auth View Duplication (High - ~95% similar)
- `LoginView.swift` ↔ `MacLoginView.swift`
- `RegisterView.swift` ↔ `MacRegisterView.swift`
- `ForgotPasswordView.swift` ↔ `MacForgotPasswordView.swift`
- `ResetPasswordView.swift` ↔ `MacResetPasswordView.swift`

#### Detail View Duplication (Moderate - ~60-70% similar)
- `SongDetailView.swift` (895 lines iOS, 1,159 lines Mac)
- `RecordingDetailView.swift` (1,004 lines iOS, 613 lines Mac)

#### Repertoire View Duplication (High - ~80% similar)
- `AddToRepertoireSheet.swift` ↔ `MacAddToRepertoireSheet.swift`
- `CreateRepertoireView.swift` ↔ `MacCreateRepertoireView.swift`

---

## Refactoring Strategies

### Strategy 1: Extract Shared ViewModels

**Effort:** Medium | **Value:** High

Create platform-agnostic `@Observable` classes for business logic:

```swift
// Shared/SongDetailViewModel.swift
@Observable
class SongDetailViewModel {
    var song: Song?
    var recordings: [Recording] = []
    var isLoading = false

    func loadSong(id: Int) async { ... }
    func toggleFavorite() { ... }
}
```

Each platform keeps its own View files but shares the ViewModel. This separates "what data to show" from "how to show it."

**Candidates for extraction:**
- `SongDetailViewModel` - Song loading, recordings fetching, favorite toggle
- `RecordingDetailViewModel` - Recording details, performer data, streaming links
- `ArtistDetailViewModel` - Artist bio, discography loading

### Strategy 2: Consolidate Auth Views with Conditional Compilation

**Effort:** Low | **Value:** Medium

Since auth views are 95% identical, merge them using `#if os(macOS)`:

```swift
// Single LoginView.swift
struct LoginView: View {
    var body: some View {
        #if os(macOS)
        macOSLayout
        #else
        iOSLayout
        #endif
    }

    private var macOSLayout: some View { ... }
    private var iOSLayout: some View { ... }
}
```

**Estimated savings:** ~1,200 lines → ~700 lines

### Strategy 3: Create Shared Components Library

**Effort:** Medium | **Value:** High

Populate the empty `Shared/` folder with reusable components:

- `CoverArtView` - Album art display with placeholder
- `PerformerRow` - Artist list items
- `RecordingRow` - Recording list items
- `StreamingLinksView` - Spotify/Apple Music buttons
- `InstrumentBadge` - Instrument display chips

### Strategy 4: Keep Views Separate (Current Approach)

**Effort:** None | **Value:** Maintains platform-specific UX

Valid reasons to NOT over-share views:
- Mac uses sidebars, tables, and hover states
- iOS uses navigation stacks, swipe gestures, and haptics
- Different screen sizes need different layouts
- Forcing shared views often leads to ugly `#if` spaghetti

---

## Recommended Approach

**Hybrid strategy combining the best of each:**

### Do Share:
1. **ViewModels** - Extract from detail views (~500-800 lines of shared logic)
2. **Auth Views** - Merge with conditional compilation (~500 lines saved)
3. **Components** - Build small shared component library

### Don't Force:
- Complex detail view layouts - keep platform-specific
- Navigation patterns - fundamentally different between platforms
- Platform-specific gestures and interactions

### Expected Impact:
- Reduce duplication by ~30-40%
- Easier to keep features in sync
- Maintain platform-appropriate UX

---

## Trade-offs Summary

| Approach | Pros | Cons |
|----------|------|------|
| More sharing | Less duplication, easier sync | More complex conditionals, harder to debug |
| Keep separate | Platform-optimized UX, simpler code | Must update both when models change |
| ViewModel extraction | Best of both worlds | Requires refactoring effort upfront |

---

## Implementation Priority

If pursuing refactoring:

1. **First:** Extract ViewModels from SongDetailView and RecordingDetailView
2. **Second:** Merge auth views with conditional compilation
3. **Third:** Build shared components as opportunities arise
4. **Ongoing:** Evaluate each new feature for sharing potential

---

## File References

**Shared Core (in `iOS/`):**
- `Support_Files/Models.swift`
- `Support_Files/NetworkManager.swift`
- `Support_Files/JazzTheme.swift`
- `Auth/AuthenticationManager.swift`
- `RepertoireManager.swift`
- `FavoritesManager.swift`

**iOS Views (in `iOS/`):**
- `SongDetailView.swift`
- `RecordingDetailView.swift`
- `Auth/Views/LoginView.swift` (and other auth views)

**Mac Views (in `Mac/Views/`):**
- `SongDetailView.swift`
- `RecordingDetailView.swift`
- `Auth/MacLoginView.swift` (and other auth views)

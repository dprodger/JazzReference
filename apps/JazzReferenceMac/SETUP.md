# JazzReferenceMac - Xcode Setup Instructions

This document explains how to add the macOS app target to your existing JazzReference Xcode project.

## Overview

The macOS app shares code with the iOS app:
- **Shared files** (add to both targets): Models, NetworkManager, JazzTheme, HelperViews, etc.
- **macOS-specific files** (macOS target only): JazzReferenceMacApp.swift, ContentView.swift, Views/*

## Step-by-Step Setup

### Step 1: Open the Project in Xcode

Open `apps/Approach Note.xcodeproj` in Xcode.

### Step 2: Add a New macOS App Target

1. In Xcode, go to **File → New → Target...**
2. Select **macOS** tab at the top
3. Choose **App** and click **Next**
4. Configure the target:
   - **Product Name**: `JazzReferenceMac`
   - **Team**: Your development team (FX893D85BJ)
   - **Organization Identifier**: `me.rodger.david`
   - **Bundle Identifier**: `me.rodger.david.JazzReferenceMac`
   - **Interface**: SwiftUI
   - **Language**: Swift
   - **Storage**: None
   - Uncheck "Include Tests"
5. Click **Finish**

### Step 3: Delete Auto-Generated Files

Xcode will create a default `JazzReferenceMac` folder with boilerplate files. Delete these:
- Delete the auto-generated `JazzReferenceMac` folder from the project
- Keep the target, but we'll use our prepared files instead

### Step 4: Add the Prepared JazzReferenceMac Folder

1. Right-click on the project root in the navigator
2. Select **Add Files to "JazzReference"...**
3. Navigate to the `JazzReferenceMac` folder we created
4. Make sure:
   - **Copy items if needed** is UNCHECKED
   - **Create groups** is selected
   - **Add to targets**: Only check `JazzReferenceMac`
5. Click **Add**

### Step 5: Configure Shared Files (Critical!)

These files from the iOS app need to be added to the macOS target:

#### From `JazzReference/Support_Files/`:
1. Select each file in Xcode's navigator
2. In the **File Inspector** (right panel), under **Target Membership**
3. Check the box for `JazzReferenceMac`

**Files to share:**
- `Models.swift` ✓
- `NetworkManager.swift` ✓
- `JazzTheme.swift` ✓
- `HelperViews.swift` ✓
- `PreviewHelpers.swift` ✓

#### From `JazzReference/`:
- `RepertoireManager.swift` ✓

#### From `JazzReference/Auth/`:
- `KeychainHelper.swift` ✓
- `AuthenticationManager.swift` ✓ (needs modification - see below)
- `Models/User.swift` ✓

### Step 6: Handle Platform-Specific Code

The `AuthenticationManager.swift` has iOS-specific code for Google Sign-In. You have two options:

**Option A: Conditional Compilation (Recommended)**

Edit `AuthenticationManager.swift` to wrap iOS-specific code:

```swift
#if os(iOS)
import GoogleSignIn
#endif

// ... and wrap the signInWithGoogle method:

#if os(iOS)
@MainActor
func signInWithGoogle() async -> Bool {
    // existing iOS code
}
#else
@MainActor
func signInWithGoogle() async -> Bool {
    // macOS placeholder - implement later if needed
    errorMessage = "Google Sign-In not yet available on macOS"
    return false
}
#endif
```

**Option B: Create macOS-specific AuthenticationManager**

Copy `AuthenticationManager.swift` to the macOS folder and modify it for macOS.

### Step 7: Configure Build Settings

Select the `JazzReferenceMac` target and configure:

1. **General Tab:**
   - Deployment Target: macOS 14.0 (or your minimum)
   - App Category: Music

2. **Signing & Capabilities:**
   - Team: Your team
   - Signing Certificate: Sign to Run Locally (for development)
   - Check **Hardened Runtime** if distributing

3. **Build Settings:**
   - Search for `INFOPLIST_FILE` and set to: `JazzReferenceMac/Info.plist`
   - Search for `CODE_SIGN_ENTITLEMENTS` and set to: `JazzReferenceMac/JazzReferenceMac.entitlements`
   - Search for `ASSETCATALOG_COMPILER_APPICON_NAME` and set to: `AppIcon`

### Step 8: Fix Any Compilation Errors

Common issues and fixes:

1. **UIImage not found**: The iOS app's `CachedAsyncImage.swift` uses UIImage. Don't add it to macOS target - use SwiftUI's built-in `AsyncImage` instead (which we do in the macOS views).

2. **UIApplication not found**: Wrap in `#if os(iOS)` or use macOS equivalents.

3. **UIImpactFeedbackGenerator**: This is iOS-only haptics. The macOS views don't use it.

### Step 9: Add App Icon (Optional)

1. Open `JazzReferenceMac/Assets.xcassets/AppIcon.appiconset`
2. Add your app icons at the required sizes:
   - 16x16 @1x and @2x
   - 32x32 @1x and @2x
   - 128x128 @1x and @2x
   - 256x256 @1x and @2x
   - 512x512 @1x and @2x

### Step 10: Build and Run

1. Select the `JazzReferenceMac` scheme in the toolbar
2. Select **My Mac** as the destination
3. Press **⌘R** to build and run

## File Structure After Setup

```
apps/
├── JazzReference/              # iOS app
│   ├── Support_Files/          # Shared with macOS
│   │   ├── Models.swift        # ✓ Both targets
│   │   ├── NetworkManager.swift # ✓ Both targets
│   │   ├── JazzTheme.swift     # ✓ Both targets
│   │   ├── HelperViews.swift   # ✓ Both targets
│   │   └── CachedAsyncImage.swift # iOS only
│   ├── Auth/
│   │   ├── AuthenticationManager.swift # ✓ Both (with #if)
│   │   ├── KeychainHelper.swift # ✓ Both targets
│   │   └── Models/User.swift   # ✓ Both targets
│   ├── RepertoireManager.swift # ✓ Both targets
│   └── ... (iOS-specific views)
├── JazzReferenceMac/           # macOS app
│   ├── JazzReferenceMacApp.swift
│   ├── ContentView.swift
│   ├── Views/
│   │   ├── SongsListView.swift
│   │   ├── ArtistsListView.swift
│   │   ├── RecordingsListView.swift
│   │   ├── SongDetailView.swift
│   │   ├── PerformerDetailView.swift
│   │   └── RecordingDetailView.swift
│   ├── Assets.xcassets/
│   ├── Info.plist
│   └── JazzReferenceMac.entitlements
└── Approach Note.xcodeproj
```

## Troubleshooting

### "No such module 'GoogleSignIn'"
The macOS target doesn't need GoogleSignIn. Make sure the package is only linked to the iOS target, not macOS.

### Keychain errors
Make sure `com.apple.security.keychain-access-groups` entitlement is set if needed, or use the default keychain access.

### Network requests failing
Ensure `com.apple.security.network.client` is set to `true` in entitlements (already configured).

## Next Steps

After basic setup works:
1. Add macOS-specific features (menu bar items, keyboard shortcuts)
2. Implement Google Sign-In for macOS (if needed)
3. Add Touch Bar support (if applicable)
4. Consider adding a menu bar utility app

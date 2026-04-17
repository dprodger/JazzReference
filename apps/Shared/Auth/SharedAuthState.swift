//
//  SharedAuthState.swift
//  Approach Note
//
//  Mirrors login status into the App Group so share extensions can check
//  whether the user is signed in without touching the Keychain.
//

import Foundation

enum SharedAuthState {
    static let appGroupIdentifier = "group.com.approachnote.shared"

    private static let isAuthenticatedKey = "isAuthenticated"
    private static let userDisplayNameKey = "userDisplayName"

    private static var defaults: UserDefaults? {
        UserDefaults(suiteName: appGroupIdentifier)
    }

    static var isAuthenticated: Bool {
        get { defaults?.bool(forKey: isAuthenticatedKey) ?? false }
        set { defaults?.set(newValue, forKey: isAuthenticatedKey) }
    }

    static var userDisplayName: String? {
        get { defaults?.string(forKey: userDisplayNameKey) }
        set { defaults?.set(newValue, forKey: userDisplayNameKey) }
    }

    static func clear() {
        defaults?.removeObject(forKey: isAuthenticatedKey)
        defaults?.removeObject(forKey: userDisplayNameKey)
    }
}

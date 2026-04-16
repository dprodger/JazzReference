//
//  LoginViewModel.swift
//  Approach Note
//
//  Shared view model for LoginView (iOS) and MacLoginView (Mac).
//  Owns form state and the trim-and-submit logic so platform views only
//  handle layout, presentation, and dismiss behavior.
//

import SwiftUI
import Combine

@MainActor
final class LoginViewModel: ObservableObject {
    @Published var email = ""
    @Published var password = ""
    @Published var showingRegister = false
    @Published var showingForgotPassword = false

    /// Whether the form has enough input to submit. Does NOT include
    /// `authManager.isLoading` — views should add that to their own
    /// `.disabled()` check so they observe the manager directly.
    var canSubmit: Bool {
        !email.isEmpty && !password.isEmpty
    }

    func signIn(using authManager: AuthenticationManager) async -> Bool {
        await authManager.login(
            email: email.trimmingCharacters(in: .whitespacesAndNewlines),
            password: password.trimmingCharacters(in: .whitespacesAndNewlines)
        )
    }

    func signInWithGoogle(using authManager: AuthenticationManager) async -> Bool {
        await authManager.signInWithGoogle()
    }
}

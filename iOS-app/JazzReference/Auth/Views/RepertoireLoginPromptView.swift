//
//  RepertoireLoginPromptView.swift
//  JazzReference
//
//  Created by Dave Rodger on 11/14/25.
//  Login form shown when unauthenticated users access Repertoire
//

import SwiftUI
import GoogleSignInSwift

struct RepertoireLoginPromptView: View {
    @EnvironmentObject var authManager: AuthenticationManager

    @State private var email = ""
    @State private var password = ""
    @State private var showingRegister = false
    @State private var showingForgotPassword = false

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                // Header
                VStack(spacing: 12) {
                    Image(systemName: "music.note.list")
                        .font(.system(size: 60))
                        .foregroundColor(JazzTheme.burgundy)

                    Text("Build Your Repertoire")
                        .font(.title)
                        .fontWeight(.bold)
                        .foregroundColor(JazzTheme.charcoal)

                    Text("Sign in to save songs and track your practice")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                }
                .padding(.top, 32)

                // Email field
                VStack(alignment: .leading, spacing: 8) {
                    Text("Email")
                        .font(.subheadline)
                        .foregroundColor(.secondary)

                    TextField("your@email.com", text: $email)
                        .textInputAutocapitalization(.never)
                        .keyboardType(.emailAddress)
                        .autocorrectionDisabled()
                        .padding()
                        .background(Color(.systemGray6))
                        .cornerRadius(10)
                }

                // Password field
                VStack(alignment: .leading, spacing: 8) {
                    Text("Password")
                        .font(.subheadline)
                        .foregroundColor(.secondary)

                    SecureField("Enter password", text: $password)
                        .padding()
                        .background(Color(.systemGray6))
                        .cornerRadius(10)
                }

                // Forgot password
                HStack {
                    Spacer()
                    Button("Forgot password?") {
                        showingForgotPassword = true
                    }
                    .font(.subheadline)
                    .foregroundColor(JazzTheme.burgundy)
                }

                // Error message
                if let error = authManager.errorMessage {
                    Text(error)
                        .font(.subheadline)
                        .foregroundColor(.red)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal)
                }

                // Login button
                Button(action: {
                    Task {
                        await authManager.login(
                            email: email.trimmingCharacters(in: .whitespacesAndNewlines),
                            password: password.trimmingCharacters(in: .whitespacesAndNewlines)
                        )
                    }
                }) {
                    if authManager.isLoading {
                        ProgressView()
                            .progressViewStyle(CircularProgressViewStyle(tint: .white))
                    } else {
                        Text("Sign In")
                            .fontWeight(.semibold)
                    }
                }
                .frame(maxWidth: .infinity)
                .padding()
                .background(email.isEmpty || password.isEmpty ? Color.gray : JazzTheme.burgundy)
                .foregroundColor(.white)
                .cornerRadius(10)
                .disabled(email.isEmpty || password.isEmpty || authManager.isLoading)

                // Divider
                HStack {
                    Rectangle()
                        .frame(height: 1)
                        .foregroundColor(.gray.opacity(0.3))
                    Text("or")
                        .foregroundColor(.secondary)
                        .padding(.horizontal, 8)
                    Rectangle()
                        .frame(height: 1)
                        .foregroundColor(.gray.opacity(0.3))
                }
                .padding(.vertical, 8)

                // Google Sign In Button
                GoogleSignInButton(action: {
                    Task {
                        await authManager.signInWithGoogle()
                    }
                })
                .frame(height: 50)
                .cornerRadius(10)
                .disabled(authManager.isLoading)

                // Divider
                HStack {
                    Rectangle()
                        .frame(height: 1)
                        .foregroundColor(.gray.opacity(0.3))
                    Text("or")
                        .foregroundColor(.secondary)
                        .padding(.horizontal, 8)
                    Rectangle()
                        .frame(height: 1)
                        .foregroundColor(.gray.opacity(0.3))
                }
                .padding(.vertical, 8)

                // Create account button
                Button(action: {
                    showingRegister = true
                }) {
                    Text("Create Account")
                        .fontWeight(.semibold)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color(.systemGray6))
                        .foregroundColor(JazzTheme.charcoal)
                        .cornerRadius(10)
                }

                Spacer()
            }
            .padding(.horizontal, 32)
        }
        .sheet(isPresented: $showingRegister) {
            RegisterView()
        }
        .sheet(isPresented: $showingForgotPassword) {
            ForgotPasswordView()
        }
    }
}

#Preview {
    RepertoireLoginPromptView()
        .environmentObject(AuthenticationManager())
}

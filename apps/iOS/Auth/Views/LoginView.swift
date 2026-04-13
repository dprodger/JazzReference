//
//  LoginView.swift
//  JazzReference
//
//  Created by Dave Rodger on 11/14/25.
//  Login screen with email/password authentication
//

import SwiftUI
import GoogleSignInSwift

struct LoginView: View {
    @EnvironmentObject var authManager: AuthenticationManager
    @Environment(\.dismiss) var dismiss

    @StateObject private var viewModel = LoginViewModel()
    
    var body: some View {
        NavigationView {
            ScrollView {
                VStack(spacing: 24) {
                    // Header
                    VStack(spacing: 8) {
                        Text("Welcome Back")
                            .font(.largeTitle)
                            .fontWeight(.bold)
                            .foregroundColor(JazzTheme.charcoal)
                        
                        Text("Sign in to access your repertoire")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                    }
                    .padding(.top, 40)
                    
                    // Email field
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Email")
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                        
                        TextField("your@email.com", text: $viewModel.email)
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
                        
                        SecureField("Enter password", text: $viewModel.password)
                            .padding()
                            .background(Color(.systemGray6))
                            .cornerRadius(10)
                    }
                    
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
                    .padding(.vertical, 16)

                    // Google Sign In Button
                    GoogleSignInButton(action: {
                        Task {
                            let success = await viewModel.signInWithGoogle(using: authManager)
                            if success {
                                dismiss()
                            }
                        }
                    })
                    .frame(height: 50)
                    .cornerRadius(10)
                    .disabled(authManager.isLoading)
                    
                    // Forgot password
                    HStack {
                        Spacer()
                        Button("Forgot password?") {
                            viewModel.showingForgotPassword = true
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
                            let success = await viewModel.signIn(using: authManager)
                            if success {
                                dismiss()
                            }
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
                    .background(viewModel.canSubmit ? JazzTheme.burgundy : Color.gray)
                    .foregroundColor(.white)
                    .cornerRadius(10)
                    .disabled(!viewModel.canSubmit || authManager.isLoading)
                    
                    // Divider
                    HStack {
                        Rectangle()
                            .frame(height: 1)
                            .foregroundColor(.gray.opacity(0.3))
                        Text("or")
                            .foregroundColor(.secondary)
                        Rectangle()
                            .frame(height: 1)
                            .foregroundColor(.gray.opacity(0.3))
                    }
                    .padding(.vertical, 8)
                    
                    // Create account button
                    Button(action: {
                        viewModel.showingRegister = true
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
                .padding()
            }
            .navigationTitle("")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Close") {
                        dismiss()
                    }
                    .foregroundColor(JazzTheme.charcoal)
                }
            }
            .sheet(isPresented: $viewModel.showingRegister) {
                RegisterView()
            }
            .sheet(isPresented: $viewModel.showingForgotPassword) {
                ForgotPasswordView()
            }
            .onChange(of: authManager.isAuthenticated) {
                if authManager.isAuthenticated {
                    dismiss()
                }
            }
        }
    }
}

#Preview {
    LoginView()
        .environmentObject(AuthenticationManager())
}

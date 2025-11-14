//
//  LoginView.swift
//  JazzReference
//
//  Created by Dave Rodger on 11/14/25.
//  Login screen with email/password authentication
//

import SwiftUI

struct LoginView: View {
    @EnvironmentObject var authManager: AuthenticationManager
    @Environment(\.dismiss) var dismiss
    
    @State private var email = ""
    @State private var password = ""
    @State private var showingRegister = false
    @State private var showingForgotPassword = false
    
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
                            let success = await authManager.login(email: email, password: password)
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
            .sheet(isPresented: $showingRegister) {
                RegisterView()
            }
            .sheet(isPresented: $showingForgotPassword) {
                ForgotPasswordView()
            }
        }
    }
}

#Preview {
    LoginView()
        .environmentObject(AuthenticationManager())
}

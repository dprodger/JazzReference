//
//  AuthenticationManager.swift
//  JazzReference
//
//  Created by Dave Rodger on 11/14/25.
//  Manages user authentication state and operations
//

import SwiftUI
import Combine

@MainActor
class AuthenticationManager: ObservableObject {
    // MARK: - Published Properties
    
    @Published var isAuthenticated = false
    @Published var currentUser: User?
    @Published var isLoading = false
    @Published var errorMessage: String?
    
    // MARK: - Private Properties
    
    private var accessToken: String?
    private let keychainHelper = KeychainHelper.shared
    
    // MARK: - Initialization
    
    init() {
        // Try to load tokens from Keychain on init
        loadTokensFromKeychain()
    }
    
    // MARK: - Token Management
    
    private func loadTokensFromKeychain() {
        if let accessToken = keychainHelper.load(forKey: "access_token"),
           let refreshToken = keychainHelper.load(forKey: "refresh_token") {
            self.accessToken = accessToken
            
            // Validate token by fetching current user
            Task {
                await fetchCurrentUser()
            }
        }
    }
    
    private func saveTokens(accessToken: String, refreshToken: String) {
        self.accessToken = accessToken
        _ = keychainHelper.save(accessToken, forKey: "access_token")
        _ = keychainHelper.save(refreshToken, forKey: "refresh_token")
    }
    
    private func clearTokens() {
        self.accessToken = nil
        keychainHelper.clearAll()
    }
    
    // MARK: - Authentication Methods
    
    /// Register a new user account
    func register(email: String, password: String, displayName: String) async -> Bool {
        isLoading = true
        errorMessage = nil
        
        let url = URL(string: "\(NetworkManager.baseURL)/auth/register")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body: [String: Any] = [
            "email": email,
            "password": password,
            "display_name": displayName
        ]
        
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        
        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            
            guard let httpResponse = response as? HTTPURLResponse else {
                throw URLError(.badServerResponse)
            }
            
            if httpResponse.statusCode == 201 {
                let authResponse = try JSONDecoder().decode(AuthResponse.self, from: data)
                
                saveTokens(accessToken: authResponse.accessToken,
                          refreshToken: authResponse.refreshToken)
                currentUser = authResponse.user
                isAuthenticated = true
                isLoading = false
                
                print("✅ Registration successful: \(authResponse.user.email)")
                return true
            } else {
                // Try to parse error message
                if let errorResponse = try? JSONDecoder().decode(AuthError.self, from: data) {
                    errorMessage = errorResponse.error
                } else {
                    errorMessage = "Registration failed"
                }
                
                print("❌ Registration failed: \(errorMessage ?? "Unknown error")")
                isLoading = false
                return false
            }
        } catch {
            errorMessage = "Registration failed: \(error.localizedDescription)"
            print("❌ Registration error: \(error)")
            isLoading = false
            return false
        }
    }
    
    /// Login with email and password
    func login(email: String, password: String) async -> Bool {
        isLoading = true
        errorMessage = nil
        
        let url = URL(string: "\(NetworkManager.baseURL)/auth/login")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body: [String: Any] = [
            "email": email,
            "password": password
        ]
        
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        
        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            
            guard let httpResponse = response as? HTTPURLResponse else {
                throw URLError(.badServerResponse)
            }
            
            if httpResponse.statusCode == 200 {
                let authResponse = try JSONDecoder().decode(AuthResponse.self, from: data)
                
                saveTokens(accessToken: authResponse.accessToken,
                          refreshToken: authResponse.refreshToken)
                currentUser = authResponse.user
                isAuthenticated = true
                isLoading = false
                
                print("✅ Login successful: \(authResponse.user.email)")
                return true
            } else {
                // Try to parse error message
                if let errorResponse = try? JSONDecoder().decode(AuthError.self, from: data) {
                    errorMessage = errorResponse.error
                } else {
                    errorMessage = "Login failed"
                }
                
                print("❌ Login failed: \(errorMessage ?? "Unknown error")")
                isLoading = false
                return false
            }
        } catch {
            errorMessage = "Login failed: \(error.localizedDescription)"
            print("❌ Login error: \(error)")
            isLoading = false
            return false
        }
    }
    
    /// Logout and clear all tokens
    func logout() {
        print("🔒 Logging out user: \(currentUser?.email ?? "unknown")")
        
        // Optional: Call logout endpoint to invalidate refresh token on backend
        if let token = accessToken,
           let refreshToken = keychainHelper.load(forKey: "refresh_token") {
            Task {
                await callLogoutEndpoint(accessToken: token, refreshToken: refreshToken)
            }
        }
        
        clearTokens()
        currentUser = nil
        isAuthenticated = false
        errorMessage = nil
    }
    
    /// Fetch current user info to validate token
    private func fetchCurrentUser() async {
        guard let token = accessToken else { return }
        
        let url = URL(string: "\(NetworkManager.baseURL)/auth/me")!
        var request = URLRequest(url: url)
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        
        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            
            guard let httpResponse = response as? HTTPURLResponse else {
                throw URLError(.badServerResponse)
            }
            
            if httpResponse.statusCode == 200 {
                let user = try JSONDecoder().decode(User.self, from: data)
                currentUser = user
                isAuthenticated = true
                print("✅ Token valid, user authenticated: \(user.email)")
            } else {
                // Token is invalid, clear it
                print("⚠️ Token invalid, clearing authentication")
                clearTokens()
                isAuthenticated = false
            }
        } catch {
            print("⚠️ Token validation failed: \(error)")
            clearTokens()
            isAuthenticated = false
        }
    }
    
    /// Call logout endpoint on backend (best effort)
    private func callLogoutEndpoint(accessToken: String, refreshToken: String) async {
        let url = URL(string: "\(NetworkManager.baseURL)/auth/logout")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body: [String: String] = ["refresh_token": refreshToken]
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        
        do {
            _ = try await URLSession.shared.data(for: request)
            print("✅ Backend logout successful")
        } catch {
            // Don't worry if it fails - tokens already cleared locally
            print("⚠️ Backend logout failed (non-critical): \(error)")
        }
    }
    
    // MARK: - Password Reset
    
    /// Request a password reset email
    func requestPasswordReset(email: String) async -> Bool {
        isLoading = true
        errorMessage = nil
        
        let url = URL(string: "\(NetworkManager.baseURL)/auth/forgot-password")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body: [String: String] = ["email": email]
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        
        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            
            guard let httpResponse = response as? HTTPURLResponse else {
                throw URLError(.badServerResponse)
            }
            
            isLoading = false
            
            if httpResponse.statusCode == 200 {
                print("✅ Password reset email sent to: \(email)")
                return true
            } else {
                if let errorResponse = try? JSONDecoder().decode(AuthError.self, from: data) {
                    errorMessage = errorResponse.error
                } else {
                    errorMessage = "Failed to send reset email"
                }
                print("❌ Password reset failed: \(errorMessage ?? "Unknown error")")
                return false
            }
        } catch {
            errorMessage = "Failed to send reset email: \(error.localizedDescription)"
            print("❌ Password reset error: \(error)")
            isLoading = false
            return false
        }
    }
    
    // MARK: - Authenticated API Requests
    
    /// Make an authenticated API request with automatic token inclusion
    func makeAuthenticatedRequest(url: URL) async throws -> Data {
        guard let token = accessToken else {
            throw URLError(.userAuthenticationRequired)
        }
        
        var request = URLRequest(url: url)
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw URLError(.badServerResponse)
        }
        
        // If unauthorized, clear tokens
        if httpResponse.statusCode == 401 {
            print("⚠️ 401 Unauthorized - clearing tokens")
            clearTokens()
            isAuthenticated = false
            throw URLError(.userAuthenticationRequired)
        }
        
        return data
    }
    
    /// Get current access token (for manual requests)
    func getAccessToken() -> String? {
        return accessToken
    }
}

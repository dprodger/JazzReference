//
//  AuthenticationManager.swift
//  JazzReference
//
//  Created by Dave Rodger on 11/14/25.
//  Manages user authentication state and operations
//

import SwiftUI
import Combine
import GoogleSignIn

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
    
    /// Refresh the access token using the stored refresh token
    private func refreshAccessToken() async -> Bool {
        guard let refreshToken = keychainHelper.load(forKey: "refresh_token") else {
            print("❌ No refresh token available")
            return false
        }
        
        let url = URL(string: "\(NetworkManager.baseURL)/auth/refresh-token")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body: [String: String] = ["refresh_token": refreshToken]
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        
        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            
            guard let httpResponse = response as? HTTPURLResponse else {
                throw URLError(.badServerResponse)
            }
            
            if httpResponse.statusCode == 200 {
                struct RefreshResponse: Codable {
                    let accessToken: String
                    let refreshToken: String
                    
                    enum CodingKeys: String, CodingKey {
                        case accessToken = "access_token"
                        case refreshToken = "refresh_token"
                    }
                }
                
                let refreshResponse = try JSONDecoder().decode(RefreshResponse.self, from: data)
                
                // Save new tokens
                saveTokens(accessToken: refreshResponse.accessToken,
                          refreshToken: refreshResponse.refreshToken)
                
                print("✅ Access token refreshed successfully")
                return true
            } else {
                print("❌ Token refresh failed with status: \(httpResponse.statusCode)")
                return false
            }
        } catch {
            print("❌ Token refresh error: \(error)")
            return false
        }
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
    // ENHANCED VERSION: Add this to AuthenticationManager.swift
    // This version supports GET, POST, DELETE with optional body data

    /// Make an authenticated API request with automatic token refresh on 401
    /// - Parameters:
    ///   - url: The URL to request
    ///   - method: HTTP method (GET, POST, DELETE, etc.)
    ///   - body: Optional request body data
    ///   - contentType: Optional content type header
    ///   - maxRetries: Maximum retry attempts (default 1)
    /// - Returns: Response data
    /// - Throws: URLError if authentication fails or network error occurs
    func makeAuthenticatedRequest(
        url: URL,
        method: String = "GET",
        body: Data? = nil,
        contentType: String? = "application/json",
        maxRetries: Int = 1
    ) async throws -> Data {
        guard let token = accessToken else {
            throw URLError(.userAuthenticationRequired)
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        
        if let contentType = contentType {
            request.setValue(contentType, forHTTPHeaderField: "Content-Type")
        }
        
        if let body = body {
            request.httpBody = body
        }
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw URLError(.badServerResponse)
        }
        
        // If unauthorized, try to refresh token and retry
        if httpResponse.statusCode == 401 {
            print("⚠️ 401 Unauthorized - attempting token refresh")
            
            // Try to refresh token
            let refreshed = await refreshAccessToken()
            
            if refreshed && maxRetries > 0 {
                // Retry the request with new token
                print("🔄 Retrying request with refreshed token")
                return try await makeAuthenticatedRequest(
                    url: url,
                    method: method,
                    body: body,
                    contentType: contentType,
                    maxRetries: maxRetries - 1
                )
            } else {
                // Refresh failed or no retries left, clear tokens
                print("❌ Token refresh failed - clearing authentication")
                await MainActor.run {
                    clearTokens()
                    isAuthenticated = false
                }
                throw URLError(.userAuthenticationRequired)
            }
        }
        
        // For non-200 responses, throw an error with status code
        if httpResponse.statusCode >= 400 {
            let errorMessage = String(data: data, encoding: .utf8) ?? "HTTP \(httpResponse.statusCode)"
            print("❌ API error \(httpResponse.statusCode): \(errorMessage)")
            throw NSError(
                domain: "APIError",
                code: httpResponse.statusCode,
                userInfo: [NSLocalizedDescriptionKey: errorMessage]
            )
        }
        
        return data
    }
    
    /// Get current access token (for manual requests)
    func getAccessToken() -> String? {
        return accessToken
    }
    
    /// Reset password using token from email
    func resetPassword(token: String, newPassword: String) async -> Bool {
        isLoading = true
        errorMessage = nil
        
        let url = URL(string: "\(NetworkManager.baseURL)/auth/reset-password")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body: [String: String] = [
            "token": token,
            "password": newPassword
        ]
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        
        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            
            guard let httpResponse = response as? HTTPURLResponse else {
                throw URLError(.badServerResponse)
            }
            
            isLoading = false
            
            if httpResponse.statusCode == 200 {
                print("✅ Password reset successful")
                return true
            } else {
                if let errorResponse = try? JSONDecoder().decode(AuthError.self, from: data) {
                    errorMessage = errorResponse.error
                } else {
                    errorMessage = "Password reset failed"
                }
                print("❌ Password reset failed: \(errorMessage ?? "Unknown error")")
                return false
            }
        } catch {
            errorMessage = "Password reset failed: \(error.localizedDescription)"
            print("❌ Password reset error: \(error)")
            isLoading = false
            return false
        }
    }
    
    @MainActor
    func signInWithGoogle() async -> Bool {
        isLoading = true
        errorMessage = nil
        
        // Get the presenting view controller
        guard let windowScene = UIApplication.shared.connectedScenes.first as? UIWindowScene,
              let rootViewController = windowScene.windows.first?.rootViewController else {
            errorMessage = "Unable to find window"
            isLoading = false
            return false
        }
        
        // Get the GIDClientID from Info.plist
        guard let clientID = Bundle.main.object(forInfoDictionaryKey: "GIDClientID") as? String else {
            errorMessage = "Google Client ID not configured"
            isLoading = false
            return false
        }
        
        // Configure Google Sign In
        let config = GIDConfiguration(clientID: clientID)
        GIDSignIn.sharedInstance.configuration = config
        
        do {
            // Start Google Sign In
            let result = try await GIDSignIn.sharedInstance.signIn(
                withPresenting: rootViewController
            )
            
            // Get ID token
            guard let idToken = result.user.idToken?.tokenString else {
                errorMessage = "Failed to get ID token from Google"
                isLoading = false
                return false
            }
            
            // Send ID token to backend
            let success = await authenticateWithGoogle(idToken: idToken)
            isLoading = false
            return success
            
        } catch {
            errorMessage = "Google Sign In failed: \(error.localizedDescription)"
            isLoading = false
            return false
        }
    }

    private func authenticateWithGoogle(idToken: String) async -> Bool {
        let url = URL(string: "\(NetworkManager.baseURL)/auth/google")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body: [String: Any] = ["id_token": idToken]
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        
        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            
            // Check HTTP status
            guard let httpResponse = response as? HTTPURLResponse else {
                errorMessage = "Invalid response from server"
                return false
            }
            
            if httpResponse.statusCode != 200 {
                // Try to parse error message
                if let errorResponse = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   let error = errorResponse["error"] as? String {
                    errorMessage = error
                } else {
                    errorMessage = "Authentication failed with status \(httpResponse.statusCode)"
                }
                return false
            }
            
            // Parse successful response
            let authResponse = try JSONDecoder().decode(AuthResponse.self, from: data)
            
            // Save tokens
            saveTokens(accessToken: authResponse.accessToken,
                      refreshToken: authResponse.refreshToken)
            
            // Update user state
            currentUser = authResponse.user
            isAuthenticated = true
            
            return true
        } catch {
            errorMessage = "Authentication failed: \(error.localizedDescription)"
            return false
        }
    }
}

//
//  User.swift
//  JazzReference
//
//  Created by Dave Rodger on 11/14/25.
//  Authentication user models
//

import Foundation

/// User model representing an authenticated user
struct User: Codable, Identifiable {
    let id: String
    let email: String
    let displayName: String?
    let profileImageUrl: String?
    let emailVerified: Bool?
    
    enum CodingKeys: String, CodingKey {
        case id, email
        case displayName = "display_name"
        case profileImageUrl = "profile_image_url"
        case emailVerified = "email_verified"
    }
}

/// Response structure from authentication endpoints
struct AuthResponse: Codable {
    let user: User
    let accessToken: String
    let refreshToken: String
    
    enum CodingKeys: String, CodingKey {
        case user
        case accessToken = "access_token"
        case refreshToken = "refresh_token"
    }
}

/// Error response from API
struct AuthError: Codable {
    let error: String
    let details: String?
}


struct ResetPassword: Codable {
    let token: String
    let password: String
}


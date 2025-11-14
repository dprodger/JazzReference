//
//  KeychainHelper.swift
//  JazzReference
//
//  Created by Dave Rodger on 11/14/25.
//  Secure storage for authentication tokens using iOS Keychain
//

import Foundation
import Security

/// Helper class for securely storing and retrieving tokens from iOS Keychain
class KeychainHelper {
    static let shared = KeychainHelper()
    
    private init() {}
    
    // MARK: - Public Methods
    
    /// Save a token value to Keychain
    /// - Parameters:
    ///   - value: The token string to save
    ///   - key: The key to store it under (e.g., "access_token")
    /// - Returns: True if save was successful
    func save(_ value: String, forKey key: String) -> Bool {
        guard let data = value.data(using: .utf8) else {
            print("KeychainHelper: Failed to encode value as UTF-8")
            return false
        }
        
        // Delete any existing item first to avoid duplicates
        delete(forKey: key)
        
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key,
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlocked
        ]
        
        let status = SecItemAdd(query as CFDictionary, nil)
        
        if status == errSecSuccess {
            print("KeychainHelper: Successfully saved '\(key)'")
            return true
        } else {
            print("KeychainHelper: Failed to save '\(key)' with status: \(status)")
            return false
        }
    }
    
    /// Load a token value from Keychain
    /// - Parameter key: The key to retrieve (e.g., "access_token")
    /// - Returns: The token string if found, nil otherwise
    func load(forKey key: String) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]
        
        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        
        guard status == errSecSuccess,
              let data = result as? Data,
              let value = String(data: data, encoding: .utf8) else {
            if status != errSecItemNotFound {
                print("KeychainHelper: Failed to load '\(key)' with status: \(status)")
            }
            return nil
        }
        
        print("KeychainHelper: Successfully loaded '\(key)'")
        return value
    }
    
    /// Delete a token from Keychain
    /// - Parameter key: The key to delete
    /// - Returns: True if delete was successful (or item didn't exist)
    @discardableResult
    func delete(forKey key: String) -> Bool {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key
        ]
        
        let status = SecItemDelete(query as CFDictionary)
        
        // Success if deleted or item didn't exist
        let success = status == errSecSuccess || status == errSecItemNotFound
        
        if success {
            print("KeychainHelper: Deleted '\(key)'")
        } else {
            print("KeychainHelper: Failed to delete '\(key)' with status: \(status)")
        }
        
        return success
    }
    
    /// Clear all authentication tokens (used on logout)
    func clearAll() {
        print("KeychainHelper: Clearing all tokens")
        delete(forKey: "access_token")
        delete(forKey: "refresh_token")
    }
}

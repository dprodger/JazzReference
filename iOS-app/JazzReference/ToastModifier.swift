//
//  ToastModifier.swift
//  JazzReference
//
//  Created by Dave Rodger on 11/13/25.
//  View modifier for adding toast notifications to any view
//

import SwiftUI

// MARK: - Toast Modifier
struct ToastModifier: ViewModifier {
    @Binding var toast: ToastItem?
    let autoDismissAfter: TimeInterval
    
    init(toast: Binding<ToastItem?>, autoDismissAfter: TimeInterval = 5.0) {
        self._toast = toast
        self.autoDismissAfter = autoDismissAfter
    }
    
    func body(content: Content) -> some View {
        content
            .overlay(alignment: .top) {
                ToastContainerView(toast: toast) {
                    dismissToast()
                }
            }
            .onChange(of: toast?.id) { oldValue, newValue in
                if newValue != nil {
                    scheduleAutoDismiss()
                }
            }
    }
    
    private func dismissToast() {
        withAnimation {
            toast = nil
        }
    }
    
    private func scheduleAutoDismiss() {
        Task {
            try? await Task.sleep(nanoseconds: UInt64(autoDismissAfter * 1_000_000_000))
            await MainActor.run {
                dismissToast()
            }
        }
    }
}

// MARK: - View Extension
extension View {
    /// Adds toast notification capability to any view
    /// - Parameters:
    ///   - toast: Binding to optional ToastItem - set to show toast, set to nil to dismiss
    ///   - autoDismissAfter: Time in seconds before auto-dismissing (default: 5.0)
    /// - Returns: Modified view with toast capability
    func toast(_ toast: Binding<ToastItem?>, autoDismissAfter: TimeInterval = 5.0) -> some View {
        modifier(ToastModifier(toast: toast, autoDismissAfter: autoDismissAfter))
    }
}

// MARK: - Convenience Methods
extension View {
    /// Show a success toast
    func showSuccessToast(_ message: String, toast: Binding<ToastItem?>) {
        toast.wrappedValue = ToastItem(type: .success, message: message)
    }
    
    /// Show an error toast
    func showErrorToast(_ message: String, toast: Binding<ToastItem?>) {
        toast.wrappedValue = ToastItem(type: .error, message: message)
    }
    
    /// Show an info toast
    func showInfoToast(_ message: String, toast: Binding<ToastItem?>) {
        toast.wrappedValue = ToastItem(type: .info, message: message)
    }
    
    /// Show a warning toast
    func showWarningToast(_ message: String, toast: Binding<ToastItem?>) {
        toast.wrappedValue = ToastItem(type: .warning, message: message)
    }
}

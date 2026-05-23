// SovereignVisionApp.swift
//
// The SwiftUI App entry. Embed this in a thin iOS / iPadOS / macOS host
// target in Xcode (File > New > Project > iOS App), or use this package
// as the only target and add `@main` here when you've created the
// platform-specific shell.

import SwiftUI

@available(iOS 17.0, macOS 14.0, *)
public struct SovereignVisionApp: App {
    public init() {}

    public var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}

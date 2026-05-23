// swift-tools-version: 5.9
//
// Sovereign Vision - iOS / macOS package.
//
// This package ships the SwiftUI client for verifying Sovereign Vision
// compliance certificates on iOS, iPadOS, and macOS. It builds against
// CryptoKit so verification runs entirely on-device.

import PackageDescription

let package = Package(
    name: "SovereignVision",
    platforms: [
        .iOS(.v17),
        .macOS(.v14),
        .visionOS(.v1),
    ],
    products: [
        .library(
            name: "SovereignVisionKit",
            targets: ["SovereignVisionKit"]
        ),
    ],
    targets: [
        .target(
            name: "SovereignVisionKit",
            path: "Sources/SovereignVisionKit"
        ),
        .testTarget(
            name: "SovereignVisionKitTests",
            dependencies: ["SovereignVisionKit"],
            path: "Tests/SovereignVisionKitTests"
        ),
    ]
)

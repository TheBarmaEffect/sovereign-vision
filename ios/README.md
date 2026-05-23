# Sovereign Vision - iOS / iPadOS / macOS / visionOS

A SwiftUI client for verifying Sovereign Vision compliance certificates
on-device. Runs on:

- iOS 17+
- iPadOS 17+
- macOS 14+
- visionOS 1+

All verification (SHA-256 integrity hash re-derivation, canonical JSON
normalisation, rule rendering) happens locally via CryptoKit. Nothing
is uploaded.

---

## Open in Xcode

```bash
cd ios/SovereignVision
open Package.swift
```

Xcode will resolve the Swift package and let you build for the iOS
simulator, your iPhone, or your Mac.

To ship to TestFlight you'll need an Apple Developer account and a
provisioning profile signed with your team identity. That step is
yours; the code is ready.

---

## Project layout

```
ios/SovereignVision/
  Package.swift                                          (Swift 5.9 package)
  Sources/SovereignVisionKit/
    SovereignVisionApp.swift                             SwiftUI App entry
    ContentView.swift                                    Main UI
    CertificateVerifier.swift                            CryptoKit-based verifier
    Constitution.swift                                   SV-001..SV-007 mirror
  Tests/SovereignVisionKitTests/
    CertificateVerifierTests.swift                       Unit tests
```

`SovereignVisionKit` is a reusable library; you can embed it in any
SwiftUI app target. To build it standalone via the Swift CLI:

```bash
cd ios/SovereignVision
swift build
swift test
```

The library targets iOS 17 / macOS 14 minimums so we can use the
modern `NavigationStack`, `fileImporter`, and CryptoKit's `SHA256`.

---

## Verifying a certificate on device

The user taps "Choose file", picks a `session_*.json` previously
exported from the Sovereign Vision desktop dashboard, and immediately
sees:

- VERIFIED / TAMPERED / MISSING FIELD / INVALID JSON badge
- Frame count, duration, session id
- Compliance score (0-100) with grade and sub-score bars
- Merkle root, head hash, chain length
- Hardware fingerprint of the issuing machine
- The full SV-001..SV-007 rule set with legal basis

No network. No telemetry. Same SHA-256 contract as the Python source.

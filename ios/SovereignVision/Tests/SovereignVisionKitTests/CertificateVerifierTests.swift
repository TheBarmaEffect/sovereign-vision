// CertificateVerifierTests.swift
//
// Sanity tests for the Swift verifier against a hand-crafted cert.

import XCTest
@testable import SovereignVisionKit

final class CertificateVerifierTests: XCTestCase {

    func testRulesPresent() {
        XCTAssertEqual(Constitution.defaultRules.count, 7)
        XCTAssertEqual(Constitution.defaultRules.first?.ruleID, "SV-001")
    }

    func testMissingIntegrityHashIsReported() {
        let json = #"{"cert_type":"session","session_id":"a"}"#
        let (_, result) = CertificateVerifier.verify(Data(json.utf8))
        if case .missingField(let f) = result {
            XCTAssertEqual(f, "integrity_hash")
        } else {
            XCTFail("expected missingField but got \(result)")
        }
    }

    func testInvalidJSONIsReported() {
        let (_, result) = CertificateVerifier.verify(Data("not json".utf8))
        if case .invalidJSON = result {} else {
            XCTFail("expected invalidJSON")
        }
    }
}

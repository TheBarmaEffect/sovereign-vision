// CertificateVerifier.swift
//
// On-device verification of a Sovereign Vision session certificate
// using CryptoKit's SHA-256. Mirrors the Python `_integrity_hash`
// function bit-for-bit so the verification works without contacting
// any server.

import CryptoKit
import Foundation

public enum VerificationResult {
    case ok
    case missingField(String)
    case hashMismatch(stored: String, derived: String)
    case invalidJSON(String)
}

public struct SessionCertificate: Decodable {
    public let cert_version: String?
    public let session_id: String?
    public let total_frames: Int?
    public let overall_status: String?
    public let duration_seconds: Double?
    public let integrity_hash: String?
    public let audit_chain: AuditChain?
    public let compliance_score: ComplianceScore?
    public let hardware: HardwareInfo?

    public struct AuditChain: Decodable {
        public let chain_length: Int?
        public let merkle_root: String?
        public let head_hash: String?
        public let genesis_hash: String?
    }

    public struct ComplianceScore: Decodable {
        public let score: Int?
        public let grade: String?
        public let rule_coverage_score: Int?
        public let status_mix_score: Int?
        public let audit_integrity_score: Int?
        public let dp_budget_score: Int?
        public let redaction_density_score: Int?
        public let breakdown: [String: String]?
    }

    public struct HardwareInfo: Decodable {
        public let chip_name: String?
        public let chip_generation: String?
        public let cpu_p_cores: Int?
        public let cpu_e_cores: Int?
        public let gpu_cores: Int?
        public let neural_engine_cores: Int?
        public let unified_memory_gb: Double?
        public let mlx_available: Bool?
        public let mlx_version: String?
    }
}

public enum CertificateVerifier {

    /// Decode + verify a session_*.json file's integrity hash.
    public static func verify(_ data: Data) -> (cert: SessionCertificate?, result: VerificationResult) {
        let cert: SessionCertificate
        do {
            cert = try JSONDecoder().decode(SessionCertificate.self, from: data)
        } catch {
            return (nil, .invalidJSON(error.localizedDescription))
        }

        guard let stored = cert.integrity_hash else {
            return (cert, .missingField("integrity_hash"))
        }

        // Decode generically, remove the integrity_hash, re-canonicalise
        // with sorted keys, hash with SHA-256.
        guard var obj = try? JSONSerialization.jsonObject(with: data,
                options: []) as? [String: Any] else {
            return (cert, .invalidJSON("could not re-decode for canonicalisation"))
        }
        obj.removeValue(forKey: "integrity_hash")
        guard let canonical = canonicaliseJSON(obj) else {
            return (cert, .invalidJSON("canonicalisation failed"))
        }

        let digest = SHA256.hash(data: canonical)
        let derived = digest.map { String(format: "%02x", $0) }.joined()

        if derived == stored {
            return (cert, .ok)
        }
        return (cert, .hashMismatch(stored: stored, derived: derived))
    }

    /// Render `Any` JSON with sorted keys to match Python's
    /// json.dumps(sort_keys=True, separators=(",", ":")).
    private static func canonicaliseJSON(_ obj: Any) -> Data? {
        func emit(_ v: Any) -> String {
            if let d = v as? [String: Any] {
                let parts = d.keys.sorted().map { k -> String in
                    "\"\(escape(k))\":\(emit(d[k]!))"
                }
                return "{" + parts.joined(separator: ",") + "}"
            }
            if let a = v as? [Any] {
                return "[" + a.map(emit).joined(separator: ",") + "]"
            }
            if let s = v as? String { return "\"\(escape(s))\"" }
            if let b = v as? Bool   { return b ? "true" : "false" }
            if let n = v as? NSNumber {
                let dbl = n.doubleValue
                if floor(dbl) == dbl && !n.stringValue.contains(".") {
                    return n.stringValue
                }
                return n.stringValue
            }
            if v is NSNull { return "null" }
            return "\(v)"
        }
        return emit(obj).data(using: .utf8)
    }

    private static func escape(_ s: String) -> String {
        var out = ""
        for c in s.unicodeScalars {
            switch c {
            case "\"":  out += "\\\""
            case "\\":  out += "\\\\"
            case "\n":  out += "\\n"
            case "\r":  out += "\\r"
            case "\t":  out += "\\t"
            default:
                if c.value < 0x20 {
                    out += String(format: "\\u%04x", c.value)
                } else {
                    out += String(c)
                }
            }
        }
        return out
    }
}

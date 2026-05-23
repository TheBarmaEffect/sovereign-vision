// ContentView.swift
//
// Apple-style SwiftUI viewer: paste or drop a session_*.json, see the
// verification result, score, status badge, and the full rule set.

import SwiftUI
import UniformTypeIdentifiers

public struct ContentView: View {
    @State private var verification: VerificationResult?
    @State private var cert: SessionCertificate?
    @State private var showImporter = false

    public init() {}

    public var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    headerSection
                    Divider()
                    if let cert = cert, let v = verification {
                        verificationCard(cert: cert, result: v)
                        if let score = cert.compliance_score {
                            complianceCard(score)
                        }
                        if let chain = cert.audit_chain {
                            chainCard(chain)
                        }
                        if let hw = cert.hardware {
                            hardwareCard(hw)
                        }
                    } else {
                        emptyState
                    }
                    Divider()
                    constitutionSection
                }
                .padding(20)
            }
            .navigationTitle("Sovereign Vision")
        }
        .fileImporter(
            isPresented: $showImporter,
            allowedContentTypes: [.json, .data],
            allowsMultipleSelection: false
        ) { result in
            guard case .success(let urls) = result,
                  let url = urls.first,
                  url.startAccessingSecurityScopedResource(),
                  let data = try? Data(contentsOf: url)
            else { return }
            defer { url.stopAccessingSecurityScopedResource() }
            let (c, v) = CertificateVerifier.verify(data)
            self.cert = c
            self.verification = v
        }
    }

    // MARK: - Sections

    private var headerSection: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Sovereign Vision")
                .font(.largeTitle).bold()
            Text("Verify a compliance certificate on-device. Zero upload.")
                .font(.caption).foregroundStyle(.secondary)
        }
    }

    private var emptyState: some View {
        VStack(spacing: 12) {
            Image(systemName: "shield.lefthalf.filled")
                .resizable().scaledToFit().frame(width: 48, height: 48)
                .foregroundStyle(.tint)
            Text("Drop in a session_*.json to verify")
                .font(.headline)
            Button("Choose file") { showImporter = true }
                .buttonStyle(.borderedProminent)
        }
        .frame(maxWidth: .infinity, minHeight: 200)
    }

    private func verificationCard(cert: SessionCertificate, result: VerificationResult) -> some View {
        let (label, color): (String, Color) = {
            switch result {
            case .ok: return ("VERIFIED", .green)
            case .missingField: return ("MISSING FIELD", .orange)
            case .hashMismatch: return ("TAMPERED", .red)
            case .invalidJSON: return ("INVALID JSON", .red)
            }
        }()
        return VStack(alignment: .leading, spacing: 8) {
            HStack {
                Circle().fill(color).frame(width: 10, height: 10)
                Text(label).font(.title2).bold().foregroundStyle(color)
                Spacer()
                if let status = cert.overall_status {
                    Text(status).font(.caption).foregroundStyle(.secondary)
                }
            }
            HStack(spacing: 24) {
                statBlock("Session", String((cert.session_id ?? "").prefix(8)))
                statBlock("Frames",  "\(cert.total_frames ?? 0)")
                statBlock("Duration", String(format: "%.2fs", cert.duration_seconds ?? 0))
            }
        }
        .padding()
        .background(RoundedRectangle(cornerRadius: 12).fill(Color(.secondarySystemBackground)))
    }

    private func complianceCard(_ score: SessionCertificate.ComplianceScore) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Compliance score").font(.caption).foregroundStyle(.secondary)
            HStack(alignment: .firstTextBaseline) {
                Text("\(score.score ?? 0)").font(.system(size: 42, weight: .bold))
                Text("/ 100  ·  grade \(score.grade ?? "-")")
                    .font(.subheadline).foregroundStyle(.secondary)
            }
            VStack(alignment: .leading, spacing: 4) {
                subscoreRow("Rule coverage", score.rule_coverage_score, 30)
                subscoreRow("Status mix", score.status_mix_score, 25)
                subscoreRow("Audit integrity", score.audit_integrity_score, 25)
                subscoreRow("DP budget", score.dp_budget_score, 10)
                subscoreRow("Redaction density", score.redaction_density_score, 10)
            }
        }
        .padding()
        .background(RoundedRectangle(cornerRadius: 12).fill(Color(.secondarySystemBackground)))
    }

    private func chainCard(_ chain: SessionCertificate.AuditChain) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Audit chain anchor").font(.caption).foregroundStyle(.secondary)
            row("Length", "\(chain.chain_length ?? 0)")
            row("Merkle root", String((chain.merkle_root ?? "-").prefix(32)) + "...")
            row("Head hash", String((chain.head_hash ?? "-").prefix(32)) + "...")
        }
        .padding()
        .background(RoundedRectangle(cornerRadius: 12).fill(Color(.secondarySystemBackground)))
    }

    private func hardwareCard(_ hw: SessionCertificate.HardwareInfo) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Hardware attestation").font(.caption).foregroundStyle(.secondary)
            row("Chip", hw.chip_name ?? "-")
            row("Cores", "\(hw.cpu_p_cores ?? 0)P + \(hw.cpu_e_cores ?? 0)E + \(hw.gpu_cores ?? 0) GPU + \(hw.neural_engine_cores ?? 0) NE")
            row("Memory", "\(Int(hw.unified_memory_gb ?? 0)) GB unified")
            row("MLX", hw.mlx_version ?? "-")
        }
        .padding()
        .background(RoundedRectangle(cornerRadius: 12).fill(Color(.secondarySystemBackground)))
    }

    private var constitutionSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("The Constitution").font(.headline)
            ForEach(Constitution.defaultRules) { rule in
                HStack(alignment: .top, spacing: 12) {
                    Text(rule.ruleID).font(.system(.caption, design: .monospaced).bold())
                        .frame(width: 60, alignment: .leading)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(rule.name).font(.subheadline).bold()
                        Text(rule.legalBasis).font(.caption).foregroundStyle(.secondary)
                    }
                    Spacer()
                    Text(rule.action.rawValue).font(.caption2).bold()
                        .padding(.horizontal, 8).padding(.vertical, 3)
                        .background(RoundedRectangle(cornerRadius: 6).fill(.tint.opacity(0.15)))
                        .foregroundStyle(.tint)
                }
                .padding(.vertical, 4)
                Divider()
            }
        }
    }

    // MARK: - Small helpers

    private func statBlock(_ label: String, _ value: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label).font(.caption2).foregroundStyle(.secondary)
            Text(value).font(.system(.body, design: .monospaced).bold())
        }
    }

    private func subscoreRow(_ label: String, _ value: Int?, _ ceiling: Int) -> some View {
        HStack {
            Text(label).font(.caption)
            Spacer()
            Text("\(value ?? 0) / \(ceiling)").font(.caption.monospaced())
        }
    }

    private func row(_ k: String, _ v: String) -> some View {
        HStack(alignment: .firstTextBaseline) {
            Text(k).font(.caption).foregroundStyle(.secondary).frame(width: 110, alignment: .leading)
            Text(v).font(.caption.monospaced())
        }
    }
}

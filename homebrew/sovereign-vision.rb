class SovereignVision < Formula
  include Language::Python::Virtualenv

  desc "On-device enterprise vision firewall - GDPR-compliant by design"
  homepage "https://github.com/TheBarmaEffect/sovereign-vision"
  url "https://files.pythonhosted.org/packages/67/22/10f9fa46d091b3f6c62ee5453fb15499e7ea0b66278d75959b982a592c1c/sovereign_vision-1.3.0.tar.gz"
  sha256 "44bd9d041c33c950604a1e7e51becc51cf1cb48dceea3f205ad45842c8704bb3"
  license "AGPL-3.0-or-later"
  head "https://github.com/TheBarmaEffect/sovereign-vision.git", branch: "main"

  depends_on "python@3.12"
  depends_on "openssl@3"    # used by RFC 3161 notarisation (`openssl ts`)

  def install
    venv = virtualenv_create(libexec, "python3.12")
    # Install runtime dependencies first, then the package itself.
    # We intentionally use --no-build-isolation for speed since all
    # required wheels are pure-Python or have prebuilt wheels on PyPI
    # for arm64-darwin.
    system libexec/"bin/pip", "install", "--no-cache-dir",
           "numpy>=2.0",
           "Pillow>=11.0",
           "opencv-python-headless>=4.10",
           "rich>=13.9",
           "pydantic>=2.10",
           "structlog>=24.4",
           "PyYAML>=6.0"
    system libexec/"bin/pip", "install", "--no-cache-dir", "--no-deps", cached_download
    (bin/"sovereign").write_env_script libexec/"bin/sovereign", PATH: "#{libexec}/bin:$PATH"
    (bin/"sovereign-vision").write_env_script libexec/"bin/sovereign-vision", PATH: "#{libexec}/bin:$PATH"
  end

  def caveats
    <<~EOS
      Sovereign Vision is installed at:
        #{libexec}

      To run the dashboard:
        sovereign demo

      To run in production mode (no RAW panel):
        sovereign demo --production

      For real YOLO26 inference on Apple Silicon, also install MLX:
        #{libexec}/bin/pip install mlx

      Source, docs, and threat model:
        https://github.com/TheBarmaEffect/sovereign-vision
    EOS
  end

  test do
    # Smoke test: CLI must print version and the 7 default rules.
    output = shell_output("#{bin}/sovereign info")
    assert_match "Sovereign Vision", output
    assert_match "SV-001", output
    assert_match "SV-007", output

    # Constitutional rules JSON should be machine-readable.
    rules = shell_output("#{bin}/sovereign rules")
    assert_match "Person Coordinate Redaction", rules

    # Doctor should not crash even in a sandbox.
    system "#{bin}/sovereign", "doctor"
  end
end

class SovereignVision < Formula
  include Language::Python::Virtualenv

  desc "On-device enterprise vision firewall: GDPR-compliant by design"
  homepage "https://github.com/TheBarmaEffect/sovereign-vision"
  url "https://github.com/TheBarmaEffect/sovereign-vision/releases/download/v1.3.0/sovereign_vision-1.3.0.tar.gz"
  sha256 "41aca791845bfc4135b4863da7475a063dfaf9f80147935ce893fbbdc651c16b"
  license "AGPL-3.0-or-later"
  head "https://github.com/TheBarmaEffect/sovereign-vision.git", branch: "main"

  depends_on "python@3.12"
  depends_on "openssl@3"   # RFC 3161 notarisation uses `openssl ts`

  resource "numpy" do
    url "https://files.pythonhosted.org/packages/source/n/numpy/numpy-2.1.3.tar.gz"
    sha256 "aa08e04e08aaf974d4458def539dece0d28146d866a39da5639596f4921fd761"
  end

  resource "Pillow" do
    url "https://files.pythonhosted.org/packages/source/P/Pillow/pillow-11.0.0.tar.gz"
    sha256 "72bacbaf24ac003fea9bff9837d1eedb6088758d41e100c1552930151f677739"
  end

  resource "opencv-python-headless" do
    url "https://files.pythonhosted.org/packages/source/o/opencv-python-headless/opencv-python-headless-4.10.0.84.tar.gz"
    sha256 "f2017c6101d7c2ef8d7bc3b414c37ff7f54d64413a1847d89970b6b7069b4e1a"
  end

  resource "rich" do
    url "https://files.pythonhosted.org/packages/source/r/rich/rich-13.9.4.tar.gz"
    sha256 "439594978a49a09530cff7ebc4b5c7103ef57b3e3aaad8d51ee9e1b6dccfeb15"
  end

  resource "pydantic" do
    url "https://files.pythonhosted.org/packages/source/p/pydantic/pydantic-2.10.3.tar.gz"
    sha256 "cb5ac360ce894ceacd69c403187900a02c4b20b693a9dd1d643e1effab9eadf9"
  end

  resource "structlog" do
    url "https://files.pythonhosted.org/packages/source/s/structlog/structlog-24.4.0.tar.gz"
    sha256 "b27bfecede327a6e2dc1eaa55b34ce8e1bb6e8bcd3673b69f5a3b4f5ba3a0cae"
  end

  resource "PyYAML" do
    url "https://files.pythonhosted.org/packages/source/P/PyYAML/PyYAML-6.0.2.tar.gz"
    sha256 "d584d9ec91ad65861cc08d42e834324ef890a082e591037abe114850ff7bbc3e"
  end

  def install
    virtualenv_install_with_resources
    # Install the sovereign CLI
    bin.install_symlink libexec/"bin/sovereign"
    bin.install_symlink libexec/"bin/sovereign-vision"
  end

  def caveats
    <<~EOS
      Sovereign Vision is installed.

      To run the dashboard:
        sovereign demo

      To run in production mode (no RAW panel):
        sovereign demo --production

      For Apple Silicon + MLX inference, install mlx separately:
        pip install mlx

      Source and docs: https://github.com/TheBarmaEffect/sovereign-vision
    EOS
  end

  test do
    # Smoke test: CLI should print version + the 7 default rules.
    output = shell_output("#{bin}/sovereign info")
    assert_match "Sovereign Vision", output
    assert_match "SV-001", output
    assert_match "SV-007", output

    # Constitutional rules JSON should parse.
    assert_match "Person Coordinate Redaction",
                  shell_output("#{bin}/sovereign rules")
  end
end

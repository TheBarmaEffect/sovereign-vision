# Sovereign Vision - Release & Distribution

This repo ships through every reasonable channel a 2026 Python project
can ship through.

| Channel | Command |
|---|---|
| pip from GitHub (any branch/tag) | `pip install git+https://github.com/TheBarmaEffect/sovereign-vision.git` |
| pip from PyPI (after upload) | `pip install sovereign-vision` |
| Homebrew tap | `brew tap TheBarmaEffect/sovereign-vision-tap && brew install sovereign-vision` |
| GitHub release assets | `pip install https://github.com/TheBarmaEffect/sovereign-vision/releases/download/v1.3.0/sovereign_vision-1.3.0-py3-none-any.whl` |
| One-line installer | `curl -sSL https://raw.githubusercontent.com/TheBarmaEffect/sovereign-vision/main/install.sh \| sh` |
| Docker | `docker run -v $PWD/certs:/data ghcr.io/thebarmaeffect/sovereign-vision:latest` |
| GitHub Action | `uses: TheBarmaEffect/sovereign-vision@main` |
| Chrome extension | Load `tools/chrome-extension/` as unpacked |
| iOS | open `ios/SovereignVision/Package.swift` in Xcode |

---

## How to cut a release

### 1. Bump version

Update in three places:

```bash
sed -i '' 's/version = "[^"]*"/version = "1.3.0"/' pyproject.toml
sed -i '' 's/version="[^"]*"/version="1.3.0"/' setup.py
sed -i '' 's/__version__ = "[^"]*"/__version__ = "1.3.0"/' sovereign/__init__.py
```

### 2. Run the constitutional gate

```bash
pytest tests/ -m constitutional -v
```

If any of the 12 zero-PII proofs fail, do not release.

### 3. Build wheel + sdist

```bash
rm -rf dist/
python -m build
```

This produces:
- `dist/sovereign_vision-1.3.0.tar.gz` (sdist)
- `dist/sovereign_vision-1.3.0-py3-none-any.whl` (wheel)

### 4. Tag and push

```bash
git tag -s v1.3.0 -m "Sovereign Vision 1.3.0"
git push --tags
```

### 5. Create the GitHub release

```bash
gh release create v1.3.0 dist/* \
  --title "Sovereign Vision 1.3.0" \
  --notes-file CHANGELOG.md
```

### 6. Upload to PyPI (optional but recommended)

```bash
twine upload dist/*
# or with a scoped token:
TWINE_USERNAME=__token__ TWINE_PASSWORD=pypi-xxxx... twine upload dist/*
```

Get a token at https://pypi.org/manage/account/token/.

---

## Verifying the install worked

```bash
# Fresh venv, install from PyPI:
python -m venv /tmp/verify && source /tmp/verify/bin/activate
pip install sovereign-vision
sovereign info
sovereign doctor
```

Expected:
```
Sovereign Vision v1.3.0
Constitutional rules loaded: 7
  SV-001  [CRITICAL]  Person Coordinate Redaction
  ...
```

---

## Homebrew tap publishing

The formula lives in this repo at `homebrew/sovereign-vision.rb`.

To publish to the tap repo:

```bash
# 1. Create the tap repo (first time only)
gh repo create TheBarmaEffect/sovereign-vision-tap --public --description \
  "Homebrew formulae for Sovereign Vision."

# 2. Clone the tap, copy the formula
git clone https://github.com/TheBarmaEffect/sovereign-vision-tap.git /tmp/tap
mkdir -p /tmp/tap/Formula
cp homebrew/sovereign-vision.rb /tmp/tap/Formula/

# 3. Update the sha256 in the formula to the release tarball
shasum -a 256 dist/sovereign_vision-1.3.0.tar.gz

# 4. Edit the formula's sha256 line and commit
cd /tmp/tap && git add Formula && git commit -m "v1.3.0" && git push

# 5. Anyone can now:
brew tap TheBarmaEffect/sovereign-vision-tap
brew install sovereign-vision
```

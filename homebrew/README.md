# Homebrew tap for Sovereign Vision

The official formula. After this repo cuts a v1.3.0 GitHub release with
the wheel/sdist attached, you can ship the tap with:

```bash
# 1. Create the public tap repo (one-time)
gh repo create TheBarmaEffect/sovereign-vision-tap --public \
  --description "Homebrew formulae for Sovereign Vision."

# 2. Clone it
git clone https://github.com/TheBarmaEffect/sovereign-vision-tap.git /tmp/sv-tap
mkdir -p /tmp/sv-tap/Formula

# 3. Copy this formula into Formula/
cp homebrew/sovereign-vision.rb /tmp/sv-tap/Formula/

# 4. Verify the sha256 matches the released tarball
shasum -a 256 dist/sovereign_vision-1.3.0.tar.gz

# 5. Commit and push the formula
cd /tmp/sv-tap
git add Formula/sovereign-vision.rb
git commit -m "sovereign-vision 1.3.0"
git push
```

Then anyone in the world can:

```bash
brew tap TheBarmaEffect/sovereign-vision-tap
brew install sovereign-vision
sovereign info
```

## Updating for new releases

When you cut v1.4.0:

```bash
# Edit the version + sha256 in the formula
sed -i '' 's|v1.3.0|v1.4.0|g' Formula/sovereign-vision.rb
sed -i '' 's|sovereign_vision-1.3.0|sovereign_vision-1.4.0|g' Formula/sovereign-vision.rb
# Update sha256 line with the new tarball hash
shasum -a 256 dist/sovereign_vision-1.4.0.tar.gz

git commit -am "sovereign-vision 1.4.0" && git push
```

## Notes

- The formula declares `python@3.12` and `openssl@3` as dependencies.
  `openssl` is required for RFC 3161 notarisation via `openssl ts`.
- Resource blocks are pinned to specific source tarballs from PyPI. If
  a transitive dependency's hash changes upstream, regenerate with
  `brew update-python-resources sovereign-vision`.
- Apple Silicon users who want real YOLO26 MLX inference (not just the
  simulation backend) should `pip install mlx` inside the formula's
  virtualenv:
  ```bash
  $(brew --prefix)/opt/sovereign-vision/libexec/bin/pip install mlx
  ```

# Homebrew Cask for File Triage.
# After the first release build, if the dmg checksum differs, update sha256:
#   curl -sL "https://github.com/mattian7741/file-triage/releases/download/v0.1.0/File%20Triage-0.1.0-arm64.dmg" | shasum -a 256
cask "file-triage" do
  version "0.1.0"
  sha256 "943d4f812fc0fe89766b19b57cc8c642533ebe2b7790ee3fc5e829eb461765dc"

  url "https://github.com/mattian7741/file-triage/releases/download/v#{version}/File%20Triage-#{version}-arm64.dmg"
  name "File Triage"
  desc "Desktop file triage — analyse and organise chaotic file collections (Electron + Explorer UI)"
  homepage "https://github.com/mattian7741/file-triage"

  app "File Triage.app"
end

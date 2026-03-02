# Homebrew Cask for File Triage.
# Asset filenames use a dot: File.Triage-<version>-arm64.dmg. Update sha256 if the release is re-built.
cask "file-triage" do
  version "0.1.0"
  sha256 "8a98f08931dfe48d217aea474cc6d42dde4223560c2e8e20a7bf4fb093ac5a62"

  url "https://github.com/mattian7741/file-triage/releases/download/v0.1.2/File.Triage-#{version}-arm64.dmg"
  name "File Triage"
  desc "Desktop file triage — analyse and organise chaotic file collections (Electron + Explorer UI)"
  homepage "https://github.com/mattian7741/file-triage"

  app "File Triage.app"
end

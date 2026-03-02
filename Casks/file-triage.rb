# Homebrew Cask for File Triage.
# After the first release build, get the real sha256:
#   curl -sL "https://github.com/mattian7741/file-triage/releases/download/v0.1.0/File%20Triage-0.1.0.dmg" | shasum -a 256
# Then replace the sha256 below and (if using a tap) push the Cask.
cask "file-triage" do
  version "0.1.0"
  sha256 "0000000000000000000000000000000000000000000000000000000000000000"

  url "https://github.com/mattian7741/file-triage/releases/download/v#{version}/File%20Triage-#{version}.dmg"
  name "File Triage"
  desc "Desktop file triage — analyse and organise chaotic file collections (Electron + Explorer UI)"
  homepage "https://github.com/mattian7741/file-triage"

  app "File Triage.app"
end

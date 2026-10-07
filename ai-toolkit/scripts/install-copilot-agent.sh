#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 || ! -d "$1" || ( $# -eq 2 && "$2" != "--configure-approvals" ) ]]; then
  echo "Usage: bash ai-toolkit/scripts/install-copilot-agent.sh <workspace-directory> [--configure-approvals]" >&2
  exit 2
fi

source_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
repository_dir="$(cd "$source_dir/.." && pwd)"
workspace="$(cd "$1" && pwd)"
# Refuse aliases and duplicate installations before changing anything.
for rel in .github .github/skills .github/agents .github/instructions .agents .agents/skills .pn-infra-toolkit-backups; do
  if [[ -L "$workspace/$rel" || ( -e "$workspace/$rel" && ! -d "$workspace/$rel" ) ]]; then
    echo "Unsupported directory or symbolic link: $workspace/$rel" >&2
    exit 1
  fi
done
for rel in .agents/skills/pn-infra .agents/skills/pn-infra-ai-toolkit .github/skills/pn-infra-ai-toolkit .github/agents/pn-infra-ai-toolkit.agent.md; do
  if [[ -e "$workspace/$rel" || -L "$workspace/$rel" ]]; then
    echo "Alternative/legacy installation found: $workspace/$rel" >&2
    echo "Archive it explicitly before installing here; no files changed." >&2
    exit 1
  fi
done

sources=(".github/skills/pn-infra" ".github/agents/pn-infra.agent.md" ".github/instructions/pn-infra-ai-toolkit.instructions.md")
targets=(".github/skills/pn-infra" ".github/agents/pn-infra.agent.md" ".github/instructions/pn-infra-ai-toolkit.instructions.md")
for i in 0 1 2; do
  src="$repository_dir/${sources[$i]}"
  dst="$workspace/${targets[$i]}"
  if [[ ! -e "$src" || -L "$src" || -L "$dst" ]]; then
    echo "Missing source or unsupported symbolic link: $src -> $dst" >&2
    exit 1
  fi
  if [[ -e "$dst" ]]; then
    if [[ "$i" == 0 && ! -d "$dst" || "$i" != 0 && ! -f "$dst" ]]; then
      echo "Unexpected destination type: $dst" >&2
      exit 1
    fi
  fi
done

backup=""
for i in 0 1 2; do
  src="$repository_dir/${sources[$i]}"
  dst="$workspace/${targets[$i]}"
  if [[ -e "$dst" ]] && diff -qr "$src" "$dst" >/dev/null 2>&1; then
    echo "Already current: ${targets[$i]}"
    continue
  fi
  if [[ -z "$backup" ]]; then
    mkdir -p "$workspace/.pn-infra-toolkit-backups"
    backup="$(mktemp -d "$workspace/.pn-infra-toolkit-backups/install-XXXXXXXX")"
    echo "Recovery directory: $backup (local only; do not commit)"
  fi
  # Prepare the new component before moving any existing version.
  cp -R "$src" "$backup/new-$i"
  mkdir -p "$(dirname "$dst")"
  if [[ -e "$dst" ]]; then
    mkdir -p "$backup/previous/$(dirname "${targets[$i]}")"
    mv "$dst" "$backup/previous/${targets[$i]}"
  fi
  if ! mv "$backup/new-$i" "$dst"; then
    echo "Installation interrupted. Previous files are preserved in $backup/previous." >&2
    echo "Restore the affected component before continuing." >&2
    exit 1
  fi
  echo "Installed: ${targets[$i]}"
done
echo "Skill (including evals/fixtures), persona and instructions installed."
echo "Open a new Copilot chat and select pn-infra-agent."

if [[ "${2:-}" != "--configure-approvals" ]]; then
  exit 0
fi

preset="$source_dir/copilot/terminal-approvals.settings.json"
settings="$workspace/.vscode/settings.json"
echo "Optional VS Code terminal approval preset for this workspace, not just pn-infra-agent."
echo "Allows common reads; copy/move/delete and general shell/Node/Python execution require approval."
echo "Preserves built-in protection rules. Other inherited approvals may still apply."
echo "Organization policies and Allow All/Autopilot can change the effective behavior."
printf 'Create workspace settings with this preset? [y/N] '
answer=""
if ! IFS= read -r answer; then
  echo "No confirmation received; permissions unchanged."
  exit 0
fi
case "$answer" in
  y|Y|yes|YES) ;;
  *) echo "Permissions unchanged."; exit 0 ;;
esac

# Never overwrite existing JSONC: it may contain comments or user-specific rules.
if [[ -L "$workspace/.vscode" || -L "$settings" ]]; then
  echo "Refusing to configure permissions through a symbolic link." >&2
  exit 1
fi
if [[ -e "$settings" ]]; then
  if cmp -s "$preset" "$settings"; then
    echo "Approval preset already installed."
    exit 0
  fi
  echo "Existing settings preserved: $settings" >&2
  echo "Review and merge $preset manually in VS Code; no permission settings changed." >&2
  exit 1
fi
mkdir -p "$workspace/.vscode"
cp -n "$preset" "$settings"
if ! cmp -s "$preset" "$settings"; then
  echo "Settings changed concurrently; existing content preserved. Review manually." >&2
  exit 1
fi
echo "Created: $settings"
echo "Use the normal/manual permission mode, not Allow All or Autopilot."
echo "Review effective settings in VS Code; this preset is not a security sandbox."

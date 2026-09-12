#!/bin/bash
set -e

# ── colours ──────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✔ $1${NC}"; }
info() { echo -e "${YELLOW}▸ $1${NC}"; }
err()  { echo -e "${RED}✘ $1${NC}"; exit 1; }

echo ""
echo "════════════════════════════════════════════════════"
echo "   n8n Social Media Poster — Auto Setup"
echo "════════════════════════════════════════════════════"
echo ""

# ── 1. Check Node.js ─────────────────────────────────────────────────────────
info "Checking Node.js..."
command -v node >/dev/null 2>&1 || err "Node.js is not installed. Install it from https://nodejs.org then re-run this script."
NODE_VER=$(node -v)
ok "Node.js found: $NODE_VER"

# ── 2. Check npm ─────────────────────────────────────────────────────────────
command -v npm >/dev/null 2>&1 || err "npm not found. Please install Node.js from https://nodejs.org"
ok "npm found: $(npm -v)"

# ── 3. Check n8n ─────────────────────────────────────────────────────────────
info "Checking n8n..."
command -v n8n >/dev/null 2>&1 || err "n8n is not installed. Run: npm install -g n8n"
ok "n8n found: $(n8n --version 2>/dev/null || echo 'installed')"

# ── 4. Clone or update the repo ──────────────────────────────────────────────
INSTALL_DIR="$HOME/n8n-social-media-poster"
REPO_URL="https://github.com/MShaheerRiaz/data-scientist-ai-era.git"

if [ -d "$INSTALL_DIR" ]; then
  info "Folder already exists — pulling latest changes..."
  git -C "$INSTALL_DIR" pull origin claude/n8n-social-media-node-JI7pR 2>/dev/null || true
  ok "Updated"
else
  info "Downloading the node package..."
  # Sparse checkout — only grab the node package subfolder, not the whole repo
  git clone \
    --no-checkout \
    --depth 1 \
    --branch claude/n8n-social-media-node-JI7pR \
    "$REPO_URL" "$INSTALL_DIR" 2>/dev/null
  cd "$INSTALL_DIR"
  git sparse-checkout init --cone
  git sparse-checkout set n8n-nodes-social-media-poster
  git checkout
  ok "Downloaded"
fi

# Move into the actual package folder
PKG_DIR="$INSTALL_DIR/n8n-nodes-social-media-poster"
cd "$PKG_DIR"
ok "Working in: $PKG_DIR"

# ── 5. Install dependencies ──────────────────────────────────────────────────
info "Installing dependencies (this takes ~15 seconds)..."
npm install --silent
ok "Dependencies installed"

# ── 6. Build ─────────────────────────────────────────────────────────────────
info "Building the node package..."
npm run build
ok "Build complete"

# ── 7. Persist the env var in shell profile ──────────────────────────────────
EXPORT_LINE="export N8N_CUSTOM_EXTENSIONS=\"$PKG_DIR\""
EXPORT_MARKER="# n8n-social-media-poster"

add_to_profile() {
  local PROFILE="$1"
  if [ -f "$PROFILE" ]; then
    if grep -q "n8n-social-media-poster" "$PROFILE"; then
      info "Shell profile already configured — skipping"
    else
      echo "" >> "$PROFILE"
      echo "$EXPORT_MARKER" >> "$PROFILE"
      echo "$EXPORT_LINE" >> "$PROFILE"
      ok "Added to $PROFILE"
    fi
  fi
}

info "Configuring shell profile..."
SHELL_NAME=$(basename "$SHELL")
if [ "$SHELL_NAME" = "zsh" ]; then
  add_to_profile "$HOME/.zshrc"
elif [ "$SHELL_NAME" = "bash" ]; then
  # Add to both — macOS uses .bash_profile, Linux uses .bashrc
  add_to_profile "$HOME/.bash_profile"
  add_to_profile "$HOME/.bashrc"
else
  # Fallback: try both common ones
  add_to_profile "$HOME/.zshrc"
  add_to_profile "$HOME/.bashrc"
fi

# Apply to the current session too
export N8N_CUSTOM_EXTENSIONS="$PKG_DIR"

# ── 8. Done ───────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════"
echo -e "${GREEN}   All done! Setup complete.${NC}"
echo "════════════════════════════════════════════════════"
echo ""
echo "The following 6 nodes are now ready in n8n:"
echo "  • Twitter / X Poster"
echo "  • Facebook Page Poster"
echo "  • Instagram Poster"
echo "  • LinkedIn Poster"
echo "  • Bluesky Poster"
echo "  • Threads Poster"
echo ""
echo "To start n8n, open a new terminal and run:"
echo ""
echo -e "   ${GREEN}n8n start${NC}"
echo ""
echo "Then open: http://localhost:5678"
echo "Search for any of the node names above in the node panel."
echo ""

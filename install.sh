#!/bin/bash
# ═══════════════════════════════════════════════════════════════
#  WA0O LEDMatrix Ham Radio Plugin Bundle — Installer
#  https://github.com/jwussler/wa0o-ledmatrix-plugins
#
#  Usage: git clone ... && cd wa0o-ledmatrix-plugins && bash install.sh
# ═══════════════════════════════════════════════════════════════
set -e

LEDMATRIX_DIR="$HOME/LEDMatrix"
DXCLUSTER_DIR="$HOME/DXClusterAPI"
DXCLUSTER_REPO="https://github.com/int2001/DXClusterAPI.git"
DXCLUSTER_BRANCH="dockerized"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CACHE_DIR="/var/cache/ledmatrix"

# ─── Colors ───────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

print_header() {
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo ""
}

print_step() { echo -e "  ${GREEN}[✓]${NC} $1"; }
print_warn() { echo -e "  ${YELLOW}[!]${NC} $1"; }
print_error() { echo -e "  ${RED}[✗]${NC} $1"; }

# ─── Docker helper: tries without sudo first, then with sudo ──
run_docker() {
    if docker "$@" 2>/dev/null; then
        return 0
    elif sudo docker "$@" 2>/dev/null; then
        return 0
    else
        return 1
    fi
}

run_docker_compose() {
    if docker compose "$@" 2>&1; then
        return 0
    elif sudo docker compose "$@" 2>&1; then
        return 0
    elif docker-compose "$@" 2>&1; then
        return 0
    elif sudo docker-compose "$@" 2>&1; then
        return 0
    else
        return 1
    fi
}

# ═════════════════════════════════════════════════════════════════
# PREFLIGHT CHECKS
# ═════════════════════════════════════════════════════════════════
print_header "WA0O LEDMatrix Ham Radio Plugin Bundle"

echo "  This installer will set up:"
echo ""
echo "    ★ DXClusterAPI      Real-time DX spot caching backend (Docker)"
echo "    ★ hamradio-spots    DX spots, solar, propagation, POTA, Top 50 alerts"
echo "    ★ weather-alerts    NWS tiered warnings with chevron display takeover"
echo "    ★ contest-countdown Countdown timers for 55 worldwide ham radio contests"
echo "    ★ wavelog-qsos      Recent contacts from your Wavelog instance"
echo "    ★ news              Scrolling RSS news ticker"
echo "    ★ ux_constants      Shared display module for consistent UX"
echo ""

# Check LEDMatrix
if [ ! -d "$LEDMATRIX_DIR" ]; then
    print_error "LEDMatrix not found at $LEDMATRIX_DIR"
    echo ""
    echo "  This plugin bundle requires LEDMatrix to already be installed."
    echo "  Install LEDMatrix first: https://github.com/ChuckBuilds/LEDMatrix"
    echo "  Then re-run this script."
    exit 1
fi
print_step "LEDMatrix found at $LEDMATRIX_DIR"

# Check plugin directory exists
if [ ! -d "$SCRIPT_DIR/plugins" ]; then
    print_error "plugins/ directory not found — are you running from the repo root?"
    exit 1
fi

# ═════════════════════════════════════════════════════════════════
# STATION CONFIGURATION
# ═════════════════════════════════════════════════════════════════
print_header "Step 1: Your Station Configuration"

echo -e "  ${BOLD}DX Cluster Connection${NC}"
echo ""

read -rp "  Your callsign for DX cluster login (e.g. N0CALL-3): " USER_DXCALL
while [ -z "$USER_DXCALL" ]; do
    echo -e "  ${RED}Callsign is required.${NC}"
    read -rp "  Your callsign: " USER_DXCALL
done
# Confirm callsign to avoid typos
echo -e "  ${YELLOW}You entered: ${BOLD}${USER_DXCALL}${NC}"
read -rp "  Is this correct? (Y/n): " CALL_CONFIRM
if [[ "$CALL_CONFIRM" =~ ^[Nn]$ ]]; then
    read -rp "  Your callsign: " USER_DXCALL
    while [ -z "$USER_DXCALL" ]; do
        read -rp "  Your callsign: " USER_DXCALL
    done
fi
# Extract base callsign (strip SSID like -3)
USER_CALLSIGN="${USER_DXCALL%%-*}"

read -rp "  Your Maidenhead grid square [FN31]: " USER_GRID
USER_GRID="${USER_GRID:-FN31}"

echo ""
echo -e "  ${BOLD}Wavelog Integration${NC}"
echo "  DXClusterAPI and Wavelog QSOs need your Wavelog instance."
echo ""

read -rp "  Wavelog base URL (e.g. https://your-wavelog.com/index.php): " USER_WAVELOG_INPUT
while [ -z "$USER_WAVELOG_INPUT" ]; do
    echo -e "  ${RED}Wavelog URL is required for DXCC lookups.${NC}"
    read -rp "  Wavelog base URL: " USER_WAVELOG_INPUT
done

# Normalize the Wavelog URL — strip trailing slash, ensure /api/lookup for DXClusterAPI
USER_WAVELOG_INPUT="${USER_WAVELOG_INPUT%/}"
# Strip /api/lookup if they included it, we'll add it ourselves
USER_WAVELOG_BASE=$(echo "$USER_WAVELOG_INPUT" | sed 's|/api/lookup.*||')
# Build the full lookup URL for DXClusterAPI
USER_WAVELOG_LOOKUP="${USER_WAVELOG_BASE}/api/lookup"
print_step "Wavelog lookup URL: ${USER_WAVELOG_LOOKUP}"

read -rsp "  Wavelog API key (input hidden): " USER_WAVELOG_KEY
echo ""
while [ -z "$USER_WAVELOG_KEY" ]; do
    echo -e "  ${RED}API key is required.${NC}"
    read -rsp "  Wavelog API key (input hidden): " USER_WAVELOG_KEY
    echo ""
done

echo ""
echo -e "  ${BOLD}DX Cluster Upstream${NC}"
echo ""

read -rp "  DX Cluster host [dxfun.com]: " USER_DXHOST
USER_DXHOST="${USER_DXHOST:-dxfun.com}"

read -rp "  DX Cluster port [8000]: " USER_DXPORT
USER_DXPORT="${USER_DXPORT:-8000}"

read -rp "  Local API port for DXClusterAPI [8192]: " USER_WEBPORT
USER_WEBPORT="${USER_WEBPORT:-8192}"

read -rp "  Enable POTA spot integration? (y/N): " USER_POTA
if [[ "$USER_POTA" =~ ^[Yy]$ ]]; then
    USER_POTA_ENABLED="true"
    read -rp "  POTA polling interval in seconds [120]: " USER_POTA_INTERVAL
    USER_POTA_INTERVAL="${USER_POTA_INTERVAL:-120}"
else
    USER_POTA_ENABLED="false"
    USER_POTA_INTERVAL="120"
fi

LOCAL_API_URL="http://localhost:${USER_WEBPORT}/dxcache/spots"

echo ""
echo -e "  ${BOLD}Weather Alerts Location${NC}"
echo "  NWS alerts need your coordinates. Find yours at: https://www.latlong.net/"
echo ""

read -rp "  Your latitude [40.7128]: " USER_LAT
USER_LAT="${USER_LAT:-40.7128}"

read -rp "  Your longitude [-74.0060]: " USER_LON
USER_LON="${USER_LON:--74.0060}"

echo ""
echo -e "  ${BOLD}NWS User-Agent${NC}"
echo "  The NWS API requires a contact email in the User-Agent header."
echo ""

read -rp "  Your email for NWS API: " USER_EMAIL
while [ -z "$USER_EMAIL" ]; do
    echo -e "  ${RED}Email is required by the NWS API.${NC}"
    read -rp "  Your email: " USER_EMAIL
done

# ─── Configuration Summary ─────────────────────────────────────
echo ""
echo -e "${CYAN}  ┌───────────────────────────────────────────────────────┐${NC}"
echo -e "${CYAN}  │  Configuration Summary                                │${NC}"
echo -e "${CYAN}  ├───────────────────────────────────────────────────────┤${NC}"
printf  "${CYAN}  │${NC}  Callsign:        %-36s${CYAN}│${NC}\n" "$USER_DXCALL"
printf  "${CYAN}  │${NC}  Base Call:        %-36s${CYAN}│${NC}\n" "$USER_CALLSIGN"
printf  "${CYAN}  │${NC}  Grid:            %-36s${CYAN}│${NC}\n" "$USER_GRID"
printf  "${CYAN}  │${NC}  Wavelog URL:      %-36s${CYAN}│${NC}\n" "$USER_WAVELOG_BASE"
printf  "${CYAN}  │${NC}  Wavelog Lookup:   %-36s${CYAN}│${NC}\n" "$USER_WAVELOG_LOOKUP"
printf  "${CYAN}  │${NC}  Wavelog Key:      %-36s${CYAN}│${NC}\n" "********"
printf  "${CYAN}  │${NC}  DX Cluster:       %-36s${CYAN}│${NC}\n" "${USER_DXHOST}:${USER_DXPORT}"
printf  "${CYAN}  │${NC}  API Port:         %-36s${CYAN}│${NC}\n" "$USER_WEBPORT"
printf  "${CYAN}  │${NC}  POTA:             %-36s${CYAN}│${NC}\n" "$USER_POTA_ENABLED"
printf  "${CYAN}  │${NC}  Location:         %-36s${CYAN}│${NC}\n" "${USER_LAT}, ${USER_LON}"
printf  "${CYAN}  │${NC}  NWS Email:        %-36s${CYAN}│${NC}\n" "$USER_EMAIL"
echo -e "${CYAN}  └───────────────────────────────────────────────────────┘${NC}"
echo ""
read -rp "  Proceed with installation? (Y/n): " CONFIRM
if [[ "$CONFIRM" =~ ^[Nn]$ ]]; then
    echo "  Installation cancelled."
    exit 0
fi

# ═════════════════════════════════════════════════════════════════
# STEP 2: DOCKER
# ═════════════════════════════════════════════════════════════════
print_header "Step 2: Docker & Docker Compose"

if command -v docker &> /dev/null; then
    print_step "Docker already installed: $(docker --version 2>/dev/null || sudo docker --version)"
else
    print_warn "Docker not found — installing..."
    curl -fsSL https://get.docker.com | sudo sh
    sudo usermod -aG docker "$USER"
    print_step "Docker installed"
    print_warn "You were added to the 'docker' group."
fi

# Ensure Docker starts on boot
if ! sudo systemctl is-enabled docker &>/dev/null; then
    sudo systemctl enable docker
    print_step "Docker enabled at boot"
else
    print_step "Docker already enabled at boot"
fi

# Make sure Docker is running right now
if ! sudo systemctl is-active docker &>/dev/null; then
    sudo systemctl start docker
    sleep 2
    print_step "Docker service started"
fi

if docker compose version &> /dev/null || sudo docker compose version &> /dev/null; then
    print_step "Docker Compose available"
elif command -v docker-compose &> /dev/null; then
    print_step "Docker Compose (standalone) available"
else
    print_warn "Docker Compose not found — installing..."
    sudo apt-get update -qq
    sudo apt-get install -y -qq docker-compose-plugin 2>/dev/null || {
        print_warn "Plugin install failed, trying standalone..."
        COMPOSE_URL="https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)"
        sudo curl -SL "$COMPOSE_URL" -o /usr/local/bin/docker-compose
        sudo chmod +x /usr/local/bin/docker-compose
    }
    print_step "Docker Compose installed"
fi

# ═════════════════════════════════════════════════════════════════
# STEP 3: DXClusterAPI
# ═════════════════════════════════════════════════════════════════
print_header "Step 3: DXClusterAPI Backend"

if [ -d "$DXCLUSTER_DIR" ]; then
    print_warn "DXClusterAPI already exists at $DXCLUSTER_DIR"
    read -rp "  Update it? (y/N): " UPDATE_DX
    if [[ "$UPDATE_DX" =~ ^[Yy]$ ]]; then
        cd "$DXCLUSTER_DIR"
        run_docker_compose down || true
        git fetch origin
        git checkout "$DXCLUSTER_BRANCH"
        git pull origin "$DXCLUSTER_BRANCH"
        print_step "DXClusterAPI updated"
    else
        print_step "Keeping existing DXClusterAPI"
    fi
else
    echo "  Cloning DXClusterAPI..."
    git clone "$DXCLUSTER_REPO" "$DXCLUSTER_DIR"
    cd "$DXCLUSTER_DIR"
    git checkout "$DXCLUSTER_BRANCH"
    print_step "DXClusterAPI cloned (branch: $DXCLUSTER_BRANCH)"
fi

cd "$DXCLUSTER_DIR"

# Write docker-compose.yaml — uses build: . for ARM/Pi compatibility
# The prebuilt ghcr.io image is amd64 only, so we must build locally
cat > "$DXCLUSTER_DIR/docker-compose.yaml" << COMPOSEEOF
services:
  dxcache:
    build: .
    container_name: dxcache
    environment:
      MAXCACHE: 10000
      WEBPORT: ${USER_WEBPORT}
      WAVELOG_URL: ${USER_WAVELOG_LOOKUP}
      WEBURL: /dxcache
      WAVELOG_KEY: ${USER_WAVELOG_KEY}
      DXHOST: ${USER_DXHOST}
      DXPORT: ${USER_DXPORT}
      DXCALL: ${USER_DXCALL}
      POTA_INTEGRATION: ${USER_POTA_ENABLED}
      POTA_POLLING_INTERVAL: ${USER_POTA_INTERVAL}
    ports:
      - ${USER_WEBPORT}:${USER_WEBPORT}
    restart: unless-stopped
COMPOSEEOF
print_step "docker-compose.yaml configured (local build for ARM)"

# Build and start container — use sudo since user may not be in docker group yet
echo "  Building and starting DXClusterAPI container..."
echo "  (first build may take a few minutes on Raspberry Pi)"
echo ""
if sudo docker compose up -d --build; then
    print_step "DXClusterAPI built and started"
elif sudo docker-compose up -d --build; then
    print_step "DXClusterAPI built and started (standalone compose)"
else
    print_error "Failed to build/start DXClusterAPI"
    echo "    Try manually: cd $DXCLUSTER_DIR && sudo docker compose up -d --build"
fi

# Wait for API
echo ""
echo "  Waiting for API to respond (this may take 30-60 seconds)..."
API_READY=false
for i in $(seq 1 30); do
    if curl -s --max-time 2 "$LOCAL_API_URL" > /dev/null 2>&1; then
        print_step "DXClusterAPI responding at $LOCAL_API_URL"
        API_READY=true
        break
    fi
    sleep 2
    printf "."
done
echo ""
if [ "$API_READY" = false ]; then
    print_warn "API not responding yet — it may need more time to connect"
    print_warn "Check status: sudo docker logs dxcache --tail 20"
fi

# ═════════════════════════════════════════════════════════════════
# STEP 4: SHARED UX MODULE
# ═════════════════════════════════════════════════════════════════
print_header "Step 4: Shared UX Module"

cd "$SCRIPT_DIR"

if [ -f "$SCRIPT_DIR/ux_constants.py" ]; then
    cp "$SCRIPT_DIR/ux_constants.py" "$LEDMATRIX_DIR/ux_constants.py"
    print_step "ux_constants.py installed to $LEDMATRIX_DIR/"
else
    print_warn "ux_constants.py not found in bundle"
fi

# ═════════════════════════════════════════════════════════════════
# STEP 5: INSTALL PLUGINS
# ═════════════════════════════════════════════════════════════════
print_header "Step 5: Installing Plugins"

install_plugin() {
    local NAME="$1"
    local SRC="$SCRIPT_DIR/plugins/$NAME"
    local DEST="$LEDMATRIX_DIR/plugin-repos/$NAME"

    if [ ! -d "$SRC" ]; then
        print_warn "$NAME — not found in bundle, skipping"
        return
    fi

    # Backup existing
    if [ -d "$DEST" ]; then
        local BACKUP="${DEST}.bak.$(date +%Y%m%d_%H%M%S)"
        cp -r "$DEST" "$BACKUP"
        print_warn "$NAME — backed up existing to $(basename $BACKUP)"
    fi

    mkdir -p "$DEST"

    # Copy all files
    cp -r "$SRC"/* "$DEST/" 2>/dev/null || true

    # Clear old pycache
    rm -rf "$DEST/__pycache__"

    # Install Python dependencies
    if [ -f "$DEST/requirements.txt" ]; then
        pip install -r "$DEST/requirements.txt" --break-system-packages -q 2>/dev/null || true
    fi

    local LINES=""
    if [ -f "$DEST/manager.py" ]; then
        LINES=" ($(wc -l < "$DEST/manager.py") lines)"
    fi
    print_step "$NAME installed${LINES}"
}

install_plugin "hamradio-spots"
install_plugin "weather-alerts"
install_plugin "contest-countdown"
install_plugin "wavelog-qsos"
install_plugin "news"

# ═════════════════════════════════════════════════════════════════
# STEP 6: CONFIGURE PLUGINS WITH USER DATA
# ═════════════════════════════════════════════════════════════════
print_header "Step 6: Plugin Configuration"

# ─── Patch weather-alerts with user's email and coordinates ────
WA_MANAGER="$LEDMATRIX_DIR/plugin-repos/weather-alerts/manager.py"
if [ -f "$WA_MANAGER" ]; then
    sed -i "s|your-email@example.com|${USER_EMAIL}|g" "$WA_MANAGER"
    print_step "weather-alerts: set NWS User-Agent email"
fi

# ─── Write plugin configs into LEDMatrix config ──────
CONFIG_FILE="$LEDMATRIX_DIR/config/config.json"
if [ -f "$CONFIG_FILE" ]; then
    if python3 -c "
import json
with open('$CONFIG_FILE') as f:
    c = json.load(f)

# ── Enable Vegas mode with ham-only rotation ──
vs = c.get('display', {}).get('vegas_scroll', {})
vs['enabled'] = True
vs['plugin_order'] = ['hamradio-spots', 'weather-alerts', 'contest-countdown', 'wavelog-qsos']
vs['excluded_plugins'] = []
c.setdefault('display', {})['vegas_scroll'] = vs

# ── hamradio-spots: all views except contest, all modes, all display options ──
hs = c.get('hamradio-spots', {})
if not hs.get('api_url'):
    hs['api_url'] = '$LOCAL_API_URL'
    hs['my_grid'] = '$USER_GRID'
    hs['my_callsign'] = '$USER_CALLSIGN'
hs['enabled'] = True
hs['vegas_views'] = [
    'dashboard', 'spots', 'conditions', 'hotspots', 'map', 'grayline',
    'clock', 'bestband', 'pota', 'spacewx', 'stats', 'continents',
    'bandopen', 'rate', 'distance', 'longpath', 'beacon', 'muf'
]
hs['priority_enabled'] = True
hs['show_voice'] = True
hs['show_cw'] = True
hs['show_digital'] = True
hs['show_flags'] = True
hs['show_frequency'] = True
hs['show_age'] = True
c['hamradio-spots'] = hs

# ── weather-alerts ──
wa = c.get('weather-alerts', {})
if not wa.get('latitude'):
    wa['latitude'] = float('$USER_LAT')
    wa['longitude'] = float('$USER_LON')
wa['enabled'] = True
c['weather-alerts'] = wa

# ── wavelog-qsos ──
wq = c.get('wavelog-qsos', {})
if not wq.get('api_key'):
    wq['wavelog_url'] = '$USER_WAVELOG_BASE'
    wq['api_key'] = '$USER_WAVELOG_KEY'
wq['enabled'] = True
c['wavelog-qsos'] = wq

# ── contest-countdown (enabled) ──
cc = c.get('contest-countdown', {})
cc['enabled'] = True
c['contest-countdown'] = cc

# ── news (installed but disabled by default) ──
ns = c.get('news', {})
ns['enabled'] = False
c['news'] = ns

# ── web-ui-info (disabled) ──
wu = c.get('web-ui-info', {})
wu['enabled'] = False
c['web-ui-info'] = wu

with open('$CONFIG_FILE', 'w') as f:
    json.dump(c, f, indent=2)
print('OK')
" 2>/dev/null; then
        print_step "Vegas mode enabled, ham radio plugins configured"
    else
        print_warn "Could not auto-configure config.json — configure via web UI"
    fi
else
    print_warn "config.json not found — configure plugins via the LEDMatrix web UI"
fi

# ═════════════════════════════════════════════════════════════════
# STEP 7: SYSTEMD — ENSURE LEDMATRIX WAITS FOR DOCKER
# ═════════════════════════════════════════════════════════════════
print_header "Step 7: Boot Order Configuration"

OVERRIDE_DIR="/etc/systemd/system/ledmatrix.service.d"
OVERRIDE_FILE="$OVERRIDE_DIR/override.conf"

if [ ! -f "$OVERRIDE_FILE" ]; then
    sudo mkdir -p "$OVERRIDE_DIR"
    sudo bash -c "cat > $OVERRIDE_FILE" << 'OVERRIDEEOF'
[Unit]
After=docker.service
Requires=docker.service

[Service]
ExecStartPre=/bin/sleep 30
OVERRIDEEOF
    sudo systemctl daemon-reload
    print_step "LEDMatrix will wait for Docker + 30s for API to cache spots"
else
    if grep -q "ExecStartPre" "$OVERRIDE_FILE" 2>/dev/null; then
        print_step "Boot delay already configured"
    else
        sudo bash -c "cat >> $OVERRIDE_FILE" << 'OVERRIDEEOF'

[Service]
ExecStartPre=/bin/sleep 30
OVERRIDEEOF
        sudo systemctl daemon-reload
        print_step "Added 30s startup delay for spot caching"
    fi
        sudo systemctl daemon-reload
        print_step "Added Docker dependency to existing override"
    fi
fi

# ═════════════════════════════════════════════════════════════════
# STEP 8: VERIFY & RESTART
# ═════════════════════════════════════════════════════════════════
print_header "Step 8: Verify & Restart"

echo "  Syntax checking all plugins..."
ALL_OK=true
for DIR in "$LEDMATRIX_DIR"/plugin-repos/*/; do
    if [ -f "$DIR/manager.py" ]; then
        NAME=$(basename "$DIR")
        if python3 -c "import ast; ast.parse(open('${DIR}manager.py').read())" 2>/dev/null; then
            print_step "$NAME — OK"
        else
            print_error "$NAME — SYNTAX ERROR"
            ALL_OK=false
        fi
    fi
done

echo ""
echo "  Clearing caches..."
sudo rm -rf "$LEDMATRIX_DIR"/plugin-repos/*/__pycache__
sudo rm -rf "$CACHE_DIR"/* 2>/dev/null || true
print_step "Caches cleared"

echo "  Restarting LEDMatrix..."
sudo systemctl restart ledmatrix
print_step "LEDMatrix restarted"

# Quick log check
sleep 5
echo ""
echo "  Checking startup logs..."
echo ""
sudo journalctl -u ledmatrix --since "10 seconds ago" --no-pager 2>/dev/null \
    | grep -iE "loaded|error|fail|hamradio|weather|contest|wavelog|news|SEGMENT|ordered" \
    | head -20

# ═════════════════════════════════════════════════════════════════
# DONE
# ═════════════════════════════════════════════════════════════════
print_header "Installation Complete!"

echo -e "  ${GREEN}DXClusterAPI:${NC}   $DXCLUSTER_DIR"
echo -e "  ${GREEN}Spots API:${NC}      $LOCAL_API_URL"
echo -e "  ${GREEN}Plugins:${NC}        $LEDMATRIX_DIR/plugin-repos/"
echo -e "  ${GREEN}Shared UX:${NC}      $LEDMATRIX_DIR/ux_constants.py"
echo ""
echo "  ┌─────────────────────────────────────────────────────┐"
echo "  │  Useful Commands                                    │"
echo "  ├─────────────────────────────────────────────────────┤"
echo "  │  Check spots:     curl -s $LOCAL_API_URL | python3 -m json.tool | head"
echo "  │  API stats:       curl -s http://localhost:${USER_WEBPORT}/dxcache/stats"
echo "  │  Spot count:      curl -s $LOCAL_API_URL | python3 -c \"import sys,json; print(len(json.load(sys.stdin)))\" "
echo "  │  Plugin logs:     sudo journalctl -u ledmatrix -f"
echo "  │  DXCluster logs:  cd $DXCLUSTER_DIR && sudo docker compose logs -f"
echo "  │  Restart display: sudo systemctl restart ledmatrix"
echo "  │  Restart DXCache: cd $DXCLUSTER_DIR && sudo docker compose restart"
echo "  └─────────────────────────────────────────────────────┘"
echo ""
echo "  ┌─────────────────────────────────────────────────────┐"
echo "  │  Test Weather Alerts                                │"
echo "  ├─────────────────────────────────────────────────────┤"
echo "  │  Tornado warning:  python3 ~/LEDMatrix/plugin-repos/weather-alerts/test_alerts.py tornado"
echo "  │  Watch:            python3 ~/LEDMatrix/plugin-repos/weather-alerts/test_alerts.py watch"
echo "  │  Clear test:       python3 ~/LEDMatrix/plugin-repos/weather-alerts/test_alerts.py clear"
echo "  └─────────────────────────────────────────────────────┘"
echo ""
echo "  ┌─────────────────────────────────────────────────────┐"
echo "  │  Contest Calendar                                   │"
echo "  ├─────────────────────────────────────────────────────┤"
echo "  │  View calendar:    python3 ~/LEDMatrix/plugin-repos/contest-countdown/contest_calendar.py"
echo "  │  Future year:      python3 ~/LEDMatrix/plugin-repos/contest-countdown/contest_calendar.py 2030"
echo "  └─────────────────────────────────────────────────────┘"
echo ""
echo "  ┌─────────────────────────────────────────────────────┐"
echo "  │  Update Plugins                                     │"
echo "  ├─────────────────────────────────────────────────────┤"
echo "  │  cd ~/wa0o-ledmatrix-plugins && git pull && bash install.sh"
echo "  └─────────────────────────────────────────────────────┘"
echo ""
echo -e "  ${CYAN}73 de ${USER_CALLSIGN}!${NC}"
echo ""

# ─── Reboot to apply Docker group, systemd override, etc. ─────
echo ""
read -rp "  Reboot now to apply all changes? (Y/n): " REBOOT
if [[ ! "$REBOOT" =~ ^[Nn]$ ]]; then
    echo -e "  ${CYAN}Rebooting in 5 seconds...${NC}"
    sleep 5
    sudo reboot
fi

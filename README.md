# 📡 WA0O LEDMatrix Ham Radio Plugins

A plugin bundle for [LEDMatrix](https://github.com/ChuckBuilds/LEDMatrix) that turns a 192×32 RGB LED matrix into a real-time ham radio information display — DX spots, weather alerts, contest countdowns, QSO log, and news — all rotating in "Vegas mode."

![License](https://img.shields.io/badge/license-MIT-green)

---

## Plugins

| Plugin | What it does |
|--------|-------------|
| **hamradio-spots** | Real-time DX cluster spots with 18+ rotating view cards — band activity, solar/propagation data, beacon monitor, POTA/SOTA alerts, Club Log Top 50 Most Wanted with MEGA JACKPOT celebrations |
| **weather-alerts** | Three-tier NWS alert system — full red chevron display takeover for tornado/severe warnings, yellow chevron ticker for watches, info cards for advisories |
| **contest-countdown** | Countdown timers for 55 worldwide contests with perpetual calendar that auto-calculates dates through 2035+ — never needs manual updates |
| **wavelog-qsos** | Recent QSO display from your Wavelog instance with band/mode color coding and country flags |
| **news** | Scrolling RSS news ticker from configurable feeds |

## Requirements

- Raspberry Pi 3B+ or 4 with Adafruit RGB Matrix Bonnet
- [LEDMatrix](https://github.com/ChuckBuilds/LEDMatrix) installed and running
- 192×32 pixel LED matrix (3× 64×32 panels)
- 15A 5V power supply (recommended for full-color displays)
- [Wavelog](https://github.com/wavelog/wavelog) instance with API key
- Docker (installed automatically)

## Install

```bash
git clone https://github.com/jwussler/wa0o-ledmatrix-plugins.git
cd wa0o-ledmatrix-plugins
bash install.sh
```

The installer handles everything interactively:

1. Prompts for your station config — callsign, grid, Wavelog URL/key, DX cluster, coordinates, NWS email
2. Installs Docker if needed
3. Clones and builds [DXClusterAPI](https://github.com/int2001/DXClusterAPI) locally for ARM/Pi compatibility
4. Installs all plugins and shared UX module
5. Enables all plugins in LEDMatrix config
6. Sets up systemd so LEDMatrix waits for Docker on boot
7. Syntax checks everything, clears caches, restarts
8. Offers a reboot to apply all changes

No credentials are stored in the repo — everything is prompted at install time.

## Update

```bash
cd ~/wa0o-ledmatrix-plugins
git pull
bash install.sh
```

Existing plugins are backed up before overwriting.

---

## DXClusterAPI Setup

The **hamradio-spots** plugin uses [DXClusterAPI](https://github.com/int2001/DXClusterAPI) by int2001 — a Dockerized service that connects to a DX cluster via telnet, caches spots, and enriches them with DXCC entity data from Wavelog. The install script handles this automatically, but here's the manual setup if needed.

### docker-compose.yaml

```yaml
services:
  dxcache:
    build: .
    container_name: dxcache
    environment:
      MAXCACHE: 10000
      WEBPORT: 8192
      WAVELOG_URL: https://your-wavelog.com/index.php/api/lookup
      WEBURL: /dxcache
      WAVELOG_KEY: YOUR_API_KEY
      DXHOST: dxfun.com
      DXPORT: 8000
      DXCALL: N0CALL-3
      POTA_INTEGRATION: false
      POTA_POLLING_INTERVAL: 120
    ports:
      - 8192:8192
    restart: unless-stopped
```

> **Important:** Use `build: .` (not `image: ghcr.io/...`) — the prebuilt image is amd64 only and won't run on Raspberry Pi.

> **Important:** `WAVELOG_URL` must end with `/api/lookup` — not just the base URL.

### Popular DX Clusters

| Host | Port | Notes |
|------|------|-------|
| `dxfun.com` | 8000 | Popular US cluster |
| `dxc.ve7cc.net` | 23 | VE7CC (Canada) |
| `dx.k3lr.com` | 7300 | K3LR Super Station |
| `dxc.ai9t.com` | 7373 | AI9T cluster |
| `telnet.reversebeacon.net` | 7000 | Reverse Beacon Network (CW/FT8 skimmer) |

### Build and Start

```bash
cd ~/DXClusterAPI
sudo docker compose up -d --build    # first build takes ~1 min on Pi 4
sudo docker logs dxcache --tail 20   # check connection
curl -s http://localhost:8192/dxcache/stats | python3 -m json.tool
```

### API Endpoints

| Endpoint | Description |
|----------|-------------|
| `/dxcache/spots` | All cached spots |
| `/dxcache/spots/20m` | Spots filtered by band |
| `/dxcache/spot/14195` | Spots near a frequency |
| `/dxcache/stats` | Cache statistics |

---

## Plugin Details

### 🔴 Ham Radio DX Spots

2400+ lines, 18+ rotating view cards:

- **Spot ticker** — real-time DX spots with callsign, frequency, mode, country flags
- **Band activity** — visual bar chart of active bands
- **Solar conditions** — SFI, K-index, A-index
- **Propagation** — MUF estimates and band condition indicators
- **Beacon monitor** — NCDXF/IARU beacon schedule
- **Rate dashboard** — spots/hour with trend indicators
- **POTA/SOTA alerts** — Parks and Summits On The Air activations
- **Top 50 Most Wanted** — Club Log rare DX alerts:
  - Top 10 → MEGA JACKPOT full display takeover
  - 11–50 → gold-bordered alert cards

### 🟡 Weather Alerts

| Tier | Triggers | Display |
|------|----------|---------|
| **1 — Critical** | Tornado Warning, Severe T-Storm Warning, Flash Flood Warning | Full display takeover — red animated chevrons, scrolling warning text |
| **2 — Urgent** | Tornado Watch, Winter Storm Warning, Flood Warning | Yellow chevron ticker every 30 min, then back to rotation |
| **3 — Info** | Wind Advisory, Frost/Freeze, Heat Advisory | Single card in normal rotation |

### 🏆 Contest Countdown

55 contests across NA, EU, Asia, and Oceania with perpetual date calculation:

| Region | Contests |
|--------|----------|
| **North America** | ARRL Field Day, Sweepstakes CW/SSB, DX CW/SSB, NAQP CW/SSB/RTTY, CQ WW SSB/CW/RTTY, CQ WPX SSB/CW/RTTY, CQ 160m CW/SSB, Winter Field Day, ARRL 10m, 160m, RAC Canada Day, RAC Winter |
| **Europe** | WAE DX CW/SSB/RTTY, SAC CW/SSB, EU HF Championship, Dutch PACC, Russian DX, SP DX, Helvetia, King of Spain CW/SSB, OK/OM DX, Ukrainian DX, Croatian CW |
| **Asia/Oceania** | All Asian DX CW/SSB, JIDX CW/SSB, IARU HF Championship, Oceania DX CW/SSB, RSGB IOTA |

Preview the calendar: `python3 ~/LEDMatrix/plugin-repos/contest-countdown/contest_calendar.py 2027`

### 📻 Wavelog QSOs

Recent contacts from your Wavelog instance — callsign with country flag, band/mode color coding, DXCC entity name. Uses incremental caching so only new QSOs are fetched after first sync.

### 📰 News

Scrolling ticker from RSS feeds — AP, NPR, BBC, CNN, sports. Configurable sources.

## Architecture

```
DX Cluster (telnet)           NWS API             Wavelog API        RSS Feeds
       │                         │                      │                 │
       ▼                         │                      │                 │
  DXClusterAPI (Docker)          │                      │                 │
  └─ localhost:8192              │                      │                 │
       │                         │                      │                 │
       ▼                         ▼                      ▼                 ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │                        LEDMatrix (Raspberry Pi)                        │
  │                                                                        │
  │  plugin-repos/                                                         │
  │  ├── hamradio-spots/     ←── DXClusterAPI spots + DXCC enrichment      │
  │  ├── weather-alerts/     ←── api.weather.gov alerts                    │
  │  ├── contest-countdown/  ←── perpetual calendar generator              │
  │  ├── wavelog-qsos/       ←── Wavelog REST API                          │
  │  └── news/               ←── RSS feeds                                 │
  │                                                                        │
  │  ux_constants.py ─── shared colors, fonts, layout across all plugins   │
  │                                                                        │
  │  Vegas Mode Rotation ──────────────────────► 192×32 LED Matrix         │
  └────────────────────────────────────────────────────────────────────────┘
```

## Testing

```bash
# Weather alert simulation
python3 ~/LEDMatrix/plugin-repos/weather-alerts/test_alerts.py tornado   # full takeover
python3 ~/LEDMatrix/plugin-repos/weather-alerts/test_alerts.py watch     # yellow ticker
python3 ~/LEDMatrix/plugin-repos/weather-alerts/test_alerts.py advisory  # info card
python3 ~/LEDMatrix/plugin-repos/weather-alerts/test_alerts.py clear     # remove test

# DX priority spot test (Top 10 MEGA JACKPOT)
echo '{"test_priority":true,"callsign":"P5DX","rank":1,"name":"North Korea","band":"20m","freq":"14195000","mode":"SSB"}' > /tmp/hamradio_test_priority.json
rm /tmp/hamradio_test_priority.json   # clear after watching

# Contest calendar
python3 ~/LEDMatrix/plugin-repos/contest-countdown/contest_calendar.py 2026
python3 ~/LEDMatrix/plugin-repos/contest-countdown/contest_calendar.py 2030
```

## Troubleshooting

```bash
# Live plugin logs
sudo journalctl -u ledmatrix -f

# Filter by plugin
sudo journalctl -u ledmatrix -f | grep -i "hamradio\|weather\|contest\|wavelog\|news"

# DXClusterAPI logs
cd ~/DXClusterAPI && sudo docker compose logs -f

# Spots API check
curl -s http://localhost:8192/dxcache/spots | python3 -m json.tool | head
curl -s http://localhost:8192/dxcache/stats | python3 -m json.tool
curl -s http://localhost:8192/dxcache/spots | python3 -c "import sys,json; print(f'{len(json.load(sys.stdin))} spots')"

# Full restart
cd ~/DXClusterAPI && sudo docker compose restart
sudo rm -rf /var/cache/ledmatrix/*
sudo rm -rf ~/LEDMatrix/plugin-repos/*/__pycache__
sudo systemctl restart ledmatrix
```

**No spots?** DXClusterAPI needs 30–60 seconds after start to connect and cache spots. Check `sudo docker logs dxcache --tail 20`.

**Weather alerts blank?** Normal when there are no active alerts for your area. Test with `test_alerts.py tornado`.

**Plugin not loading?** Syntax check: `python3 -c "import ast; ast.parse(open('manager.py').read()); print('OK')"`

**Display dim or flickering?** Upgrade to a 15A 5V power supply.

## Acknowledgments

- **[ChuckBuilds](https://github.com/ChuckBuilds)** — LEDMatrix display framework
- **[int2001](https://github.com/int2001)** — DXClusterAPI backend
- **[Wavelog](https://github.com/wavelog/wavelog)** — Amateur radio logging
- **[National Weather Service](https://api.weather.gov)** — Free alert data

## License

MIT — See [LICENSE](LICENSE) for details.

---

*73 de WA0O — EM48*

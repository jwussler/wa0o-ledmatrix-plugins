# 📡 WA0O LEDMatrix Ham Radio Plugins

A collection of plugins for the [LEDMatrix](https://github.com/ty-porter/LEDMatrix) LED panel display system, purpose-built for amateur radio operators.

Turns a 192×32 RGB LED matrix into a real-time ham radio information display with DX spots, weather alerts, contest countdowns, and more — all rotating in "Vegas mode."

![License](https://img.shields.io/badge/license-GPL--3.0-blue)

---

## What's Included

| Plugin | Description |
|--------|-------------|
| **hamradio-spots** | Real-time DX cluster spots with 18+ view cards: band activity, solar conditions, propagation data, beacon monitoring, POTA/SOTA alerts, and Club Log Top 50 Most Wanted "MEGA JACKPOT" celebrations |
| **weather-alerts** | NWS weather alerts with three-tier response: red animated chevron display takeover for tornado/severe warnings, yellow chevron periodic alerts for watches, and info cards for advisories |
| **contest-countdown** | Countdown timers for major ham radio contests (ARRL, CQ WW, Field Day, etc.) with "ON THE AIR" display during active contests |
| **wavelog-qsos** | Recent QSO display from your Wavelog instance with band/mode color coding and country flags |
| **news** | Scrolling news ticker pulling from RSS feeds (configurable sources) |
| **ux_constants.py** | Shared display constants ensuring consistent colors, fonts, and layout across all plugins |

## Requirements

- **Raspberry Pi** (3B+ or 4 recommended) with **Adafruit RGB Matrix Bonnet**
- **LEDMatrix** software installed and running
- **192×32 pixel LED matrix** (3× 64×32 panels)
- **15A 5V power supply** recommended for full-color displays
- **Wavelog** instance for DXCC lookups and QSO data
- **Docker** (installed automatically by the installer)

## Quick Start

```bash
git clone https://github.com/jwussler/wa0o-ledmatrix-plugins.git
cd wa0o-ledmatrix-plugins
bash install.sh
```

The installer will walk you through everything:

1. **Prompt for your station config** — callsign, grid square, Wavelog URL & API key, DX cluster, weather coordinates
2. **Install Docker** if not present
3. **Clone and configure [DXClusterAPI](https://github.com/int2001/DXClusterAPI)** — the spots data backend
4. **Install all plugins** into your LEDMatrix `plugin-repos/` directory
5. **Write your config** with callsign, grid, API URLs, coordinates
6. **Syntax check** all plugins and **restart** LEDMatrix

No API keys or credentials are stored in this repo — everything is prompted at install time.

## Updating

```bash
cd wa0o-ledmatrix-plugins
git pull
bash install.sh
```

The installer backs up your existing plugins before overwriting.

## Plugin Details

### 🔴 Ham Radio DX Spots

The main plugin — 2400+ lines with 18+ rotating view cards:

- **Spot ticker** — scrolling real-time DX spots with callsign, frequency, mode, and country flags
- **Band activity** — visual bar chart showing which bands are hot
- **Solar conditions** — SFI, K-index, A-index from WWV
- **Propagation** — MUF estimates and band condition indicators
- **Beacon monitor** — NCDXF/IARU beacon schedule and expected propagation
- **Rate dashboard** — spots per hour with trend indicators
- **POTA/SOTA alerts** — Parks/Summits On The Air activations
- **Top 50 Most Wanted** — Club Log rare DX jackpot alerts with tiered response:
  - **Top 10** → full display takeover with MEGA JACKPOT celebration
  - **11–50** → gold-bordered drop-in alert cards

### 🟡 Weather Alerts

Three-tier NWS alert system:

| Tier | Events | Behavior |
|------|--------|----------|
| **Tier 1** | Tornado Warning, Severe T-Storm Warning, Flash Flood Warning | Full display takeover with red animated chevron borders and scrolling warning text |
| **Tier 2** | Tornado Watch, Winter Storm Warning, Flood Warning | Yellow chevron ticker, plays once every 30 min then returns to rotation |
| **Tier 3** | Wind Advisory, Frost/Freeze, Heat Advisory | Single info card in normal rotation |

### 🏆 Contest Countdown

Tracks upcoming ham radio contests with countdown timers. Shows "ON THE AIR" during active contests. Supports ARRL, CQ WW, Field Day, Sweepstakes, and more.

### 📻 Wavelog QSOs

Displays your recent contacts pulled from Wavelog with:

- Callsign with country flag
- Band and mode (color-coded to match hamradio-spots)
- DXCC entity name
- Incremental caching — only pulls new QSOs after first sync

### 📰 News

Scrolling news ticker from configurable RSS feeds. Default sources include AP, NPR, BBC, CNN, and sports feeds.

## Architecture

```
DX Cluster (telnet)           NWS API             Wavelog API
       │                         │                      │
       ▼                         │                      │
  DXClusterAPI (Docker)          │                      │
       │                         │                      │
       ▼                         ▼                      ▼
  ┌──────────────────────────────────────────────────────────┐
  │                    LEDMatrix (Pi)                         │
  │                                                          │
  │  plugin-repos/                                           │
  │  ├── hamradio-spots/  ←── DXClusterAPI spots feed        │
  │  ├── weather-alerts/  ←── NWS api.weather.gov            │
  │  ├── contest-countdown/                                  │
  │  ├── wavelog-qsos/    ←── Wavelog REST API               │
  │  └── news/            ←── RSS feeds                      │
  │                                                          │
  │  Vegas Mode Rotation ──► 192×32 LED Matrix               │
  └──────────────────────────────────────────────────────────┘
```

## Testing

### Weather Alerts

```bash
# Simulate a tornado warning (full display takeover)
python3 ~/LEDMatrix/plugin-repos/weather-alerts/test_alerts.py tornado

# Simulate a severe thunderstorm watch
python3 ~/LEDMatrix/plugin-repos/weather-alerts/test_alerts.py watch

# Simulate a wind advisory
python3 ~/LEDMatrix/plugin-repos/weather-alerts/test_alerts.py advisory

# Clear test alerts
python3 ~/LEDMatrix/plugin-repos/weather-alerts/test_alerts.py clear
```

### DX Spot Priority Alerts

```bash
# Test a Top 10 MEGA JACKPOT alert (North Korea!)
echo '{"callsign":"P5DX","frequency":14195.0}' > /tmp/test_priority_spot.json

# Clear test
rm /tmp/test_priority_spot.json
```

## Troubleshooting

```bash
# Plugin load status
sudo journalctl -u ledmatrix -f

# DXClusterAPI status
cd ~/DXClusterAPI && docker compose logs -f

# Check if spots API is responding
curl -s http://localhost:8192/dxcache/spots | python3 -m json.tool | head

# Check API cache stats
curl -s http://localhost:8192/dxcache/stats

# Full restart (nuclear option)
cd ~/DXClusterAPI && docker compose restart
sudo rm -rf /var/cache/ledmatrix/*
sudo rm -rf ~/LEDMatrix/plugin-repos/*/__pycache__
sudo systemctl restart ledmatrix
```

## Dependencies

- **[DXClusterAPI](https://github.com/int2001/DXClusterAPI)** by int2001 — Dockerized DX cluster JSON API
- **[Wavelog](https://github.com/wavelog/wavelog)** — Web-based amateur radio logging
- **[NWS API](https://api.weather.gov)** — Free National Weather Service alerts
- **[LEDMatrix](https://github.com/ty-porter/LEDMatrix)** — LED matrix display framework

## License

GPL-3.0 — See [LICENSE](LICENSE) for details.

---

*73 de WA0O — EM48*

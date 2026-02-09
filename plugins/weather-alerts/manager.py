"""
Weather Alerts Plugin for LEDMatrix v2.5.0
NWS alerts with tiered response and proper text layout.

TIER 1 (tornado/SVR/flash flood warnings) -> Red chevron ticker, full takeover
TIER 2 (watches, winter storm warning)     -> Yellow chevron ticker, ONE cycle every 30min
                                              + 1 summary card in Vegas rotation
TIER 3 (advisories, statements)            -> 1 info card in Vegas rotation

v2.5.0: T2 no longer takes over display permanently. Runs one ticker cycle
        then cools off for 30 min. Summary card stays in Vegas rotation.
"""
import logging
import requests
import time
import json
import os
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
from src.plugin_system.base_plugin import BasePlugin
from ux_constants import UX, load_fonts

logger = logging.getLogger(__name__)
__version__ = "2.5.0"

PRIORITY_FILE = "/tmp/ledmatrix_weather_alert_active"


class WeatherAlertsPlugin(BasePlugin):
    """NWS Weather Alerts - tiered response with readable text layout"""

    W = UX.WIDTH
    H = UX.HEIGHT
    CHAR_W = UX.CHAR_ADVANCE
    MARGIN = 4
    BORDER_PX = 2
    CHARS_PER_LINE = 30
    ROW1 = 2
    ROW2 = 12
    ROW3 = 22

    # =========================================================================
    # TIER CLASSIFICATION + PRIORITY WEIGHT
    # =========================================================================
    TIER1_EVENTS = {
        "Tornado Warning":              6,
        "Tsunami Warning":              6,
        "Storm Surge Warning":          5,
        "Extreme Wind Warning":         5,
        "Flash Flood Warning":          4,
        "Blizzard Warning":             3,
        "Ice Storm Warning":            3,
        "Dust Storm Warning":           3,
        "Severe Thunderstorm Warning":  2,
        "Excessive Heat Warning":       2,
    }
    TIER2_EVENTS = {
        "Tornado Watch", "Severe Thunderstorm Watch",
        "Flash Flood Watch", "Winter Storm Warning",
        "Flood Warning", "High Wind Warning",
        "Red Flag Warning", "Excessive Heat Watch",
        "Blizzard Watch", "Hurricane Warning",
        "Hurricane Watch", "Tropical Storm Warning",
    }

    COLORS = {
        "Extreme": {"bg": (180, 0, 0), "border": (255, 0, 0),
                    "text": (255, 255, 255), "accent": (255, 255, 0)},
        "Severe":  {"bg": (140, 0, 0), "border": (255, 50, 0),
                    "text": (255, 255, 255), "accent": (255, 200, 0)},
        "Moderate": {"bg": (100, 60, 0), "border": (255, 165, 0),
                     "text": (255, 255, 255), "accent": (255, 200, 50)},
        "Minor":   {"bg": (0, 0, 80), "border": (100, 100, 255),
                    "text": (255, 255, 255), "accent": (200, 200, 255)},
        "Unknown": {"bg": (40, 40, 40), "border": (200, 200, 200),
                    "text": (255, 255, 255), "accent": (200, 200, 200)},
    }

    # Chevron colors per tier
    CHEVRON_COLORS = {
        1: (255, 0, 0),       # Red for T1 (warnings)
        2: (255, 200, 0),     # Yellow for T2 (watches)
    }

    EVENT_SHORT = {
        "Tornado Warning": "TORNADO WARNING",
        "Tornado Watch": "TORNADO WATCH",
        "Severe Thunderstorm Warning": "SVR T-STORM WRN",
        "Severe Thunderstorm Watch": "SVR T-STORM WATCH",
        "Flash Flood Warning": "FLASH FLOOD WRN",
        "Flash Flood Watch": "FLASH FLOOD WATCH",
        "Flood Warning": "FLOOD WARNING",
        "Flood Watch": "FLOOD WATCH",
        "Winter Storm Warning": "WINTER STORM WRN",
        "Winter Storm Watch": "WINTER STORM WATCH",
        "Winter Weather Advisory": "WINTER WX ADVSRY",
        "Blizzard Warning": "BLIZZARD WARNING",
        "Ice Storm Warning": "ICE STORM WARNING",
        "Wind Chill Warning": "WIND CHILL WRN",
        "Wind Chill Advisory": "WIND CHILL ADVSRY",
        "Excessive Heat Warning": "EXTREME HEAT WRN",
        "Heat Advisory": "HEAT ADVISORY",
        "Dense Fog Advisory": "DENSE FOG ADVSRY",
        "Wind Advisory": "WIND ADVISORY",
        "High Wind Warning": "HIGH WIND WARNING",
        "Fire Weather Watch": "FIRE WX WATCH",
        "Red Flag Warning": "RED FLAG WARNING",
        "Special Weather Statement": "SPECIAL WX STMT",
        "Freeze Warning": "FREEZE WARNING",
        "Frost Advisory": "FROST ADVISORY",
        "Dust Storm Warning": "DUST STORM WRN",
    }

    def __init__(self, plugin_id, config, display_manager, cache_manager, plugin_manager):
        super().__init__(plugin_id, config, display_manager, cache_manager, plugin_manager)

        self.latitude = self.config.get("latitude", 40.7128)
        self.longitude = self.config.get("longitude", -74.0060)
        self.check_interval = self.config.get("check_interval", 120)

        self.alerts = []
        self.last_fetch = 0
        self.alert_active = False
        self.has_tier1 = self.has_tier2 = self.has_tier3 = False
        self.fetch_errors = 0
        self.test_active = False

        # Controller checks this for 125 FPS
        self.enable_scrolling = False

        # Ticker state (shared for T1 and T2)
        self._ticker_text = ""
        self._ticker_width = 0
        self._gap_px = 80                # Gap between looping copies
        self._loop_width = 0             # ticker_width + gap
        self._cache_event = None
        self._scroll_start = None

        # T2 periodic cycle state
        self._t2_cycle_active = False
        self._t2_last_cycle_end = 0       # Timestamp when last T2 cycle finished
        self._t2_cooldown = self.config.get("t2_cooldown", 1800)  # 30 min default
        self._t2_cycle_start = None

        # Throttle update() during high FPS
        self._last_update_time = 0
        self._update_throttle = 2.0      # Only call update() every 2s

        # Config
        self._scroll_speed = self.config.get("scroll_speed", 40)

        self.font, font_large = load_fonts(__file__)
        try:
            font_path = Path(__file__).parent.parent.parent / 'assets' / 'fonts' / '4x6-font.ttf'
            self.font_lg = ImageFont.truetype(str(font_path), 12)
        except Exception:
            self.font_lg = self.font

        self.cache_dir = Path("/var/cache/ledmatrix/weather-alerts")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.test_file = "/tmp/weather_alert_test.json"

        logger.info(f"WeatherAlerts v{__version__} init {self.latitude},{self.longitude}")

    # =========================================================================
    # HELPERS
    # =========================================================================
    def _get_tier(self, alert):
        ev = alert.get("event", "")
        if ev in self.TIER1_EVENTS:
            return 1
        if ev in self.TIER2_EVENTS:
            return 2
        return 3

    def _get_weight(self, alert):
        return self.TIER1_EVENTS.get(alert.get("event", ""), 1)

    def _col(self, sev):
        return self.COLORS.get(sev, self.COLORS["Unknown"])

    def _short(self, event):
        return self.EVENT_SHORT.get(event, event.upper()[:20])

    def _parse_time(self, s):
        if not s:
            return None
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None

    def _remaining(self, expires_str):
        exp = self._parse_time(expires_str)
        if not exp:
            return "???"
        d = exp - datetime.now(timezone.utc)
        if d.total_seconds() <= 0:
            return "EXPIRED"
        h = int(d.total_seconds() // 3600)
        m = int((d.total_seconds() % 3600) // 60)
        return f"{h}h{m:02d}m" if h else f"{m}min"

    def _clean_nws_text(self, text):
        if not text:
            return ""
        text = re.sub(r'\.\.\.+', '. ', text)
        text = text.replace("*", "")
        text = text.replace("\n\n", " ")
        text = text.replace("\n", " ")
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        return text

    def _wrap(self, text, width=None):
        if width is None:
            width = self.CHARS_PER_LINE
        text = self._clean_nws_text(text)
        if not text:
            return []
        lines = []
        words = text.split()
        current = ""
        for word in words:
            if not current:
                current = word
            elif len(current) + 1 + len(word) <= width:
                current += " " + word
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines

    def _cx(self, text):
        return max(self.MARGIN, (self.W - len(text) * self.CHAR_W) // 2)

    def _rx(self, text):
        return max(self.MARGIN, self.W - self.MARGIN - len(text) * self.CHAR_W)

    def _stamp_test(self, draw):
        if not self.test_active:
            return
        tx = self.W - 4 * self.CHAR_W - 2
        draw.rectangle([tx - 1, 0, self.W - 1, 9], fill=(0, 0, 0))
        draw.text((tx, 1), "TEST", font=self.font, fill=(255, 0, 255))

    # =========================================================================
    # DATA FETCHING
    # =========================================================================
    def update(self):
        now = time.time()

        if os.path.exists(self.test_file):
            try:
                with open(self.test_file, "r") as f:
                    self.alerts = json.load(f)
                for a in self.alerts:
                    a["_tier"] = self._get_tier(a)
                    a["_weight"] = self._get_weight(a)
                self.alerts.sort(key=lambda al: (al["_tier"], -al["_weight"]))
                self.test_active = True
                self._update_flags()
                self._manage_priority_file()
                logger.info(f"TEST: {len(self.alerts)} alerts "
                           f"T1:{sum(1 for a in self.alerts if a['_tier']==1)} "
                           f"T2:{sum(1 for a in self.alerts if a['_tier']==2)} "
                           f"T3:{sum(1 for a in self.alerts if a['_tier']==3)} "
                           f"Weights:{[a.get('_weight',0) for a in self.alerts if a['_tier']==1]}")
                return
            except Exception as e:
                logger.error(f"Test load error: {e}")

        if now - self.last_fetch < self.check_interval:
            return
        self.last_fetch = now
        self.test_active = False

        try:
            url = f"https://api.weather.gov/alerts/active?point={self.latitude},{self.longitude}"
            headers = {
                "User-Agent": "(LEDMatrix Weather Alerts, your-email@example.com)",
                "Accept": "application/geo+json",
            }
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()

            self.alerts = []
            for feat in resp.json().get("features", []):
                p = feat.get("properties", {})
                a = {
                    "event": p.get("event", "Unknown"),
                    "severity": p.get("severity", "Unknown"),
                    "urgency": p.get("urgency", "Unknown"),
                    "certainty": p.get("certainty", "Unknown"),
                    "headline": p.get("headline", ""),
                    "description": p.get("description", ""),
                    "instruction": p.get("instruction", ""),
                    "onset": p.get("onset") or p.get("effective", ""),
                    "expires": p.get("expires", ""),
                    "sender": p.get("senderName", "NWS"),
                    "areas": p.get("areaDesc", ""),
                }
                a["_tier"] = self._get_tier(a)
                a["_weight"] = self._get_weight(a)
                self.alerts.append(a)

            sev_ord = {"Extreme": 0, "Severe": 1, "Moderate": 2, "Minor": 3, "Unknown": 4}
            self.alerts.sort(key=lambda a: (a["_tier"], -a["_weight"],
                                            sev_ord.get(a["severity"], 5)))
            self._update_flags()
            self.fetch_errors = 0
            self._manage_priority_file()

            try:
                with open(self.cache_dir / "alerts.json", "w") as f:
                    json.dump(self.alerts, f)
            except Exception:
                pass

            if self.alerts:
                logger.warning(f"ALERTS: {', '.join(a['event'] for a in self.alerts)}")
            else:
                logger.info("No active alerts")

        except Exception as e:
            self.fetch_errors += 1
            logger.error(f"NWS error ({self.fetch_errors}): {e}")
            if not self.alerts:
                try:
                    with open(self.cache_dir / "alerts.json", "r") as f:
                        self.alerts = json.load(f)
                    for a in self.alerts:
                        a["_tier"] = self._get_tier(a)
                        a["_weight"] = self._get_weight(a)
                    self._update_flags()
                except Exception:
                    pass

    def _update_flags(self):
        self.has_tier1 = any(a["_tier"] == 1 for a in self.alerts)
        self.has_tier2 = any(a["_tier"] == 2 for a in self.alerts)
        self.has_tier3 = any(a["_tier"] == 3 for a in self.alerts)
        self.alert_active = len(self.alerts) > 0

        # T1 always scrolls. T2 scrolls only during active cycle.
        self.enable_scrolling = self.has_tier1 or self._t2_cycle_active

    def _manage_priority_file(self):
        if self.has_tier1 or self._t2_cycle_active:
            tier = 1 if self.has_tier1 else 2
            try:
                with open(PRIORITY_FILE, "w") as f:
                    json.dump({"active": True, "tier": tier,
                               "events": [a["event"] for a in self.alerts
                                          if a["_tier"] <= 2]}, f)
                os.chmod(PRIORITY_FILE, 0o666)
            except Exception:
                pass
        else:
            try:
                os.remove(PRIORITY_FILE)
            except FileNotFoundError:
                pass

    # =========================================================================
    # T2 CYCLE MANAGEMENT
    # =========================================================================
    def _should_start_t2_cycle(self):
        """Check if it's time for a T2 ticker cycle."""
        if not self.has_tier2:
            return False
        if self.has_tier1:
            return False  # T1 takes priority
        if self._t2_cycle_active:
            return False  # Already running
        now = time.time()
        # First cycle starts immediately, subsequent ones after cooldown
        if self._t2_last_cycle_end == 0:
            return True
        return (now - self._t2_last_cycle_end) >= self._t2_cooldown

    def _start_t2_cycle(self):
        """Begin a T2 ticker cycle."""
        self._t2_cycle_active = True
        self._t2_cycle_start = time.time()
        self._scroll_start = time.time()
        self._cache_event = None  # Force ticker rebuild
        self.enable_scrolling = True
        logger.info("T2 ticker cycle STARTING")

    def _end_t2_cycle(self):
        """End a T2 ticker cycle, enter cooldown."""
        self._t2_cycle_active = False
        self._t2_last_cycle_end = time.time()
        self._t2_cycle_start = None
        self._scroll_start = None
        self._cache_event = None
        self.enable_scrolling = self.has_tier1  # Only keep scrolling for T1
        self._manage_priority_file()
        cooldown_min = self._t2_cooldown / 60
        logger.info(f"T2 ticker cycle ENDED - cooldown {cooldown_min:.0f}min")

    # =========================================================================
    # DRAWING PRIMITIVES
    # =========================================================================
    def _draw_border(self, draw, color, t=2):
        for i in range(t):
            draw.rectangle([i, i, self.W - 1 - i, self.H - 1 - i], outline=color)

    def _text(self, draw, x, y, text, color):
        draw.text((x, y), text, font=self.font, fill=color)

    def _text_c(self, draw, y, text, color):
        draw.text((self._cx(text), y), text, font=self.font, fill=color)

    def _text_r(self, draw, y, text, color):
        draw.text((self._rx(text), y), text, font=self.font, fill=color)

    # =========================================================================
    # CHEVRON STRIPES (animated diagonal stripes)
    # =========================================================================
    def _draw_chevron_stripes(self, draw, now, color):
        """Animated diagonal stripes on top+bottom bars.
        color = stripe color, alternates with black."""
        offset = int(now * 60) % 12
        for bar_y0, bar_y1 in [(0, 9), (23, 32)]:
            for x in range(-12, self.W + 12, 12):
                sx = x + offset
                pts1 = [(sx, bar_y0), (sx + 6, bar_y0),
                        (sx - 4, bar_y1), (sx - 10, bar_y1)]
                pts2 = [(sx + 6, bar_y0), (sx + 12, bar_y0),
                        (sx + 2, bar_y1), (sx - 4, bar_y1)]
                draw.polygon(pts1, fill=color)
                draw.polygon(pts2, fill=(0, 0, 0))

    # =========================================================================
    # TICKER TEXT BUILDER
    # =========================================================================
    def _build_ticker_text(self, alert):
        """Build the single-line ticker string."""
        ev = self._short(alert["event"])
        areas = alert.get("areas", "")
        rem = self._remaining(alert["expires"])
        desc = self._clean_nws_text(alert.get("description", ""))
        inst = self._clean_nws_text(alert.get("instruction", "")
                                     or "Monitor conditions. Follow NWS guidance.")
        sep = "  +++  "
        ticker = (f"*** {ev} ***{sep}"
                  f"Areas: {areas}{sep}"
                  f"Expires: {rem}{sep}"
                  f"{desc}{sep}"
                  f"ACTION: {inst}{sep}")
        return ticker

    # =========================================================================
    # TIER 2 VEGAS CARD (summary)
    # =========================================================================
    def _draw_watch_card(self, img, draw, alert):
        """T2 summary card for Vegas rotation - yellow left bar."""
        c = self._col(alert["severity"])
        draw.rectangle([0, 0, 3, self.H], fill=(255, 200, 0))
        self._draw_border(draw, (255, 200, 0), 1)
        ev = self._short(alert["event"])
        self._text(draw, 6, self.ROW1, ev, (255, 200, 0))
        areas = alert.get("areas", "")[:28]
        if areas:
            self._text(draw, 6, self.ROW2, areas, c["text"])
        rem = self._remaining(alert["expires"])
        self._text(draw, 6, self.ROW3, f"Until {rem}", (180, 180, 180))

    # =========================================================================
    # TIER 3 CARDS (Vegas rotation)
    # =========================================================================
    def _draw_info_card(self, img, draw, alert):
        c = self._col(alert["severity"])
        self._draw_border(draw, c["border"], 1)
        ev = self._short(alert["event"])
        self._text(draw, self.MARGIN, self.ROW1, ev, c["accent"])
        areas = alert.get("areas", "")[:28]
        if areas:
            self._text(draw, self.MARGIN, self.ROW2, areas[:self.CHARS_PER_LINE],
                      (200, 200, 200))
        rem = self._remaining(alert["expires"])
        self._text(draw, self.MARGIN, self.ROW3, f"Until {rem}", (120, 120, 120))

    # =========================================================================
    # NO ALERTS
    # =========================================================================
    def _draw_clear(self, img, draw):
        self._draw_border(draw, (0, 80, 0), 1)
        self._text(draw, self.MARGIN, self.ROW1, "NWS WEATHER ALERTS", (0, 150, 0))
        self._text(draw, self.MARGIN, self.ROW2, "No active alerts", (0, 100, 0))
        self._text(draw, self.MARGIN, self.ROW3, "Your Area", (80, 80, 80))

    # =========================================================================
    # VEGAS MODE
    # =========================================================================
    def get_vegas_views(self) -> List[str]:
        """T2 and T3 alerts produce Vegas cards. T1 uses permanent takeover."""
        if not self.alerts:
            return ["clear:0:0"] if self.config.get("show_when_clear", False) else []

        views = []
        for i, alert in enumerate(self.alerts):
            tier = alert.get("_tier", 3)
            if tier == 2:
                views.append(f"watch:{i}:0")
            elif tier == 3:
                views.append(f"info:{i}:0")
        return views

    def get_vegas_content(self) -> Optional[List[Image.Image]]:
        self.update()

        # Check if T2 cycle should start
        if self._should_start_t2_cycle():
            self._start_t2_cycle()

        # T1: flood Vegas with warning cards (animated chevron frames)
        if self.has_tier1:
            images = []
            t1_alerts = [a for a in self.alerts if a["_tier"] == 1]
            for alert in t1_alerts:
                weight = alert.get("_weight", 2)
                num_cards = max(6, weight * 4)  # 8-24 cards per alert
                for frame in range(num_cards):
                    img = Image.new("RGB", (self.W, self.H), (0, 0, 0))
                    draw = ImageDraw.Draw(img)
                    # Animate chevrons across frames
                    fake_time = time.time() + frame * 0.15
                    self._draw_chevron_stripes(draw, fake_time, self.CHEVRON_COLORS[1])
                    # Black center band with warning text
                    draw.rectangle([0, 10, self.W, 22], fill=(0, 0, 0))
                    ev = self._short(alert["event"])
                    rem = self._remaining(alert["expires"])
                    areas = alert.get("areas", "")[:24]
                    text = f"*** {ev} ***  {areas}  {rem}"
                    self._text(draw, self.MARGIN, 12, text[:self.CHARS_PER_LINE], (255, 255, 255))
                    self._stamp_test(draw)
                    images.append(img)
            logger.info(f"Vegas T1: {len(images)} warning cards for {len(t1_alerts)} alerts")
            return images if images else None

        # T2 active cycle - show watch cards in rotation
        if self._t2_cycle_active:
            pass  # Fall through to normal card generation

        if not self.alerts:
            if self.config.get("show_when_clear", False):
                img = Image.new("RGB", (self.W, self.H), (0, 0, 0))
                self._draw_clear(img, ImageDraw.Draw(img))
                return [img]
            return None

        images = []
        for view in self.get_vegas_views():
            img = Image.new("RGB", (self.W, self.H), (0, 0, 0))
            draw = ImageDraw.Draw(img)
            parts = view.split(":")
            ctype = parts[0]
            aidx = int(parts[1]) if len(parts) > 1 else 0
            if aidx >= len(self.alerts):
                aidx = 0
            alert = self.alerts[aidx]
            try:
                if ctype == "watch":
                    self._draw_watch_card(img, draw, alert)
                elif ctype == "info":
                    self._draw_info_card(img, draw, alert)
                elif ctype == "clear":
                    self._draw_clear(img, draw)
                else:
                    self._draw_info_card(img, draw, alert)
            except Exception as e:
                logger.error(f"Draw error {view}: {e}")
            self._stamp_test(draw)
            images.append(img)

        logger.info(f"Vegas: {len(images)} alert images")
        return images if images else None

    # =========================================================================
    # DISPLAY - STATELESS FRAME RENDERER (125 FPS for T1/T2 cycles)
    # =========================================================================
    def display(self, display_mode=None, force_clear=False):
        """Render ONE frame per call. No loops, no sleep."""
        # Throttle update() - don't read files 125x/sec
        now = time.time()
        if now - self._last_update_time >= self._update_throttle:
            self.update()
            self._last_update_time = now

            # Check if T2 cycle should start (only check on update, not every frame)
            if self._should_start_t2_cycle():
                self._start_t2_cycle()

        img = Image.new("RGB", (self.W, self.H), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        if self.alerts:
            a = self.alerts[0]
            t = a.get("_tier", 3)
            if t == 1:
                # T1: permanent red chevron ticker
                self._render_ticker_frame(img, draw, a, 1)
            elif t == 2 and self._t2_cycle_active:
                # T2: yellow chevron ticker (single cycle)
                self._render_t2_ticker_frame(img, draw, a)
            elif t == 2:
                # T2 in cooldown: show static watch card
                self._draw_watch_card(img, draw, a)
            else:
                self._draw_info_card(img, draw, a)
        elif self.config.get("show_when_clear", False):
            self._draw_clear(img, draw)
        else:
            return

        self._stamp_test(draw)
        self.display_manager.image = img
        self.display_manager.update_display()

    def _render_ticker_frame(self, img, draw, alert, tier):
        """Render ONE frame of LOOPING scrolling ticker (for T1).
        Called at 125 FPS. Ticker loops seamlessly forever."""
        now = time.time()

        # Build/cache ticker text
        event_key = alert.get("event", "") + alert.get("areas", "")
        if self._cache_event != event_key:
            self._ticker_text = self._build_ticker_text(alert)
            self._ticker_width = len(self._ticker_text) * self.CHAR_W
            self._loop_width = self._ticker_width + self._gap_px
            self._cache_event = event_key
            self._scroll_start = now

        # Init on first call
        if self._scroll_start is None:
            self._scroll_start = now

        elapsed = now - self._scroll_start

        # Get chevron color for this tier
        chevron_color = self.CHEVRON_COLORS.get(tier, (255, 0, 0))

        # Draw chevron stripes top + bottom
        self._draw_chevron_stripes(draw, now, chevron_color)

        # Black center band for ticker text
        draw.rectangle([0, 10, self.W, 22], fill=(0, 0, 0))

        # Scroll position: continuous loop using modulo
        scroll_x = -(int(elapsed * self._scroll_speed) % self._loop_width)

        # Draw primary ticker text
        draw.text((scroll_x, 12), self._ticker_text,
                 font=self.font, fill=(255, 255, 255))

        # Draw second copy trailing behind to fill any gap
        second_x = scroll_x + self._loop_width
        if second_x < self.W:
            draw.text((second_x, 12), self._ticker_text,
                     font=self.font, fill=(255, 255, 255))

        # Draw third copy if needed (for very short ticker text)
        third_x = second_x + self._loop_width
        if third_x < self.W:
            draw.text((third_x, 12), self._ticker_text,
                     font=self.font, fill=(255, 255, 255))

    def _render_t2_ticker_frame(self, img, draw, alert):
        """Render ONE frame of SINGLE-PASS ticker (for T2).
        Text enters from right, scrolls left, ends when fully off-screen left.
        Then cycle ends and display returns to Vegas rotation."""
        now = time.time()

        # Build/cache ticker text
        event_key = "t2_" + alert.get("event", "") + alert.get("areas", "")
        if self._cache_event != event_key:
            self._ticker_text = self._build_ticker_text(alert)
            self._ticker_width = len(self._ticker_text) * self.CHAR_W
            self._cache_event = event_key
            self._scroll_start = now

        if self._scroll_start is None:
            self._scroll_start = now

        elapsed = now - self._scroll_start

        # Text starts at right edge (x=W), scrolls left
        # One pass distance = W + ticker_width (enter from right, exit left)
        scroll_x = int(self.W - elapsed * self._scroll_speed)

        # Check if text has fully scrolled off screen left
        text_right_edge = scroll_x + self._ticker_width
        if text_right_edge < 0:
            # Cycle complete - release display
            self._end_t2_cycle()
            # Draw the static watch card for this frame
            self._draw_watch_card(img, draw, alert)
            return

        # Draw yellow chevron stripes top + bottom
        self._draw_chevron_stripes(draw, now, self.CHEVRON_COLORS[2])

        # Black center band for ticker text
        draw.rectangle([0, 10, self.W, 22], fill=(0, 0, 0))

        # Draw ticker text
        draw.text((scroll_x, 12), self._ticker_text,
                 font=self.font, fill=(255, 255, 255))

    # =========================================================================
    # LIFECYCLE + LIVE PRIORITY
    # =========================================================================
    def get_display_duration(self):
        return self.config.get("alert_card_duration", 4) if self.enable_scrolling else \
               self.config.get("display_duration", 10)

    def cleanup(self):
        self.alerts = []
        self.alert_active = self.has_tier1 = self.has_tier2 = self.has_tier3 = False
        self.enable_scrolling = False
        self._ticker_text = ""
        self._cache_event = None
        self._scroll_start = None
        self._t2_cycle_active = False
        self._t2_last_cycle_end = 0
        self._t2_cycle_start = None
        try:
            os.remove(PRIORITY_FILE)
        except FileNotFoundError:
            pass

    def has_live_priority(self) -> bool:
        """T1 and active T2 take over the display."""
        return self.has_live_content()

    def has_live_content(self) -> bool:
        """T1 always takes over. T2 takes over only during active cycle."""
        if getattr(self, 'has_tier1', False):
            return True
        if getattr(self, '_t2_cycle_active', False):
            return True
        # Check if T2 cycle should start
        if self._should_start_t2_cycle():
            self._start_t2_cycle()
            return True
        return False

    def get_live_modes(self) -> list:
        return ["weather-alerts"]

"""
Wavelog Recent QSOs Plugin for LEDMatrix
Displays your last logged QSOs from Wavelog, only if they're recent (< 1 hour old).
Supports both API and direct MySQL methods.

v2.1.0: Smooth scrolling ticker at 125 FPS with pre-rendered color-coded QSO data.
        Stateless one-frame-per-call display(). Throttled updates.
"""

import logging
import requests
import time
import json
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

from src.plugin_system.base_plugin import BasePlugin
from ux_constants import UX, load_fonts, get_band_color, get_mode_color, draw_title_row, text_right_x

logger = logging.getLogger(__name__)
__version__ = "2.1.0"


class WavelogQSOsPlugin(BasePlugin):
    """
    Plugin to display recent QSOs from Wavelog on the LED matrix.
    Only shows QSOs that are less than a configurable age (default: 1 hour).
    If no recent QSOs exist, the plugin shows nothing / skips display.

    v2.1.0: Smooth scrolling ticker with pre-rendered color-coded images.
    """

    PREFIX_TO_ISO = {
        "W": "US", "K": "US", "N": "US", "AA": "US", "AB": "US", "AC": "US", "AD": "US", "AE": "US", "AF": "US", "AG": "US", "AH": "US", "AI": "US", "AJ": "US", "AK": "US", "AL": "US",
        "KA": "US", "KB": "US", "KC": "US", "KD": "US", "KE": "US", "KF": "US", "KG": "US", "KH": "US", "KI": "US", "KJ": "US", "KK": "US", "KL": "US", "KM": "US", "KN": "US", "KO": "US", "KP": "US", "KQ": "US", "KR": "US", "KS": "US", "KT": "US", "KU": "US", "KV": "US", "KW": "US", "KX": "US", "KY": "US", "KZ": "US",
        "NA": "US", "NB": "US", "NC": "US", "ND": "US", "NE": "US", "NF": "US", "NG": "US", "NH": "US", "NI": "US", "NJ": "US", "NK": "US", "NL": "US", "NM": "US", "NN": "US", "NO": "US", "NP": "US", "NQ": "US", "NR": "US", "NS": "US", "NT": "US", "NU": "US", "NV": "US", "NW": "US", "NX": "US", "NY": "US", "NZ": "US",
        "WA": "US", "WB": "US", "WC": "US", "WD": "US", "WE": "US", "WF": "US", "WG": "US", "WH": "US", "WI": "US", "WJ": "US", "WK": "US", "WL": "US", "WM": "US", "WN": "US", "WO": "US", "WP": "US", "WQ": "US", "WR": "US", "WS": "US", "WT": "US", "WU": "US", "WV": "US", "WW": "US", "WX": "US", "WY": "US", "WZ": "US",
        "JA": "JP", "JH": "JP", "JR": "JP", "JE": "JP", "JF": "JP", "JG": "JP", "7J": "JP", "7K": "JP",
        "DL": "DE", "DA": "DE", "DB": "DE", "DC": "DE", "DD": "DE", "DF": "DE", "DG": "DE", "DH": "DE", "DJ": "DE", "DK": "DE",
        "G": "GB", "M": "GB", "2E": "GB", "GW": "GB", "GM": "GB",
        "F": "FR", "TM": "FR", "I": "IT", "IK": "IT", "IZ": "IT",
        "EA": "ES", "EB": "ES", "EC": "ES",
        "VE": "CA", "VA": "CA", "VY": "CA", "VK": "AU", "ZL": "NZ",
        "PY": "BR", "PP": "BR", "PT": "BR", "PU": "BR", "ZV": "BR", "ZW": "BR",
        "LU": "AR", "UA": "RU", "RA": "RU", "BY": "CN", "BA": "CN",
        "HL": "KR", "DS": "KR", "VU": "IN", "XE": "MX", "ZS": "ZA",
        "PA": "NL", "SP": "PL", "SM": "SE", "LA": "NO", "OH": "FI", "OZ": "DK",
        "OE": "AT", "HB": "CH", "ON": "BE", "CT": "PT", "SV": "GR", "OK": "CZ",
        "UR": "UA", "HA": "HU", "YO": "RO", "LZ": "BG", "9A": "HR", "S5": "SI",
        "EI": "IE", "CE": "CL", "OA": "PE", "HK": "CO", "YV": "VE",
        "YB": "ID", "HS": "TH", "9M": "MY", "9V": "SG", "DU": "PH", "BV": "TW",
        "4X": "IL", "TA": "TR", "SU": "EG", "5Z": "KE", "5N": "NG", "CO": "CU",
    }
    FLAG_WIDTH = 10
    FLAG_HEIGHT = 7

    def __init__(self, plugin_id, config, display_manager, cache_manager, plugin_manager):
        super().__init__(plugin_id, config, display_manager, cache_manager, plugin_manager)

        # Config
        self.wavelog_url = self.config.get("wavelog_url", "http://localhost/wavelog").rstrip("/")
        if self.wavelog_url.endswith("/index.php"):
            self._api_base = self.wavelog_url
        elif self.wavelog_url.endswith("index.php"):
            self._api_base = self.wavelog_url
        else:
            self._api_base = f"{self.wavelog_url}/index.php"
        self.api_key = self.config.get("api_key", "")
        self.max_qsos = self.config.get("max_qsos", 10)
        self.max_age_minutes = self.config.get("max_age_minutes", 60)
        self.fetch_method = self.config.get("fetch_method", "api")
        self.station_id = self.config.get("station_id", 1)

        # MySQL config (optional fallback)
        self.db_host = self.config.get("db_host", "localhost")
        self.db_name = self.config.get("db_name", "wavelog")
        self.db_user = self.config.get("db_user", "wavelog")
        self.db_pass = self.config.get("db_pass", "")

        # Display
        self.display_mode = self.config.get("display_mode", "ticker")
        self.qsos = []
        self.has_recent_qsos = False
        self.last_fetch = 0
        self.fetch_interval = self.config.get("fetch_interval", 120)

        # Vegas mode cards
        self.vegas_views = ["recent_qsos"]
        self.vegas_view_index = 0

        # API state for incremental fetching
        self._cached_qsos = []
        self._cache_file = Path("/var/cache/ledmatrix/wavelog_last_id.json")
        self._last_fetched_id = self._load_cached_id()

        # Colors (from shared UX constants)
        self.title_color = UX.TITLE_COLOR
        self.call_color = UX.CALL_COLOR
        self.freq_color = UX.FREQ_COLOR
        self.mode_color = UX.MODE_COLORS.get("SSB", (100, 255, 100))
        self.time_color = UX.TIME_COLOR
        self.text_color = UX.TEXT_SECONDARY

        # Layout constants (from shared UX constants)
        self.TITLE_Y = UX.TITLE_Y
        self.ROW1_Y = UX.ROW1_Y
        self.ROW2_Y = UX.ROW2_Y
        self.DISPLAY_WIDTH = UX.WIDTH
        self.CHAR_WIDTH = UX.CHAR_WIDTH
        self.SPACING = UX.SPACING

        # Fonts (shared loader)
        self.font, self.font_large = load_fonts(__file__)

        # Flags (reuse from hamradio-spots)
        self.flags = {}
        self._load_flags()

        # =====================================================================
        # SMOOTH SCROLLING STATE (v2.1.0)
        # =====================================================================
        # Controller checks this for 125 FPS
        self.enable_scrolling = False

        # Pre-rendered ticker image
        self._ticker_img = None          # Wide PIL image with all QSO data
        self._ticker_width = 0           # Width of ticker image
        self._ticker_gap = 80            # Gap between looping copies (px)
        self._ticker_loop_width = 0      # ticker_width + gap
        self._ticker_qso_hash = None     # Hash to detect QSO changes

        # Scroll state
        self._scroll_speed = self.config.get("scroll_speed", 50)  # pixels per second
        self._scroll_start = None        # time.time() when scroll phase started

        # Throttle update() during 125 FPS
        self._last_update_time = 0
        self._update_throttle = 2.0      # Only run update() every 2s

        self.logger.info(f"Wavelog QSOs v{__version__} init - API base: {self._api_base}, "
                        f"method: {self.fetch_method}, max_age: {self.max_age_minutes}min, "
                        f"scroll_speed: {self._scroll_speed}px/s")

    # =========================================================================
    # SMOOTH SCROLLING - TICKER IMAGE BUILDER
    # =========================================================================

    def _qso_hash(self) -> str:
        """Hash of current QSOs to detect data changes."""
        if not self.qsos:
            return ""
        parts = []
        for q in self.qsos:
            parts.append(f"{q['callsign']}_{q['band']}_{q['mode']}")
        return "|".join(parts)

    def _build_ticker_image(self) -> None:
        """Pre-render a wide image with all QSO data, color-coded.
        Called when QSOs change. Result cached in self._ticker_img."""
        if not self.qsos:
            self._ticker_img = None
            self._ticker_width = 0
            self._ticker_loop_width = 0
            return

        CW = self.CHAR_WIDTH
        SP = self.SPACING
        SEP = "  \u2022  "  # bullet separator between QSOs
        SEP_WIDTH = len(SEP) * CW

        # Calculate total width needed
        # Each QSO: [flag 10+3px] CALL SP BAND SP MODE SP AGE [separator]
        segments = []  # list of (text, color, has_flag, callsign)
        total_w = 0

        for i, qso in enumerate(self.qsos):
            call = qso["callsign"]
            band = qso["band"]
            mode = qso["mode"]
            age = self._format_age(qso.get("_datetime_utc"))
            country = qso.get("country", "")

            # Flag space
            flag = self._get_flag(call)
            flag_w = (self.FLAG_WIDTH + 3) if flag else 0

            # Field widths
            call_w = len(call) * CW
            band_w = len(band) * CW
            mode_w = len(mode) * CW
            age_w = len(age) * CW
            country_short = country[:10] if country else ""
            country_w = len(country_short) * CW if country_short else 0

            qso_w = flag_w + call_w + SP + band_w + SP + mode_w + SP + age_w
            if country_short:
                qso_w += SP + country_w

            segments.append({
                "callsign": call,
                "band": band,
                "mode": mode,
                "age": age,
                "country": country_short,
                "flag": flag,
                "flag_w": flag_w,
                "width": qso_w,
            })
            total_w += qso_w
            if i < len(self.qsos) - 1:
                total_w += SEP_WIDTH

        if total_w == 0:
            self._ticker_img = None
            return

        # Render into a wide image (use rows 1-2 height = 21px)
        ticker_h = 21  # from ROW1_Y to bottom
        self._ticker_img = Image.new('RGB', (total_w, ticker_h), (0, 0, 0))
        draw = ImageDraw.Draw(self._ticker_img)

        x = 0
        text_y = 0  # Vertically centered in the 21px strip

        for i, seg in enumerate(segments):
            # Flag
            if seg["flag"]:
                try:
                    self._ticker_img.paste(seg["flag"], (x, text_y + 1))
                except Exception:
                    pass
                x += seg["flag_w"]

            # Callsign (yellow)
            draw.text((x, text_y), seg["callsign"], font=self.font, fill=self.call_color)
            x += len(seg["callsign"]) * CW + SP

            # Band (band color)
            draw.text((x, text_y), seg["band"], font=self.font, fill=self._get_band_color(seg["band"]))
            x += len(seg["band"]) * CW + SP

            # Mode (mode color)
            draw.text((x, text_y), seg["mode"], font=self.font, fill=self._get_mode_color(seg["mode"]))
            x += len(seg["mode"]) * CW + SP

            # Age (gray)
            draw.text((x, text_y), seg["age"], font=self.font, fill=self.time_color)
            x += len(seg["age"]) * CW

            # Country (dim)
            if seg["country"]:
                x += SP
                draw.text((x, text_y), seg["country"], font=self.font, fill=UX.TEXT_DIM)
                x += len(seg["country"]) * CW

            # Separator between QSOs
            if i < len(segments) - 1:
                draw.text((x, text_y), SEP, font=self.font, fill=UX.TEXT_DIM)
                x += SEP_WIDTH

        self._ticker_width = total_w
        self._ticker_loop_width = total_w + self._ticker_gap
        self._ticker_qso_hash = self._qso_hash()
        self._scroll_start = time.time()

        self.logger.info(f"Built ticker image: {total_w}px wide, {len(self.qsos)} QSOs, "
                        f"loop_width={self._ticker_loop_width}px")

    # =========================================================================
    # DISPLAY - STATELESS FRAME RENDERER (125 FPS)
    # =========================================================================

    def display(self, display_mode: str = None, force_clear: bool = False) -> None:
        """Render ONE frame per call. No loops, no sleep.
        Called at 125 FPS when enable_scrolling=True."""
        now = time.time()

        # Throttle update() - don't fetch data 125x/sec
        if now - self._last_update_time >= self._update_throttle:
            self.update()
            self._last_update_time = now

        W = self.DISPLAY_WIDTH
        H = UX.HEIGHT
        img = Image.new('RGB', (W, H), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        if not self.has_recent_qsos:
            self.enable_scrolling = False
            draw.text((2, self.TITLE_Y), "WAVELOG", font=self.font, fill=UX.TEXT_MUTED)
            draw.text((2, self.ROW1_Y), "No recent QSOs", font=self.font, fill=UX.TEXT_DIM)
            self.display_manager.image = img
            self.display_manager.update_display()
            return True

        # Enable smooth scrolling when we have QSOs
        self.enable_scrolling = True

        # Rebuild ticker if QSOs changed
        current_hash = self._qso_hash()
        if current_hash != self._ticker_qso_hash or self._ticker_img is None:
            self._build_ticker_image()

        if self._ticker_img is None:
            self.enable_scrolling = False
            return True

        # Static title row
        draw.text((2, self.TITLE_Y), "WAVELOG", font=self.font, fill=self.title_color)
        count_text = f"{len(self.qsos)} QSO{'s' if len(self.qsos) != 1 else ''}"
        draw.text((text_right_x(count_text), self.TITLE_Y), count_text,
                  font=self.font, fill=self.text_color)

        # Scrolling ticker area (below title)
        if self._scroll_start is None:
            self._scroll_start = now

        elapsed = now - self._scroll_start
        raw_x = elapsed * self._scroll_speed

        # Instant cut: when primary copy's right edge exits screen, reset
        right_edge = int(self._ticker_width - raw_x)
        if right_edge < 0:
            # Reset scroll
            self._scroll_start = now
            raw_x = 0

        scroll_x = int(-raw_x)
        ticker_y = self.ROW1_Y

        # Paste primary ticker (crop to visible portion)
        self._paste_ticker(img, scroll_x, ticker_y)

        # Paste trailing copy for seamless loop
        second_x = scroll_x + self._ticker_loop_width
        if second_x < W:
            self._paste_ticker(img, second_x, ticker_y)

        self.display_manager.image = img
        self.display_manager.update_display()
        return True

    def _paste_ticker(self, target: Image.Image, x_offset: int, y_offset: int) -> None:
        """Paste the pre-rendered ticker image at the given offset, clipping to display bounds."""
        W = self.DISPLAY_WIDTH
        if self._ticker_img is None:
            return

        # Calculate visible region of ticker
        src_left = max(0, -x_offset)
        src_right = min(self._ticker_width, W - x_offset)
        if src_left >= src_right:
            return

        dst_x = max(0, x_offset)
        # Crop visible portion and paste
        cropped = self._ticker_img.crop((src_left, 0, src_right, self._ticker_img.height))
        target.paste(cropped, (dst_x, y_offset))

    # =========================================================================
    # DATA FETCHING (unchanged from v2.0)
    # =========================================================================

    def update(self):
        """Fetch recent QSOs from Wavelog."""
        now = time.time()
        if now - self.last_fetch < self.fetch_interval:
            return

        self.last_fetch = now

        try:
            if self.fetch_method == "mysql":
                raw_qsos = self._fetch_mysql()
            else:
                raw_qsos = self._fetch_api()

            # Filter to only QSOs within max_age_minutes
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=self.max_age_minutes)
            recent = []
            for qso in raw_qsos:
                qso_time = qso.get("_datetime_utc")
                if qso_time and qso_time >= cutoff:
                    recent.append(qso)

            self.qsos = recent[:self.max_qsos]
            self.has_recent_qsos = len(self.qsos) > 0

            if self.has_recent_qsos:
                self.logger.info(f"Wavelog: {len(self.qsos)} QSOs within last {self.max_age_minutes} min")
            else:
                self.logger.debug(f"Wavelog: No QSOs within last {self.max_age_minutes} min")

        except Exception as e:
            self.logger.error(f"Wavelog fetch error: {e}")

    def _load_cached_id(self) -> int:
        """Load last fetched ID and cached QSOs from cache file."""
        try:
            if self._cache_file.exists():
                data = json.loads(self._cache_file.read_text())
                cached_id = int(data.get("last_fetched_id", 0))
                cached_qsos = data.get("cached_qsos", [])
                if cached_qsos:
                    for q in cached_qsos:
                        if q.get("_datetime_utc_str"):
                            try:
                                q["_datetime_utc"] = datetime.fromisoformat(q["_datetime_utc_str"])
                            except:
                                pass
                    self._cached_qsos = cached_qsos
                    self.logger.info(f"Restored {len(cached_qsos)} cached QSOs")
                if cached_id > 0:
                    self.logger.info(f"Restored last_fetched_id={cached_id} from cache")
                return cached_id
        except Exception as e:
            self.logger.warning(f"Could not load cached ID: {e}")
        return 0

    def _save_cached_id(self) -> None:
        """Persist last fetched ID and QSOs to cache file."""
        try:
            self._cache_file.parent.mkdir(parents=True, exist_ok=True)
            saveable_qsos = []
            for q in self._cached_qsos[:self.max_qsos * 2]:
                sq = dict(q)
                dt = sq.get("_datetime_utc")
                if dt:
                    sq["_datetime_utc_str"] = dt.isoformat()
                    del sq["_datetime_utc"]
                saveable_qsos.append(sq)
            self._cache_file.write_text(json.dumps({
                "last_fetched_id": self._last_fetched_id,
                "cached_qsos": saveable_qsos,
                "updated": datetime.now(timezone.utc).isoformat()
            }))
        except Exception as e:
            self.logger.warning(f"Could not save cached ID: {e}")

    def _probe_latest_id(self) -> int:
        """On first startup, probe the API to get current lastfetchedid."""
        url = f"{self._api_base}/api/get_contacts_adif"
        payload = {
            "key": self.api_key,
            "station_id": str(self.station_id),
            "fetchfromid": 999999999
        }
        try:
            resp = requests.post(url, json=payload,
                                 headers={"Content-Type": "application/json"},
                                 timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                latest_id = int(data.get("lastfetchedid", 0))
                self.logger.info(f"Probed latest ID: {latest_id}")
                return latest_id
        except Exception as e:
            self.logger.warning(f"Probe failed: {e}")
        return 0

    def _fetch_api(self) -> List[Dict]:
        """Fetch QSOs via Wavelog REST API using api/get_contacts_adif endpoint."""
        qsos = []

        if not self.api_key:
            self.logger.error("No API key configured for Wavelog API method")
            return qsos

        is_initial = (self._last_fetched_id == 0)
        timeout = 60 if is_initial else 15
        if is_initial:
            self.logger.info("First fetch - downloading full log (this may take a moment)...")

        url = f"{self._api_base}/api/get_contacts_adif"
        payload = {
            "key": self.api_key,
            "station_id": str(self.station_id),
            "fetchfromid": self._last_fetched_id
        }

        try:
            resp = requests.post(
                url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                timeout=timeout
            )

            if resp.status_code == 200:
                data = resp.json()
                exported = data.get("exported_qsos", 0)
                new_last_id = data.get("lastfetchedid", self._last_fetched_id)
                adif_string = data.get("adif", "")
                message = data.get("message", "")

                self.logger.debug(f"API response: {exported} QSOs exported, "
                                 f"lastfetchedid={new_last_id}, msg={message}")

                if adif_string:
                    parsed = self._parse_adif(adif_string)
                    if parsed:
                        if self._last_fetched_id > 0 and self._cached_qsos:
                            self._cached_qsos.extend(parsed)
                        else:
                            self._cached_qsos = parsed

                        self._cached_qsos.sort(
                            key=lambda q: q.get("_datetime_utc") or datetime.min.replace(tzinfo=timezone.utc),
                            reverse=True
                        )
                        self._cached_qsos = self._cached_qsos[:self.max_qsos * 2]

                    if new_last_id:
                        self._last_fetched_id = int(new_last_id)
                        self._save_cached_id()

                qsos = list(self._cached_qsos) if self._cached_qsos else []
            else:
                self.logger.error(f"Wavelog API returned status {resp.status_code}: {resp.text[:200]}")

        except requests.exceptions.ConnectionError:
            self.logger.error(f"Cannot connect to Wavelog at {self.wavelog_url}")
        except requests.exceptions.Timeout:
            self.logger.error("Wavelog API request timed out")
        except Exception as e:
            self.logger.error(f"Wavelog API error: {e}")

        if not qsos and self._cached_qsos:
            qsos = list(self._cached_qsos)

        return qsos

    def _parse_adif(self, adif_string: str) -> List[Dict]:
        """Parse an ADIF string into a list of QSO dictionaries."""
        import re
        qsos = []

        records = re.split(r'<eor>', adif_string, flags=re.IGNORECASE)

        for record in records:
            record = record.strip()
            if not record:
                continue

            if '<eoh>' in record.lower():
                _, _, record = record.lower().partition('<eoh>')
                record = adif_string[adif_string.lower().index('<eoh>') + 5:]
                sub_records = re.split(r'<eor>', record, flags=re.IGNORECASE)
                if sub_records:
                    record = sub_records[0].strip()

            fields = {}
            for match in re.finditer(r'<(\w+):(\d+)(?::\w+)?>([\s\S]*?)(?=<\w+:|\Z)', record):
                field_name = match.group(1).upper()
                field_len = int(match.group(2))
                field_value = match.group(3)[:field_len].strip()
                fields[field_name] = field_value

            if not fields:
                continue

            callsign = fields.get("CALL", "???")
            if callsign == "???":
                continue

            band = fields.get("BAND", "?")
            mode = fields.get("MODE", "?")
            submode = fields.get("SUBMODE", "")
            freq = fields.get("FREQ", "")
            name = fields.get("NAME", "")
            rst_sent = fields.get("RST_SENT", "")
            rst_rcvd = fields.get("RST_RCVD", "")
            country = fields.get("COUNTRY", "")
            grid = fields.get("GRIDSQUARE", "")
            qso_date = fields.get("QSO_DATE", "")
            time_on = fields.get("TIME_ON", "")

            display_mode = submode if submode else mode

            dt_utc = None
            if qso_date:
                try:
                    if time_on:
                        t = time_on.ljust(4, '0')
                        if len(t) >= 6:
                            dt_utc = datetime.strptime(f"{qso_date}{t[:6]}", "%Y%m%d%H%M%S")
                        else:
                            dt_utc = datetime.strptime(f"{qso_date}{t[:4]}", "%Y%m%d%H%M")
                    else:
                        dt_utc = datetime.strptime(qso_date, "%Y%m%d")
                    dt_utc = dt_utc.replace(tzinfo=timezone.utc)
                except (ValueError, TypeError) as e:
                    self.logger.debug(f"Date parse error for {callsign}: {e}")

            qsos.append({
                "callsign": callsign.upper().strip(),
                "band": band.upper().strip(),
                "mode": display_mode.upper().strip(),
                "freq": freq.strip(),
                "name": name.strip(),
                "rst_sent": rst_sent.strip(),
                "rst_rcvd": rst_rcvd.strip(),
                "country": country.strip(),
                "grid": grid.upper().strip(),
                "_datetime_utc": dt_utc,
            })

        self.logger.debug(f"Parsed {len(qsos)} QSOs from ADIF string")
        return qsos

    def _fetch_statistics(self) -> Optional[Dict]:
        """Fetch station statistics via api/statistics endpoint."""
        if not self.api_key:
            return None
        try:
            url = f"{self._api_base}/api/statistics/{self.api_key}"
            resp = requests.get(url, timeout=10, headers={"Accept": "application/json"})
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            self.logger.debug(f"Statistics endpoint error: {e}")
        return None

    def _fetch_mysql(self) -> List[Dict]:
        """Fetch QSOs directly from the Wavelog MySQL database."""
        qsos = []
        try:
            import mysql.connector
        except ImportError:
            self.logger.error("mysql-connector-python not installed. "
                            "Run: pip install mysql-connector-python --break-system-packages")
            return qsos

        try:
            conn = mysql.connector.connect(
                host=self.db_host,
                database=self.db_name,
                user=self.db_user,
                password=self.db_pass,
                connect_timeout=5
            )
            cursor = conn.cursor(dictionary=True)

            query = """
                SELECT
                    COL_CALL,
                    COL_BAND,
                    COL_MODE,
                    COL_SUBMODE,
                    COL_FREQ,
                    COL_TIME_ON,
                    COL_TIME_OFF,
                    COL_RST_SENT,
                    COL_RST_RCVD,
                    COL_NAME,
                    COL_COUNTRY,
                    COL_GRIDSQUARE
                FROM TABLE_HRD_CONTACTS_V01
                WHERE station_id = %s
                ORDER BY COL_TIME_ON DESC
                LIMIT %s
            """
            cursor.execute(query, (self.station_id, self.max_qsos))
            rows = cursor.fetchall()

            for row in rows:
                dt_utc = None
                time_on = row.get("COL_TIME_ON")
                if time_on:
                    if isinstance(time_on, datetime):
                        dt_utc = time_on.replace(tzinfo=timezone.utc) if time_on.tzinfo is None else time_on
                    else:
                        try:
                            dt_utc = datetime.fromisoformat(str(time_on)).replace(tzinfo=timezone.utc)
                        except (ValueError, TypeError):
                            pass

                mode = row.get("COL_MODE", "")
                submode = row.get("COL_SUBMODE", "")
                display_mode = submode if submode else mode

                qsos.append({
                    "callsign": str(row.get("COL_CALL", "???")).upper().strip(),
                    "band": str(row.get("COL_BAND", "?")).upper().strip(),
                    "mode": str(display_mode).upper().strip(),
                    "freq": str(row.get("COL_FREQ", "")).strip(),
                    "name": str(row.get("COL_NAME", "") or "").strip(),
                    "rst_sent": str(row.get("COL_RST_SENT", "") or "").strip(),
                    "rst_rcvd": str(row.get("COL_RST_RCVD", "") or "").strip(),
                    "country": str(row.get("COL_COUNTRY", "") or "").strip(),
                    "grid": str(row.get("COL_GRIDSQUARE", "") or "").upper().strip(),
                    "_datetime_utc": dt_utc,
                })

            cursor.close()
            conn.close()
            self.logger.debug(f"MySQL: Got {len(qsos)} QSOs")

        except Exception as e:
            self.logger.error(f"MySQL fetch error: {e}")

        return qsos

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _get_mode_color(self, mode: str) -> tuple:
        return get_mode_color(mode)

    def _get_band_color(self, band: str) -> tuple:
        return get_band_color(band)

    def _load_flags(self):
        flags_dir = Path(__file__).parent.parent / "hamradio-spots" / "flags"
        if not flags_dir.exists():
            self.logger.debug(f"No flags directory at {flags_dir}")
            return
        for flag_file in flags_dir.glob("*.png"):
            code = flag_file.stem.upper()
            try:
                img = Image.open(flag_file).convert("RGB").resize(
                    (self.FLAG_WIDTH, self.FLAG_HEIGHT), Image.LANCZOS)
                self.flags[code] = img
            except:
                pass
        self.logger.info(f"Loaded {len(self.flags)} country flags")

    def _get_flag(self, callsign: str) -> Optional[Image.Image]:
        if not callsign:
            return None
        callsign = callsign.upper()
        for length in range(min(3, len(callsign)), 0, -1):
            prefix = callsign[:length]
            if prefix in self.PREFIX_TO_ISO:
                return self.flags.get(self.PREFIX_TO_ISO[prefix])
        return None

    def _format_age(self, dt_utc: datetime) -> str:
        if not dt_utc:
            return "?"
        delta = datetime.now(timezone.utc) - dt_utc
        minutes = int(delta.total_seconds() / 60)
        if minutes < 1:
            return "now"
        elif minutes < 60:
            return f"{minutes}m"
        else:
            return f"{minutes // 60}h{minutes % 60}m"

    # =========================================================================
    # VEGAS MODE (static images - unchanged)
    # =========================================================================

    def _draw_qso_row(self, draw: ImageDraw, qso: Dict, x: int, y: int, width: int) -> None:
        """Draw a single QSO row for Vegas static cards."""
        CW = self.CHAR_WIDTH
        SP = self.SPACING

        callsign = qso["callsign"]
        band = qso["band"]
        mode = qso["mode"]
        age = self._format_age(qso.get("_datetime_utc"))
        country = qso.get("country", "")

        draw.text((x, y), age, font=self.font, fill=self.time_color)
        x += len(age) * CW + SP
        draw.text((x, y), callsign, font=self.font, fill=self.call_color)
        x += len(callsign) * CW + SP
        draw.text((x, y), band, font=self.font, fill=self._get_band_color(band))
        x += len(band) * CW + SP
        draw.text((x, y), mode, font=self.font, fill=self._get_mode_color(mode))
        x += len(mode) * CW + SP
        if country:
            avail = width - x - 2
            max_chars = avail // CW
            c = country[:max_chars] if len(country) <= max_chars else country[:max(max_chars-1, 1)] + "."
            draw.text((x, y), c, font=self.font, fill=UX.TEXT_DIM)

    def get_vegas_content(self) -> Optional[List[Image.Image]]:
        """Return static images for Vegas mode rotation."""
        self.update()
        if not self.has_recent_qsos:
            return None

        images = []
        W = self.DISPLAY_WIDTH
        H = UX.HEIGHT

        # Generate cards showing 2 QSOs each
        for start in range(0, len(self.qsos), 2):
            img = Image.new('RGB', (W, H), (0, 0, 0))
            draw = ImageDraw.Draw(img)

            # Title
            draw.text((2, self.TITLE_Y), "WAVELOG", font=self.font, fill=self.title_color)
            count_text = f"{len(self.qsos)} QSO{'s' if len(self.qsos) != 1 else ''}"
            draw.text((text_right_x(count_text), self.TITLE_Y), count_text,
                      font=self.font, fill=self.text_color)

            # QSO rows
            if start < len(self.qsos):
                self._draw_qso_row(draw, self.qsos[start], 2, self.ROW1_Y, W)
            if start + 1 < len(self.qsos):
                self._draw_qso_row(draw, self.qsos[start + 1], 2, self.ROW2_Y, W)

            images.append(img)

        return images if images else None

    def get_vegas_content_type(self) -> str:
        return 'static'

    def get_display_duration(self) -> int:
        if not self.has_recent_qsos:
            return 5
        return self.config.get("display_duration", 20)

    def get_vegas_views(self) -> List[str]:
        if not self.has_recent_qsos:
            return []
        return self.vegas_views

    def cleanup(self) -> None:
        self.qsos = []
        self.has_recent_qsos = False
        self.enable_scrolling = False
        self._ticker_img = None
        self._ticker_qso_hash = None
        self._scroll_start = None
        self.logger.info("Wavelog QSOs plugin cleaned up")


# For direct testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    test_config = {
        "enabled": True,
        "wavelog_url": "http://localhost/wavelog",
        "api_key": "",
        "public_slug": "",
        "fetch_method": "mysql",
        "db_host": "localhost",
        "db_name": "wavelog",
        "db_user": "wavelog",
        "db_pass": "",
        "station_id": 1,
        "max_qsos": 10,
        "max_age_minutes": 60,
    }

    plugin = WavelogQSOsPlugin("wavelog-qsos", test_config, None, None, None)
    print("Testing Wavelog fetch (will fail without DB/API)...")
    try:
        if test_config["fetch_method"] == "mysql":
            qsos = plugin._fetch_mysql()
        else:
            qsos = plugin._fetch_api()
        print(f"Fetched {len(qsos)} QSOs")
        for q in qsos[:5]:
            print(f"  {q['callsign']} {q['band']} {q['mode']} {q.get('_datetime_utc', '?')}")
    except Exception as e:
        print(f"Error: {e}")

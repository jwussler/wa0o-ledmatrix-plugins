"""
Ham Radio DX Spots Plugin for LEDMatrix
Version: 3.4.0 - Clean tiered alerts with workability scoring
"""
import logging
import requests
import time
import math
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import os
from src.plugin_system.base_plugin import BasePlugin
from ux_constants import UX, load_fonts

logger = logging.getLogger(__name__)
__version__ = "3.4.0"


class HamRadioSpotsPlugin(BasePlugin):
    """Ham Radio DX Spots with priority alerts for top 50 most wanted"""
    
    # =========================================================================
    # LAYOUT CONSTANTS (from shared UX module)
    # =========================================================================
    DISPLAY_WIDTH = UX.WIDTH
    DISPLAY_HEIGHT = UX.HEIGHT
    TITLE_Y = UX.TITLE_Y
    ROW1_Y = UX.ROW1_Y
    ROW2_Y = UX.ROW2_Y
    
    HOTSPOT_START_Y = 9
    HOTSPOT_ROW_HEIGHT = 7
    HOTSPOT_BAR_X = 22
    HOTSPOT_BAR_MAX_WIDTH = 45
    HOTSPOT_COUNT_X = 70
    
    SPOT_FLAG_WIDTH = 11
    SPOT_CHAR_WIDTH = UX.CHAR_WIDTH
    SPOT_SPACING = UX.SPACING
    
    # =========================================================================
    # COLOR DEFINITIONS
    # =========================================================================
    BAND_COLORS = {
        "160m": (128, 0, 128), "80m": (0, 0, 255), "60m": (0, 128, 128),
        "40m": (0, 255, 0), "30m": (128, 255, 0), "20m": (255, 255, 0),
        "17m": (255, 165, 0), "15m": (255, 100, 0), "12m": (255, 50, 0),
        "10m": (255, 0, 0), "6m": (255, 0, 128), "2m": (200, 200, 200),
    }
    
    MODE_COLORS = {
        "SSB": (100, 255, 100), "USB": (100, 255, 100), "LSB": (100, 255, 100),
        "CW": (255, 100, 100), "FT8": (0, 255, 255), "FT4": (0, 200, 200),
        "RTTY": (255, 150, 0), "PSK": (200, 100, 255), "DIGI": (0, 180, 180),
    }
    
    BAND_ORDER = ["10m", "12m", "15m", "17m", "20m", "30m", "40m", "60m", "80m", "160m"]
    
    VOICE_SEGMENTS = {
        "160m": [(1900, 2000)], "80m": [(3600, 4000)], "60m": [(5332, 5405)],
        "40m": [(7125, 7300)], "30m": [], "20m": [(14150, 14350)],
        "17m": [(18110, 18168)], "15m": [(21200, 21450)], "12m": [(24930, 24990)],
        "10m": [(28300, 29700)], "6m": [(50100, 54000)],
    }
    
    # =========================================================================
    # CLUB LOG TOP 50 MOST WANTED (2024) - PRIORITY ALERTS
    # =========================================================================
    TOP_50_WANTED = {
        # Top 10
        "P5": ("North Korea", 1),
        "3Y/B": ("Bouvet Island", 2),
        "FT5/W": ("Crozet Island", 3),
        "BS7": ("Scarborough Reef", 4),
        "CE0X": ("San Felix", 5),
        "BV9P": ("Pratas Island", 6),
        "KH7K": ("Kure Island", 7),
        "KH3": ("Johnston Island", 8),
        "3Y/P": ("Peter I Island", 9),
        "FT5/X": ("Kerguelen", 10),
        # 11-20
        "VK0M": ("Macquarie Island", 11),
        "ZS8": ("Marion Island", 12),
        "EZ": ("Turkmenistan", 13),
        "KH1": ("Baker Howland", 14),
        "KH5": ("Palmyra Jarvis", 15),
        "VP8S": ("S Sandwich Is", 16),
        "VP8G": ("S Georgia Is", 17),
        "3D2/C": ("Conway Reef", 18),
        "SV/A": ("Mount Athos", 19),
        "YK": ("Syria", 20),
        # 21-30
        "FT/G": ("Glorioso Is", 21),
        "VU4": ("Andaman Is", 22),
        "VU7": ("Lakshadweep", 23),
        "ZL9": ("Auckland Is", 24),
        "FT/J": ("Juan de Nova", 25),
        "7O": ("Yemen", 26),
        "3C0": ("Annobon Island", 27),
        "FR/G": ("Glorioso", 28),
        "E3": ("Eritrea", 29),
        "T5": ("Somalia", 30),
        # 31-40
        "5A": ("Libya", 31),
        "EP": ("Iran", 32),
        "YI": ("Iraq", 33),
        "1A": ("SMOM", 34),
        "ZD9": ("Tristan da Cunha", 35),
        "3C": ("Equat Guinea", 36),
        "TT": ("Chad", 37),
        "TN": ("Congo", 38),
        "9U": ("Burundi", 39),
        "KH4": ("Midway Island", 40),
        # 41-50
        "VP8O": ("S Orkney Is", 41),
        "ZD7": ("St Helena", 42),
        "A5": ("Bhutan", 43),
        "VK0H": ("Heard Island", 44),
        "KP1": ("Navassa Island", 45),
        "FR/T": ("Tromelin", 46),
        "FT/T": ("Tromelin", 47),
        "3D2/R": ("Rotuma", 48),
        "FK/C": ("Chesterfield", 49),
        "KH8/S": ("Swains Island", 50),
    }
    
    # For backward compatibility
    RARE_DXCC = TOP_50_WANTED
    
    # =========================================================================
    # NCDXF/IARU BEACON SCHEDULE
    # =========================================================================
    BEACON_SCHEDULE = {
        "4U1UN": ("New York", 0), "VE8AT": ("Canada", 10), "W6WX": ("California", 20),
        "KH6RS": ("Hawaii", 30), "ZL6B": ("New Zealand", 40), "VK6RBP": ("Australia", 50),
        "JA2IGY": ("Japan", 60), "RR9O": ("Russia", 70), "VR2B": ("Hong Kong", 80),
        "4S7B": ("Sri Lanka", 90), "ZS6DN": ("South Africa", 100), "5Z4B": ("Kenya", 110),
        "4X6TU": ("Israel", 120), "OH2B": ("Finland", 130), "CS3B": ("Madeira", 140),
        "LU4AA": ("Argentina", 150), "OA4B": ("Peru", 160), "YV5B": ("Venezuela", 170),
    }
    BEACON_BANDS = ["20m", "17m", "15m", "12m", "10m"]
    BEACON_FREQS = {"20m": 14.100, "17m": 18.110, "15m": 21.150, "12m": 24.930, "10m": 28.200}
    
    # Contest weekends (month, weekend_number, name)
    
    # Country coordinates for world map
    COUNTRY_COORDS = {
        "US": (38, -97), "CA": (56, -106), "MX": (23, -102), "BR": (-14, -51),
        "AR": (-34, -64), "CL": (-35, -71), "VE": (7, -66), "CO": (4, -72),
        "PE": (-10, -76), "GB": (54, -2), "DE": (51, 10), "FR": (46, 2),
        "IT": (42, 12), "ES": (40, -4), "PT": (39, -8), "NL": (52, 5),
        "BE": (50, 4), "PL": (52, 20), "SE": (62, 15), "NO": (62, 10),
        "FI": (64, 26), "DK": (56, 10), "AT": (47, 14), "CH": (47, 8),
        "CZ": (50, 15), "HU": (47, 20), "RO": (46, 25), "BG": (43, 25),
        "GR": (39, 22), "TR": (39, 35), "UA": (49, 32), "RU": (60, 100),
        "JP": (36, 138), "CN": (35, 105), "KR": (36, 128), "IN": (21, 78),
        "TH": (15, 101), "MY": (4, 109), "ID": (-5, 120), "PH": (12, 122),
        "AU": (-25, 134), "NZ": (-41, 174), "ZA": (-29, 24), "EG": (27, 30),
        "KE": (-1, 38), "NG": (10, 8), "IL": (31, 35), "CU": (22, -80),
        "TW": (24, 121), "SG": (1, 104),
    }
    
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
    
    def __init__(self, plugin_id: str, config: Dict[str, Any],
                 display_manager, cache_manager, plugin_manager):
        super().__init__(plugin_id, config, display_manager, cache_manager, plugin_manager)
        
        # API Settings
        self.api_url = config.get("api_url", "https://api.wa0o.com/dxcache/spots")
        self.solar_url = config.get("solar_url", "https://www.hamqsl.com/solarxml.php")
        self.refresh_interval = config.get("refresh_interval", 900)
        self.solar_refresh_interval = config.get("solar_refresh_interval", 600)
        
        # Display Settings
        self.display_mode = config.get("display_mode", "rotate")
        self.vegas_views = config.get("vegas_views", ["spots", "conditions", "hotspots", "map", "grayline", "continents", "bandopen", "rate", "clock", "distance", "stats", "pota", "spacewx", "longpath", "beacon", "muf", "bestband"])
        self.vegas_view_index = 0
        self.page_duration = config.get("page_duration", 8)
        
        # Location for gray line - can use grid square or lat/lon
        grid = config.get("my_grid", "")
        if grid:
            self.my_lat, self.my_lon = self._grid_to_latlon(grid)
            self.my_grid = grid.upper()
            self.logger.info(f"Location from grid {grid}: {self.my_lat:.2f}, {self.my_lon:.2f}")
        else:
            self.my_lat = config.get("my_lat", 38.9)
            self.my_lon = config.get("my_lon", -90.5)
            self.my_grid = ""
        
        self.my_callsign = config.get("my_callsign", "")
        
        # Filtering
        self.show_voice = config.get("show_voice", True)
        self.show_cw = config.get("show_cw", False)
        self.show_digital = config.get("show_digital", False)
        self.filter_bands = config.get("filter_bands", [])
        self.exclude_bands = config.get("exclude_bands", [])
        self.max_spots = config.get("max_spots", 50)
        
        # Priority Alert Settings
        self.priority_enabled = config.get("priority_enabled", True)
        self.priority_duration = config.get("priority_duration", 300)  # 5 minutes
        self.priority_flash_speed = config.get("priority_flash_speed", 3)  # Hz
        
        # Display options
        self.show_flags = config.get("show_flags", True)
        self.show_frequency = config.get("show_frequency", True)
        self.show_mode = config.get("show_mode", True)
        self.show_age = config.get("show_age", True)
        self.title_color = tuple(config.get("title_color", [255, 200, 0]))
        self.pota_color = tuple(config.get("pota_color", [0, 255, 128]))
        self.rare_color = tuple(config.get("rare_color", [255, 0, 255]))
        self.priority_color = tuple(config.get("priority_color", [255, 0, 0]))  # Red for top 50
        
        # State
        self.all_spots: List[Dict] = []
        self.spots: List[Dict] = []
        self.priority_spots: List[Dict] = []  # Top 50 most wanted
        self.rare_spots: List[Dict] = []  # 21-40 rare
        self.solar_data: Dict[str, Any] = {}
        self.last_fetch = 0
        self.last_solar_fetch = 0
        self.current_page = 0
        self.last_page_change = time.time()
        
        # Priority Alert State
        self.priority_active = False
        self.priority_tier = None  # HIGH/MEDIUM/LOW/None
        self.priority_start_time = 0
        self.priority_callsign = ""
        self.test_priority_spot = None
        
        # Smooth Scrolling State (v3.3.0) - Priority alerts only
        self.enable_scrolling = False     # Controller checks for 125 FPS
        self._priority_phase = "attn"     # "attn" or "scroll"
        self._attn_start = None           # time.time() when attn phase started
        self._attn_duration = config.get("attention_duration", 12.0)  # 4 cards x 3s
        self._scroll_start_time = None    # time.time() when scroll phase started
        self._pri_scroll_speed = config.get("priority_scroll_speed", 50)  # px/sec
        self._pri_ticker_img = None       # Pre-rendered wide ticker image
        self._pri_ticker_width = 0
        self._pri_ticker_gap = 80
        self._pri_ticker_loop_width = 0
        self._pri_ticker_key = None       # Cache key to detect changes
        self._last_update_time = 0        # Throttle update() during 125 FPS
        self._update_throttle = 2.0       # Only update() every 2s
        
        # Priority alert timeout + cooldown (v3.3.1)
        self._priority_max_duration = config.get("priority_max_duration", 300)  # 5 min
        self._priority_cooldown_hours = config.get("priority_cooldown_hours", 6)  # 6h reset
        self._priority_cooldowns = {}     # {callsign: expire_timestamp}
        
        # Initialize
        self._load_fonts()
        self._load_flags()
        self._create_world_map()
        self.update()
        self._update_solar()
        
        self.logger.info(f"Ham Radio Spots v{__version__}: {len(self.spots)} spots, priority alerts: {self.priority_enabled}")
    
    def _load_fonts(self):
        self.font, self.font_large = load_fonts(__file__)
    
    def _load_flags(self):
        self.flags = {}
        flags_dir = Path(__file__).parent / "flags"
        if not flags_dir.exists():
            return
        for flag_file in flags_dir.glob("*.png"):
            code = flag_file.stem.upper()
            try:
                img = Image.open(flag_file).convert("RGB").resize((10, 7), Image.LANCZOS)
                self.flags[code] = img
            except:
                pass
    
    def _create_world_map(self):
        self.world_map = Image.new('RGB', (self.DISPLAY_WIDTH, self.DISPLAY_HEIGHT), (0, 0, 0))
        draw = ImageDraw.Draw(self.world_map)
        continents = {
            'na': [(20, 8), (25, 6), (35, 6), (45, 8), (50, 12), (45, 16), (35, 18), (25, 15), (20, 12), (20, 8)],
            'sa': [(35, 18), (40, 20), (42, 25), (38, 28), (32, 26), (30, 22), (35, 18)],
            'eu': [(85, 6), (95, 5), (105, 6), (110, 10), (100, 12), (90, 11), (85, 8), (85, 6)],
            'af': [(85, 12), (100, 12), (105, 18), (100, 26), (90, 28), (82, 22), (85, 12)],
            'as': [(110, 6), (130, 5), (150, 8), (160, 14), (150, 18), (130, 16), (115, 12), (110, 6)],
            'oc': [(150, 20), (165, 18), (170, 22), (165, 26), (155, 28), (150, 24), (150, 20)],
        }
        for name, points in continents.items():
            if len(points) > 2:
                draw.polygon(points, outline=(0, 50, 0), fill=(0, 20, 0))
    
    def validate_config(self) -> bool:
        return bool(self.api_url)
    
    # =========================================================================
    # TEST MODE - Inject fake priority spot
    # =========================================================================
    
    def test_priority_alert(self, callsign: str = "P5DX", rank: int = 1, 
                            name: str = "North Korea", band: str = "20m", 
                            freq: str = "14195000", mode: str = "SSB") -> None:
        """Inject a test priority spot to see the alert"""
        self.test_priority_spot = {
            "spotted": callsign,
            "spotter": "TEST",
            "band": band,
            "frequency": freq,
            "mode": mode,
            "message": mode,
            "when": datetime.now(timezone.utc).isoformat(),
            "priority_name": name,
            "priority_rank": rank,
            "dxcc_spotter": {"cont": "NA", "entity": "United States"},
            "dxcc_spotted": {"cont": "??", "entity": name},
        }

        # Run workability scoring
        work = self._calculate_workability(self.test_priority_spot)
        self.test_priority_spot["workability_score"] = work["score"]
        self.test_priority_spot["workability_level"] = work["level"]
        self.test_priority_spot["workability_na_count"] = work["na_count"]
        self.test_priority_spot["workability_factors"] = work["factors"]

        self.priority_spots = [self.test_priority_spot]
        self.priority_active = True  # Test always forces takeover
        # Use rank-based tier for testing
        rank_val = rank if isinstance(rank, int) else 1
        self.priority_tier = "TAKEOVER" if rank_val <= 10 else "DROPIN"
        self.priority_start_time = time.time()
        self.priority_callsign = callsign

        tier_name = "TAKEOVER" if rank <= 10 else "DROPIN"
        would_fire = f"YES ({tier_name})"
        self.logger.warning(
            f"TEST ALERT: {callsign} - {name} (#{rank}) {band} {mode} "
            f"WORKABILITY: {work['score']}/100 [{work['level']}] "
            f"Would fire in production: {would_fire} "
            f"NA:{work['na_count']} Factors:{work['factors']}")
    
    def clear_test_priority(self) -> None:
        """Clear test priority spot"""
        self.test_priority_spot = None
        self.priority_tier = None
        self.priority_spots = []
        self.priority_active = False
        self.logger.info("Test priority alert cleared")
    
    # =========================================================================
    # DATA FETCHING
    # =========================================================================
    
    def update(self) -> bool:
        self._check_test_priority()
        if time.time() - self.last_fetch < self.refresh_interval:
            return False
        try:
            response = requests.get(self.api_url, timeout=10)
            response.raise_for_status()
            self.all_spots = response.json()
            self.spots = self._filter_spots()
            
            # Check for priority (top 50) and rare (21-40) spots
            # Don't overwrite if test priority is active
            if not self.test_priority_spot:
                self.priority_spots = self._find_priority_dx()
            self.rare_spots = self._find_rare_dx()
            
            # Activate priority mode if top 50 found
            # RANK-BASED TIERS:
            #   Top 10 (#1-10)  = TAKEOVER - full MEGA JACKPOT display takeover
            #   Top 11-50       = DROPIN   - single card held for priority_display_duration
            if self.priority_spots and self.priority_enabled:
                call = self.priority_spots[0].get("spotted", "").upper()
                # Check cooldown - skip if this callsign was recently alerted
                now_ts = time.time()
                expire = self._priority_cooldowns.get(call, 0)
                if now_ts < expire:
                    mins_left = int((expire - now_ts) / 60)
                    self.logger.debug(f"Priority {call} suppressed - cooldown {mins_left}m remaining")
                    self.priority_active = False
                    self.priority_spots = []
                else:
                    best_spot = self.priority_spots[0]
                    rank = best_spot.get('priority_rank', 50)
                    score = best_spot.get('workability_score', 50)
                    name = best_spot.get('priority_name', 'RARE DX')
                    
                    if rank <= 10:
                        # TOP 10: Full takeover with JACKPOT cards
                        # Don't reset start time if already in TAKEOVER
                        if not self.priority_active or self.priority_tier != "TAKEOVER":
                            self.priority_start_time = now_ts
                        self.priority_active = True
                        self.priority_tier = "TAKEOVER"
                        self.priority_callsign = call
                        self.logger.warning(
                            f"🚨 TOP 10 TAKEOVER: #{rank} {call} - "
                            f"{name} ({score}/100)")
                    else:
                        # TOP 11-50: Drop-in card, Vegas holds then resumes
                        self.priority_active = False
                        self.priority_tier = "DROPIN"
                        self.priority_callsign = call
                        self.logger.info(
                            f"⚠️ TOP 50 DROP-IN: #{rank} {call} - "
                            f"{name} ({score}/100) - hold card")
            elif not self.test_priority_spot:
                # Only clear if no test spot AND no priority spots
                self.priority_active = False
                self.priority_tier = None
                self.priority_spots = []
            
            self.last_fetch = time.time()
            return True
        except Exception as e:
            self.logger.error(f"Fetch failed: {e}")
            return False
    
    def _update_solar(self) -> bool:
        if time.time() - self.last_solar_fetch < self.solar_refresh_interval and self.solar_data:
            return False
        try:
            response = requests.get(self.solar_url, timeout=10)
            root = ET.fromstring(response.content)
            solar = root.find('.//solardata')
            if solar:
                self.solar_data = {
                    'sfi': solar.findtext('solarflux', 'N/A'),
                    'k_index': solar.findtext('kindex', 'N/A'),
                    'a_index': solar.findtext('aindex', 'N/A'),
                }
                calc = solar.find('calculatedconditions')
                if calc:
                    for band in calc.findall('band'):
                        name = band.get('name', '').replace('-', '_')
                        self.solar_data[f"band_{name}_day"] = band.text or 'N/A'
                self.last_solar_fetch = time.time()
                return True
        except Exception as e:
            self.logger.error(f"Solar fetch failed: {e}")
        return False
    
    def _filter_spots(self) -> List[Dict]:
        seen = set()
        filtered = []
        for spot in self.all_spots:
            band = spot.get("band", "")
            callsign = spot.get("spotted", "")
            freq = spot.get("frequency", "")
            if (callsign, freq) in seen:
                continue
            seen.add((callsign, freq))
            if self.filter_bands and band not in self.filter_bands:
                continue
            if band in self.exclude_bands:
                continue
            try:
                freq_khz = float(freq)
                is_voice = self._is_voice_freq(freq_khz, band)
                if self.show_voice and is_voice:
                    filtered.append(spot)
                elif self.show_cw and not is_voice:
                    filtered.append(spot)
                elif self.show_digital and not is_voice:
                    filtered.append(spot)
            except:
                filtered.append(spot)
            if len(filtered) >= self.max_spots:
                break
        filtered.sort(key=lambda s: s.get("when", ""), reverse=True)
        return filtered
    
    def _find_priority_dx(self) -> List[Dict]:
        """Find TOP 50 most wanted DXCC entities - triggers priority alert.
        Calculates workability score and filters by level."""
        priority = []
        for spot in self.all_spots:
            callsign = spot.get("spotted", "").upper()
            for prefix, (name, rank) in self.TOP_50_WANTED.items():
                if callsign.startswith(prefix):
                    spot['priority_name'] = name
                    spot['priority_rank'] = rank
                    
                    # Calculate workability
                    work = self._calculate_workability(spot)
                    spot['workability_score'] = work['score']
                    spot['workability_level'] = work['level']
                    spot['workability_na_count'] = work['na_count']
                    spot['workability_factors'] = work['factors']
                    
                    self.logger.info(
                        f"TOP 50 workability: {callsign} ({name}) = {work['score']}/100 "
                        f"[{work['level']}] NA:{work['na_count']}/{work['total_spotters']} "
                        f"factors:{work['factors']}"
                    )
                    
                    # Include HIGH, MEDIUM, and LOW for tiered display
                    # Only UNLIKELY is fully suppressed
                    if work['level'] != "UNLIKELY":
                        priority.append(spot)
                    else:
                        self.logger.info(
                            f"Suppressed {callsign} - UNLIKELY "
                            f"({work['score']}/100)"
                        )
                    break
        priority.sort(key=lambda s: s.get('priority_rank', 999))
        return priority
    
    def _find_rare_dx(self) -> List[Dict]:
        """Find rare DX (21-40) - shown with special color but no priority alert"""
        rare = []
        for spot in self.all_spots:
            callsign = spot.get("spotted", "").upper()
            for prefix, (name, rank) in self.RARE_DXCC.items():
                if callsign.startswith(prefix):
                    spot['rare_name'] = name
                    spot['rare_rank'] = rank
                    rare.append(spot)
                    break
        rare.sort(key=lambda s: s.get('rare_rank', 999))
        return rare[:5]
    
    # =========================================================================
    # WORKABILITY SCORING
    # =========================================================================
    
    # Band openness windows from EM48 (Central Missouri) by UTC hour
    # Score 0-10 for each hour: 0=dead, 5=marginal, 10=peak
    BAND_TIME_MATRIX = {
        "160m": [9,9,9,9,8,7,5,2,0,0,0,0,0,0,0,0,0,0,0,0,1,3,5,8],
        "80m":  [9,9,9,8,7,5,3,1,0,0,0,0,0,0,0,0,0,0,0,1,3,5,7,9],
        "60m":  [8,8,7,7,6,5,3,2,1,1,1,1,1,1,2,3,4,5,6,7,8,8,8,8],
        "40m":  [9,9,8,7,6,5,4,3,2,2,3,4,5,6,7,7,6,5,5,6,7,8,9,9],
        "30m":  [7,7,6,6,5,5,4,4,4,5,6,7,8,8,8,7,6,5,5,5,6,7,7,7],
        "20m":  [5,4,3,2,1,1,1,2,3,5,7,8,9,9,9,9,8,7,6,5,5,5,5,5],
        "17m":  [3,2,1,1,0,0,0,1,2,4,6,8,9,9,9,8,7,6,5,4,4,3,3,3],
        "15m":  [2,1,1,0,0,0,0,0,1,3,5,7,9,9,9,8,7,5,4,3,3,2,2,2],
        "12m":  [1,0,0,0,0,0,0,0,0,2,4,6,8,9,9,8,6,4,3,2,1,1,1,1],
        "10m":  [0,0,0,0,0,0,0,0,0,1,3,5,7,9,9,8,6,4,2,1,0,0,0,0],
        "6m":   [0,0,0,0,0,0,0,0,0,1,2,4,6,7,7,6,4,2,1,0,0,0,0,0],
    }
    
    # NA prefixes for spotter continent detection (fallback if dxcc_spotter missing)
    NA_PREFIXES = {"W", "K", "N", "AA", "AB", "AC", "AD", "AE", "AF", "AG",
                   "VE", "VA", "VY", "XE", "KP", "KH", "KL", "KG4", "NP", "WP"}
    
    # SFI thresholds by band - minimum SFI for band to be usable
    SFI_BAND_MIN = {
        "160m": 0, "80m": 0, "60m": 0, "40m": 0, "30m": 0,
        "20m": 60, "17m": 70, "15m": 80, "12m": 90, "10m": 100, "6m": 110,
    }
    
    # My grid square coordinates
    MY_LAT = 38.6
    MY_LON = -90.5

    def _calculate_workability(self, priority_spot: dict) -> dict:
        """Calculate workability score (0-100) for a priority DX spot.
        
        Returns dict with:
            score: 0-100
            level: HIGH/MEDIUM/LOW/UNLIKELY
            na_count: number of NA spotters
            total_spotters: total spotters for this call
            factors: dict of individual factor scores for debugging
        """
        callsign = priority_spot.get("spotted", "").upper()
        band = priority_spot.get("band", "20m")
        freq = priority_spot.get("frequency", 0)
        mode = priority_spot.get("message", "").upper()  # mode often in message field
        
        # Also check dxcc_spotted mode field
        dxcc_spotted = priority_spot.get("dxcc_spotted", {})
        if not mode:
            mode = dxcc_spotted.get("pota_mode", "") or ""
        mode = mode.upper().strip()
        
        factors = {}
        
        # ---- FACTOR 1: NA Spotter Count (35 points max) ----
        na_count = 0
        total_spotters = 0
        for spot in self.all_spots:
            if spot.get("spotted", "").upper() == callsign:
                total_spotters += 1
                # Check continent from dxcc_spotter
                spotter_cont = spot.get("dxcc_spotter", {}).get("cont", "")
                if spotter_cont == "NA":
                    na_count += 1
                elif not spotter_cont:
                    # Fallback: check spotter callsign prefix
                    spotter_call = spot.get("spotter", "").upper()
                    for pfx in self.NA_PREFIXES:
                        if spotter_call.startswith(pfx):
                            na_count += 1
                            break
        
        if na_count >= 3:
            factors["na_spotters"] = 35
        elif na_count == 2:
            factors["na_spotters"] = 28
        elif na_count == 1:
            factors["na_spotters"] = 20
        elif total_spotters > 0:
            # No NA spotters but others hear it
            factors["na_spotters"] = 5
        else:
            factors["na_spotters"] = 0
        
        # ---- FACTOR 2: Band vs Time of Day (25 points max) ----
        now_utc = datetime.now(timezone.utc)
        hour = now_utc.hour
        band_time = self.BAND_TIME_MATRIX.get(band, [5]*24)
        raw_bt = band_time[hour]  # 0-10
        factors["band_time"] = int(raw_bt * 2.5)  # Scale to 0-25
        
        # ---- FACTOR 3: K-index (15 points max) ----
        try:
            k_index = int(self.solar_data.get("kindex", 2))
        except (ValueError, TypeError):
            k_index = 2
        
        if k_index <= 1:
            factors["k_index"] = 15
        elif k_index == 2:
            factors["k_index"] = 13
        elif k_index == 3:
            factors["k_index"] = 8
        elif k_index == 4:
            factors["k_index"] = 3
        else:
            factors["k_index"] = 0
        
        # ---- FACTOR 4: SFI vs Band (15 points max) ----
        try:
            sfi = float(self.solar_data.get("solarflux", 100))
        except (ValueError, TypeError):
            sfi = 100
        
        sfi_min = self.SFI_BAND_MIN.get(band, 0)
        if sfi_min == 0:
            # Low bands don't need SFI
            factors["sfi"] = 15
        elif sfi >= sfi_min + 30:
            factors["sfi"] = 15
        elif sfi >= sfi_min + 10:
            factors["sfi"] = 10
        elif sfi >= sfi_min:
            factors["sfi"] = 5
        else:
            # SFI too low for this band
            factors["sfi"] = 0
        
        # ---- FACTOR 5: Mode (10 points max) ----
        if "FT8" in mode or "FT4" in mode:
            factors["mode"] = 10  # Digital gets through best
        elif "CW" in mode:
            factors["mode"] = 8
        elif "RTTY" in mode or "PSK" in mode or "DIGI" in mode:
            factors["mode"] = 7
        elif "SSB" in mode or "USB" in mode or "LSB" in mode:
            factors["mode"] = 5
        else:
            factors["mode"] = 6  # Unknown mode, assume moderate
        
        # ---- TOTAL ----
        score = sum(factors.values())
        score = max(0, min(100, score))
        
        if score >= 70:
            level = "HIGH"
        elif score >= 40:
            level = "MEDIUM"
        elif score >= 15:
            level = "LOW"
        else:
            level = "UNLIKELY"
        
        return {
            "score": score,
            "level": level,
            "na_count": na_count,
            "total_spotters": total_spotters,
            "factors": factors,
        }

    def _is_voice_freq(self, freq_khz: float, band: str) -> bool:
        segments = self.VOICE_SEGMENTS.get(band, [])
        for low, high in segments:
            if low <= freq_khz <= high:
                return True
        return False
    
    def _calculate_sun_times(self, lat: float, lon: float, date: datetime) -> Tuple[datetime, datetime]:
        day_of_year = date.timetuple().tm_yday
        declination = 23.45 * math.sin(math.radians((360/365) * (day_of_year - 81)))
        lat_rad = math.radians(lat)
        dec_rad = math.radians(declination)
        try:
            cos_hour = -math.tan(lat_rad) * math.tan(dec_rad)
            cos_hour = max(-1, min(1, cos_hour))
            hour_angle = math.degrees(math.acos(cos_hour))
        except:
            hour_angle = 90
        solar_noon = 12 - (lon / 15)
        sunrise_utc = solar_noon - (hour_angle / 15)
        sunset_utc = solar_noon + (hour_angle / 15)
        base = date.replace(hour=0, minute=0, second=0, microsecond=0)
        sunrise = base + timedelta(hours=sunrise_utc)
        sunset = base + timedelta(hours=sunset_utc)
        return sunrise, sunset
    
    def _get_gray_line_lon(self) -> float:
        now = datetime.now(timezone.utc)
        hours_utc = now.hour + now.minute / 60
        return (12 - hours_utc) * 15
    
    def _calculate_distance_bearing(self, lat2: float, lon2: float) -> Tuple[float, float]:
        """Calculate distance (km) and bearing from my QTH to target"""
        lat1, lon1 = math.radians(self.my_lat), math.radians(self.my_lon)
        lat2, lon2 = math.radians(lat2), math.radians(lon2)
        
        # Haversine distance
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        km = 6371 * c
        
        # Bearing
        x = math.sin(dlon) * math.cos(lat2)
        y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
        bearing = math.degrees(math.atan2(x, y))
        if bearing < 0:
            bearing += 360
        
        return km, bearing
    
    def _get_continent(self, country_code: str) -> str:
        """Get continent for a country code"""
        continents = {
            "NA": ["US", "CA", "MX", "CU"],
            "SA": ["BR", "AR", "CL", "VE", "CO", "PE"],
            "EU": ["GB", "DE", "FR", "IT", "ES", "PT", "NL", "BE", "PL", "SE", "NO", "FI", "DK", "AT", "CH", "CZ", "HU", "RO", "BG", "GR", "UA", "IE"],
            "AF": ["ZA", "EG", "KE", "NG"],
            "AS": ["JP", "CN", "KR", "IN", "TH", "MY", "ID", "PH", "TW", "SG", "RU", "IL", "TR"],
            "OC": ["AU", "NZ"],
        }
        for cont, countries in continents.items():
            if country_code in countries:
                return cont
        return "??"
    
    @staticmethod
    def _grid_to_latlon(grid: str) -> Tuple[float, float]:
        """Convert Maidenhead grid square to lat/lon (center of grid)"""
        grid = grid.upper().strip()
        if len(grid) < 4:
            return 0.0, 0.0
        
        # Field (A-R)
        lon = (ord(grid[0]) - ord('A')) * 20 - 180
        lat = (ord(grid[1]) - ord('A')) * 10 - 90
        
        # Square (0-9)
        lon += int(grid[2]) * 2
        lat += int(grid[3]) * 1
        
        # Subsquare (a-x) if present
        if len(grid) >= 6:
            lon += (ord(grid[4].upper()) - ord('A')) * (2/24)
            lat += (ord(grid[5].upper()) - ord('A')) * (1/24)
            # Center of subsquare
            lon += 1/24
            lat += 0.5/24
        else:
            # Center of square
            lon += 1
            lat += 0.5
        
        return lat, lon
    
    # Helper methods
    def _get_mode(self, spot: Dict) -> str:
        mode = spot.get("dxcc_spotted", {}).get("pota_mode", "") or spot.get("mode", "")
        if not mode:
            try:
                freq = float(spot.get("frequency", 0))
                band = spot.get("band", "")
                mode = "SSB" if self._is_voice_freq(freq, band) else "CW"
            except:
                pass
        return mode.upper()[:3] if mode else ""
    
    def _get_age(self, spot: Dict) -> str:
        when = spot.get("when", "")
        if not when:
            return ""
        try:
            spot_time = datetime.fromisoformat(when.replace('Z', '+00:00'))
            minutes = int((datetime.now(timezone.utc) - spot_time).total_seconds() / 60)
            if minutes < 1:
                return "now"
            elif minutes < 60:
                return f"{minutes}m"
            return f"{minutes // 60}h"
        except:
            return ""
    
    def _get_flag(self, callsign: str) -> Optional[Image.Image]:
        if not callsign or not self.show_flags:
            return None
        callsign = callsign.upper()
        for length in range(min(3, len(callsign)), 0, -1):
            prefix = callsign[:length]
            if prefix in self.PREFIX_TO_ISO:
                return self.flags.get(self.PREFIX_TO_ISO[prefix])
        return None
    
    def _get_country_code(self, callsign: str) -> Optional[str]:
        callsign = callsign.upper()
        for length in range(min(3, len(callsign)), 0, -1):
            prefix = callsign[:length]
            if prefix in self.PREFIX_TO_ISO:
                return self.PREFIX_TO_ISO[prefix]
        return None
    
    def _latlon_to_pixel(self, lat: float, lon: float) -> Tuple[int, int]:
        x = int((lon + 180) * (self.DISPLAY_WIDTH / 360))
        y = int((90 - lat) * (self.DISPLAY_HEIGHT / 180))
        return max(0, min(self.DISPLAY_WIDTH - 1, x)), max(0, min(self.DISPLAY_HEIGHT - 1, y))
    
    def _get_band_counts(self) -> Dict[str, int]:
        counts = {}
        for spot in self.all_spots:
            band = spot.get("band", "")
            if band:
                counts[band] = counts.get(band, 0) + 1
        return counts
    
    def _color_for_band(self, band: str) -> tuple:
        return self.BAND_COLORS.get(band, (255, 255, 255))
    
    def _color_for_mode(self, mode: str) -> tuple:
        for key, color in self.MODE_COLORS.items():
            if key in mode.upper():
                return color
        return (180, 180, 180)
    
    def _color_for_condition(self, cond: str) -> tuple:
        c = cond.lower()
        if "good" in c:
            return (0, 255, 0)
        elif "fair" in c:
            return (255, 255, 0)
        elif "poor" in c:
            return (255, 0, 0)
        return (128, 128, 128)
    
    def _is_priority_spot(self, spot: Dict) -> bool:
        """Check if spot is TOP 50 most wanted"""
        callsign = spot.get("spotted", "").upper()
        for prefix in self.TOP_50_WANTED:
            if callsign.startswith(prefix):
                return True
        return False
    
    def _is_rare_spot(self, spot: Dict) -> bool:
        """Check if spot is rare (21-40)"""
        callsign = spot.get("spotted", "").upper()
        for prefix in self.RARE_DXCC:
            if callsign.startswith(prefix):
                return True
        return False
    
    # =========================================================================
    # DRAWING METHODS
    # =========================================================================
    

    def _generate_jackpot_cards(self) -> List[Image.Image]:
        """Generate celebration cards for Top 50 DX hit.
        Clean, readable layouts with consistent structure."""
        images = []

        if not self.priority_spots:
            return images

        spot = self.priority_spots[0]
        callsign = spot.get("spotted", "???")
        band = spot.get("band", "20m")
        freq = spot.get("frequency", "14195")
        mode = spot.get("mode", "SSB")
        name = spot.get("priority_name", "RARE DX")
        rank = spot.get("priority_rank", 1)

        try:
            freq_str = f"{float(freq)/1000:.3f}"
        except:
            freq_str = str(freq)

        flag = self._get_flag(callsign)
        band_color = self.BAND_COLORS.get(band, (255, 255, 0))
        mode_color = self._color_for_mode(mode)

        W = self.DISPLAY_WIDTH
        H = self.DISPLAY_HEIGHT
        CW = UX.CHAR_WIDTH

        # Two clean card styles, alternating through color schemes
        # Scheme: (bg, border, accent, text)
        schemes = [
            ((140, 0, 0),    (255, 255, 0), (255, 255, 0), (255, 255, 255)),  # Red/Yellow
            ((0, 0, 0),      (255, 200, 0), (255, 200, 0), (255, 255, 255)),  # Black/Gold
            ((120, 0, 80),   (255, 255, 255), (255, 255, 0), (255, 255, 255)),  # Purple/White
            ((0, 0, 120),    (0, 255, 255), (0, 255, 255), (255, 255, 255)),  # Blue/Cyan
            ((160, 100, 0),  (255, 255, 255), (255, 255, 255), (0, 0, 0)),    # Gold/White
            ((0, 100, 0),    (255, 255, 0), (255, 255, 0), (255, 255, 255)),  # Green/Yellow
        ]

        for i in range(12):
            img = Image.new('RGB', (W, H), (0, 0, 0))
            draw = ImageDraw.Draw(img)

            bg, border, accent, text = schemes[i % len(schemes)]
            draw.rectangle([0, 0, W, H], fill=bg)
            draw.rectangle([0, 0, W-1, H-1], outline=border)

            if i % 2 == 0:
                # Style A: Title row / callsign+freq row / entity row
                # Row 1
                draw.text((4, 3), f"#{rank}", font=self.font, fill=accent)
                title = "MEGA JACKPOT!"
                tx = (W - len(title) * CW) // 2
                draw.text((tx, 3), title, font=self.font, fill=accent)

                # Row 2: [flag] callsign   freq  band  mode
                x = 4
                if flag:
                    img.paste(flag, (x, 14))
                    x += 14
                draw.text((x, 13), callsign, font=self.font, fill=text)
                x += len(callsign) * CW + CW * 2
                draw.text((x, 13), freq_str, font=self.font, fill=band_color)
                x += len(freq_str) * CW + CW
                draw.text((x, 13), band, font=self.font, fill=band_color)
                x += len(band) * CW + CW
                draw.text((x, 13), mode, font=self.font, fill=mode_color)

                # Row 3: entity name + workability
                w_score = spot.get("workability_score", 0)
                w_na = spot.get("workability_na_count", 0)
                na_tag = f" NA:{w_na}" if w_na > 0 else ""
                draw.text((4, 24), f"{name[:16]}{na_tag} {w_score}%", font=self.font, fill=accent)

            else:
                # Style B: TOP 50 MOST WANTED / centered callsign / freq band mode entity
                # Row 1
                t = f"TOP 50 #{rank} MOST WANTED"
                tx = (W - len(t) * CW) // 2
                draw.text((tx, 3), t, font=self.font, fill=accent)

                # Row 2: centered callsign with flag
                call_w = len(callsign) * CW
                flag_w = 14 if flag else 0
                total = flag_w + call_w
                cx = (W - total) // 2
                if flag:
                    img.paste(flag, (cx, 14))
                    cx += 14
                draw.text((cx, 13), callsign, font=self.font, fill=text)

                # Row 3: freq  band  mode  entity
                x = 4
                draw.text((x, 24), freq_str, font=self.font, fill=band_color)
                x += len(freq_str) * CW + CW
                draw.text((x, 24), band, font=self.font, fill=band_color)
                x += len(band) * CW + CW
                draw.text((x, 24), mode, font=self.font, fill=mode_color)
                x += len(mode) * CW + CW * 2
                draw.text((x, 24), name[:14], font=self.font, fill=accent)

            images.append(img)

        return images


    def _generate_medium_cards(self) -> List[Image.Image]:
        """Generate 3 priority cards for MEDIUM tier - prominent but not dramatic.
        Gold border on dark background. Clean, informative layout."""
        images = []
        if not self.priority_spots:
            return images

        spot = self.priority_spots[0]
        callsign = spot.get("spotted", "???")
        band = spot.get("band", "20m")
        freq = spot.get("frequency", "14195")
        mode = spot.get("mode", "SSB")
        name = spot.get("priority_name", "RARE DX")
        rank = spot.get("priority_rank", 1)
        w_score = spot.get("workability_score", 50)
        w_na = spot.get("workability_na_count", 0)

        try:
            freq_str = f"{float(freq)/1000:.3f}"
        except:
            freq_str = str(freq)

        flag = self._get_flag(callsign)
        band_color = self.BAND_COLORS.get(band, (255, 255, 0))
        mode_color = self._color_for_mode(mode)
        W = self.DISPLAY_WIDTH
        H = self.DISPLAY_HEIGHT
        CW = UX.CHAR_WIDTH

        # Card 1: Main info card
        img1 = Image.new('RGB', (W, H), (0, 0, 15))
        d = ImageDraw.Draw(img1)
        d.rectangle([0, 0, W-1, H-1], outline=(200, 150, 0))

        d.text((4, 3), "DX ALERT", font=self.font, fill=(255, 200, 0))
        ri = f"#{rank}"
        d.text((W - len(ri) * CW - 4, 3), ri, font=self.font, fill=(255, 100, 100))

        x = 4
        if flag:
            img1.paste(flag, (x, 14))
            x += 14
        d.text((x, 13), callsign, font=self.font, fill=(255, 255, 255))
        rx = W - 4
        rx -= len(mode) * CW
        d.text((rx, 13), mode, font=self.font, fill=mode_color)
        rx -= CW
        rx -= len(band) * CW
        d.text((rx, 13), band, font=self.font, fill=band_color)
        rx -= CW
        rx -= len(freq_str) * CW
        d.text((rx, 13), freq_str, font=self.font, fill=band_color)

        na_tag = f"NA:{w_na} " if w_na > 0 else ""
        d.text((4, 24), f"{name[:16]} {na_tag}{w_score}%", font=self.font, fill=(200, 150, 0))
        images.append(img1)

        # Card 2: Centered callsign focus
        img2 = Image.new('RGB', (W, H), (0, 0, 15))
        d = ImageDraw.Draw(img2)
        d.rectangle([0, 0, W-1, H-1], outline=(200, 150, 0))

        t = f"TOP 50 #{rank} MOST WANTED"
        tx = (W - len(t) * CW) // 2
        d.text((tx, 3), t, font=self.font, fill=(200, 150, 0))

        call_w = len(callsign) * CW
        flag_w = 14 if flag else 0
        cx = (W - flag_w - call_w) // 2
        if flag:
            img2.paste(flag, (cx, 14))
            cx += 14
        d.text((cx, 13), callsign, font=self.font, fill=(255, 255, 255))

        info = f"{freq_str}  {band}  {mode}"
        ix = (W - len(info) * CW) // 2
        d.text((ix, 24), info, font=self.font, fill=(180, 180, 180))
        images.append(img2)

        # Card 3: Entity + score focus
        img3 = Image.new('RGB', (W, H), (0, 0, 15))
        d = ImageDraw.Draw(img3)
        d.rectangle([0, 0, W-1, H-1], outline=(200, 150, 0))

        d.text((4, 3), "DX ALERT", font=self.font, fill=(255, 200, 0))
        score_color = (0, 255, 0) if w_score >= 60 else (255, 255, 0)
        sc_text = f"{w_score}%"
        d.text((W - len(sc_text) * CW - 4, 3), sc_text, font=self.font, fill=score_color)

        d.text((4, 13), name[:28], font=self.font, fill=(0, 255, 255))

        x = 4
        if flag:
            img3.paste(flag, (x, 25))
            x += 14
        d.text((x, 24), callsign, font=self.font, fill=(255, 255, 255))
        x += len(callsign) * CW + CW * 2
        d.text((x, 24), band, font=self.font, fill=band_color)
        x += len(band) * CW + CW
        d.text((x, 24), mode, font=self.font, fill=mode_color)
        images.append(img3)

        return images

    def _generate_low_card(self) -> Optional[Image.Image]:
        """Generate 1 subtle card for LOW tier - quiet heads-up.
        Dim border, muted colors. Just enough to notice."""
        if not self.priority_spots:
            return None

        spot = self.priority_spots[0]
        callsign = spot.get("spotted", "???")
        band = spot.get("band", "20m")
        mode = spot.get("mode", "SSB")
        name = spot.get("priority_name", "RARE DX")
        rank = spot.get("priority_rank", 1)
        w_score = spot.get("workability_score", 25)

        flag = self._get_flag(callsign)
        band_color = self.BAND_COLORS.get(band, (255, 255, 0))
        mode_color = self._color_for_mode(mode)
        W = self.DISPLAY_WIDTH
        H = self.DISPLAY_HEIGHT
        CW = UX.CHAR_WIDTH

        img = Image.new('RGB', (W, H), (0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, W-1, H-1], outline=(60, 60, 60))

        d.text((4, 3), "TOP 50 SPOTTED", font=self.font, fill=(100, 100, 100))
        ri = f"#{rank}"
        d.text((W - len(ri) * CW - 4, 3), ri, font=self.font, fill=(100, 60, 60))

        x = 4
        if flag:
            img.paste(flag, (x, 14))
            x += 14
        d.text((x, 13), callsign, font=self.font, fill=(180, 180, 180))
        rx = W - 4
        rx -= len(mode) * CW
        d.text((rx, 13), mode, font=self.font, fill=mode_color)
        rx -= CW
        rx -= len(band) * CW
        d.text((rx, 13), band, font=self.font, fill=band_color)

        d.text((4, 24), name[:18], font=self.font, fill=(80, 80, 80))
        sc = f"{w_score}%"
        d.text((W - len(sc) * CW - 4, 24), sc, font=self.font, fill=(80, 80, 80))

        return img


    def _generate_dropin_card(self) -> List[Image.Image]:
        """Generate drop-in priority card for Top 11-50.
        Gold bordered, prominent but not dramatic. Shows all key info
        so you can act on it during the 15-second hold."""
        images = []
        if not self.priority_spots:
            return images

        spot = self.priority_spots[0]
        callsign = spot.get("spotted", "???")
        band = spot.get("band", "20m")
        freq = spot.get("frequency", "14195")
        mode = spot.get("mode", "SSB")
        name = spot.get("priority_name", "RARE DX")
        rank = spot.get("priority_rank", 1)
        w_score = spot.get("workability_score", 50)
        w_na = spot.get("workability_na_count", 0)

        try:
            freq_str = f"{float(freq)/1000:.3f}"
        except:
            freq_str = str(freq)

        flag = self._get_flag(callsign)
        band_color = self.BAND_COLORS.get(band, (255, 255, 0))
        mode_color = self._color_for_mode(mode)
        W = self.DISPLAY_WIDTH
        H = self.DISPLAY_HEIGHT
        CW = UX.CHAR_WIDTH

        # Card 1: Main info - everything you need to jump on it
        img1 = Image.new('RGB', (W, H), (10, 5, 0))
        d = ImageDraw.Draw(img1)
        # Double gold border for emphasis
        d.rectangle([0, 0, W-1, H-1], outline=(255, 200, 0))
        d.rectangle([1, 1, W-2, H-2], outline=(180, 140, 0))

        # Row 1: DX ALERT  #rank  workability%
        d.text((4, 2), "DX ALERT", font=self.font, fill=(255, 200, 0))
        ri = f"#{rank}"
        d.text((80, 2), ri, font=self.font, fill=(255, 100, 100))
        score_color = (0, 255, 0) if w_score >= 60 else (255, 255, 0) if w_score >= 40 else (255, 100, 100)
        sc = f"{w_score}%"
        d.text((W - len(sc) * CW - 4, 2), sc, font=self.font, fill=score_color)

        # Row 2: [flag] CALLSIGN  freq  band  mode
        x = 4
        if flag:
            img1.paste(flag, (x, 13))
            x += 14
        d.text((x, 12), callsign, font=self.font, fill=(255, 255, 255))
        # Right-align freq band mode
        rx = W - 4
        rx -= len(mode) * CW
        d.text((rx, 12), mode, font=self.font, fill=mode_color)
        rx -= CW
        rx -= len(band) * CW
        d.text((rx, 12), band, font=self.font, fill=band_color)
        rx -= CW
        rx -= len(freq_str) * CW
        d.text((rx, 12), freq_str, font=self.font, fill=band_color)

        # Row 3: Entity name  NA:count
        na_tag = f"NA:{w_na}" if w_na > 0 else ""
        d.text((4, 23), name[:20], font=self.font, fill=(0, 255, 255))
        if na_tag:
            d.text((W - len(na_tag) * CW - 4, 23), na_tag, font=self.font, fill=(0, 200, 255))

        images.append(img1)

        # Card 2: Alternate layout - centered callsign emphasis
        img2 = Image.new('RGB', (W, H), (10, 5, 0))
        d = ImageDraw.Draw(img2)
        d.rectangle([0, 0, W-1, H-1], outline=(255, 200, 0))
        d.rectangle([1, 1, W-2, H-2], outline=(180, 140, 0))

        # Row 1: TOP 50 MOST WANTED  #rank
        t = "TOP 50 MOST WANTED"
        tx = (W - len(t) * CW) // 2
        d.text((tx, 2), t, font=self.font, fill=(255, 200, 0))

        # Row 2: centered [flag] CALLSIGN
        call_w = len(callsign) * CW
        flag_w = 14 if flag else 0
        cx = (W - flag_w - call_w) // 2
        if flag:
            img2.paste(flag, (cx, 13))
            cx += 14
        d.text((cx, 12), callsign, font=self.font, fill=(255, 255, 255))

        # Row 3: freq  band  mode  entity
        x = 4
        d.text((x, 23), freq_str, font=self.font, fill=band_color)
        x += len(freq_str) * CW + CW
        d.text((x, 23), band, font=self.font, fill=band_color)
        x += len(band) * CW + CW
        d.text((x, 23), mode, font=self.font, fill=mode_color)
        x += len(mode) * CW + CW * 2
        d.text((x, 23), name[:14], font=self.font, fill=(200, 150, 0))

        images.append(img2)

        return images

    def _draw_priority_alert(self, img: Image.Image, draw: ImageDraw.ImageDraw, frame: int = 0) -> None:
        """Draw clean, readable priority alert cards for TOP 50 most wanted.
        4 color schemes, one consistent layout, band/mode colored."""

        if not self.priority_spots:
            return

        spot = self.priority_spots[0]
        callsign = spot.get("spotted", "???")
        band = spot.get("band", "20m")
        freq = spot.get("frequency", "")
        mode = spot.get("mode", "SSB")
        name = spot.get("priority_name", "RARE DX")
        rank = spot.get("priority_rank", 0)

        try:
            freq_str = f"{float(freq)/1000:.3f}"
        except:
            freq_str = str(freq)

        W = self.DISPLAY_WIDTH
        H = self.DISPLAY_HEIGHT
        CW = UX.CHAR_WIDTH
        band_color = self.BAND_COLORS.get(band, (255, 255, 0))
        mode_color = self._color_for_mode(mode)
        flag = self._get_flag(callsign)

        scheme = frame % 4

        # Color schemes: (bg, border, accent, text)
        color_map = [
            ((140, 0, 0),   (255, 255, 0), (255, 255, 0), (255, 255, 255)),  # Red
            ((0, 0, 0),     (255, 200, 0), (255, 200, 0), (255, 255, 255)),  # Black/Gold
            ((120, 0, 80),  (255, 255, 0), (255, 255, 0), (255, 255, 255)),  # Purple
            ((200, 200, 200), (255, 0, 0), (200, 0, 0), (0, 0, 0)),          # White/Red
        ]
        bg, border, accent, text = color_map[scheme]

        # Background + border
        draw.rectangle([0, 0, W, H], fill=bg)
        draw.rectangle([0, 0, W-1, H-1], outline=border)

        # Row 1: >> TOP 50 DX! <<  #rank
        if frame % 2 == 0:
            draw.text((4, 3), ">>", font=self.font, fill=accent)
            draw.text((W - 16, 3), "<<", font=self.font, fill=accent)
        draw.text((24, 3), "TOP 50 DX!", font=self.font, fill=accent)
        # Show workability score + rank
        w_score = spot.get("workability_score", 0)
        w_level = spot.get("workability_level", "?")
        w_na = spot.get("workability_na_count", 0)
        rank_info = f"#{rank}"
        if w_level == "MEDIUM":
            rank_info += " MED"
        rx = W - len(rank_info) * CW - 6
        draw.text((rx, 3), rank_info, font=self.font, fill=accent)

        # Row 2: [flag] CALLSIGN    freq  band  mode
        x = 4
        if flag:
            img.paste(flag, (x, 14))
            x += 14
        draw.text((x, 13), callsign, font=self.font, fill=text)
        # Right-align freq band mode
        mode_str = mode
        band_str = band
        right_x = W - 4
        right_x -= len(mode_str) * CW
        draw.text((right_x, 13), mode_str, font=self.font, fill=mode_color)
        right_x -= CW
        right_x -= len(band_str) * CW
        draw.text((right_x, 13), band_str, font=self.font, fill=band_color)
        right_x -= CW
        right_x -= len(freq_str) * CW
        draw.text((right_x, 13), freq_str, font=self.font, fill=band_color)

        # Row 3: Entity name + NA spotter count + score
        na_tag = f" NA:{w_na}" if w_na > 0 else ""
        entity_text = f"{name[:18]}{na_tag} {w_score}%"
        draw.text((4, 24), entity_text, font=self.font, fill=accent)


    # =========================================================================
    # NEW VIEW CARDS
    # =========================================================================
    
    def _draw_continents_view(self, img: Image.Image, draw: ImageDraw.ImageDraw) -> None:
        """Continent breakdown - spots by region"""
        draw.text((2, self.TITLE_Y), "CONTINENTS", font=self.font, fill=self.title_color)
        
        # Count spots by continent
        counts = {"NA": 0, "SA": 0, "EU": 0, "AF": 0, "AS": 0, "OC": 0}
        for spot in self.all_spots:
            callsign = spot.get("spotted", "")
            country = self._get_country_code(callsign)
            if country:
                cont = self._get_continent(country)
                if cont in counts:
                    counts[cont] += 1
        
        total = sum(counts.values()) or 1
        
        # Draw bars for each continent
        colors = {
            "NA": (0, 150, 255), "SA": (0, 255, 100), "EU": (255, 200, 0),
            "AF": (255, 100, 0), "AS": (255, 0, 128), "OC": (0, 255, 255)
        }
        
        x = 2
        for cont in ["NA", "EU", "AS", "SA", "AF", "OC"]:
            count = counts[cont]
            color = colors[cont]
            draw.text((x, 10), cont, font=self.font, fill=color)
            bar_height = min(20, int((count / total) * 40)) if total > 0 else 0
            draw.rectangle([x, 30-bar_height, x+12, 30], fill=color)
            draw.text((x, 22), str(count), font=self.font, fill=(150, 150, 150))
            x += 32
    
    def _draw_band_opening_view(self, img: Image.Image, draw: ImageDraw.ImageDraw) -> None:
        """Band opening indicator - activity spikes"""
        draw.text((2, self.TITLE_Y), "BAND OPEN", font=self.font, fill=self.title_color)
        
        # Get band counts
        counts = self._get_band_counts()
        if not counts:
            draw.text((2, self.ROW1_Y), "No activity", font=self.font, fill=(128, 128, 128))
            return
        
        # Find hottest band
        hottest = max(counts.items(), key=lambda x: x[1])
        hot_band, hot_count = hottest
        
        # Determine if it's a "opening" (more than 10 spots)
        if hot_count >= 10:
            status = "HOT!"
            status_color = (255, 0, 0)
        elif hot_count >= 5:
            status = "OPEN"
            status_color = (255, 255, 0)
        else:
            status = "Quiet"
            status_color = (100, 100, 100)
        
        draw.text((100, self.TITLE_Y), status, font=self.font, fill=status_color)
        
        # Show top 2 bands
        sorted_bands = sorted(counts.items(), key=lambda x: -x[1])[:2]
        y = self.ROW1_Y
        for band, count in sorted_bands:
            color = self._color_for_band(band)
            draw.text((2, y), f"{band}: {count} spots", font=self.font, fill=color)
            # Activity bar
            bar_w = min(80, count * 4)
            draw.rectangle([90, y+2, 90+bar_w, y+6], fill=color)
            y += 11
    
    def _draw_qso_rate_view(self, img: Image.Image, draw: ImageDraw.ImageDraw) -> None:
        """QSO rate - spots activity graph"""
        draw.text((2, self.TITLE_Y), "SPOT RATE", font=self.font, fill=self.title_color)
        
        # Count spots by age (last 60 min in 10-min buckets)
        now = datetime.now(timezone.utc)
        buckets = [0] * 6  # 6 x 10-min buckets
        
        for spot in self.all_spots:
            when = spot.get("when", "")
            if not when:
                continue
            try:
                spot_time = datetime.fromisoformat(when.replace('Z', '+00:00'))
                age_min = (now - spot_time).total_seconds() / 60
                if age_min < 60:
                    bucket = int(age_min / 10)
                    if 0 <= bucket < 6:
                        buckets[bucket] += 1
            except:
                pass
        
        max_bucket = max(buckets) or 1
        total = sum(buckets)
        rate = total  # spots per hour
        
        draw.text((100, self.TITLE_Y), f"{rate}/hr", font=self.font, fill=(0, 255, 0))
        
        # Draw bar graph
        bar_width = 25
        x = 10
        for i, count in enumerate(buckets):
            bar_height = int((count / max_bucket) * 18) if max_bucket > 0 else 0
            color = (0, 255, 0) if i == 0 else (100, 200, 100)
            draw.rectangle([x, 30-bar_height, x+bar_width-2, 30], fill=color)
            x += bar_width
        
        # Labels
        draw.text((5, 22), "now", font=self.font, fill=(150, 150, 150))
        draw.text((155, 22), "60m", font=self.font, fill=(150, 150, 150))
    
    def _draw_clock_view(self, img: Image.Image, draw: ImageDraw.ImageDraw) -> None:
        """Big UTC clock with callsign"""
        now_utc = datetime.now(timezone.utc)
        now_local = datetime.now()
        
        # Callsign or UTC label
        if self.my_callsign:
            draw.text((2, self.TITLE_Y), self.my_callsign[:10], font=self.font, fill=(0, 255, 255))
        else:
            draw.text((2, self.TITLE_Y), "UTC", font=self.font, fill=self.title_color)
        
        # Spot count badge
        spot_count = len(self.spots)
        draw.text((160, self.TITLE_Y), f"{spot_count}sp", font=self.font, fill=(100, 255, 100))
        
        # Big UTC time
        utc_str = now_utc.strftime("%H:%M:%S")
        draw.text((50, 8), utc_str, font=self.font_large, fill=(0, 255, 255))
        
        # Local time
        local_str = now_local.strftime("%H:%M:%S")
        draw.text((2, 22), "LOC", font=self.font, fill=(150, 150, 150))
        draw.text((30, 22), local_str, font=self.font, fill=(200, 200, 200))
        
        # Day of week and date
        day_str = now_utc.strftime("%a")
        date_str = now_utc.strftime("%m/%d")
        draw.text((120, 22), day_str, font=self.font, fill=(255, 200, 0))
        draw.text((150, 22), date_str, font=self.font, fill=(150, 150, 150))
    
    def _draw_distance_view(self, img: Image.Image, draw: ImageDraw.ImageDraw) -> None:
        """Distance and bearing to current DX"""
        draw.text((2, self.TITLE_Y), "DISTANCE", font=self.font, fill=self.title_color)
        
        if not self.spots:
            draw.text((2, self.ROW1_Y), "No spots", font=self.font, fill=(128, 128, 128))
            return
        
        # Get first spot with known coordinates
        for spot in self.spots[:3]:
            callsign = spot.get("spotted", "")
            country = self._get_country_code(callsign)
            if country and country in self.COUNTRY_COORDS:
                lat, lon = self.COUNTRY_COORDS[country]
                km, bearing = self._calculate_distance_bearing(lat, lon)
                miles = km * 0.621371
                
                # Direction from bearing
                dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
                dir_idx = int((bearing + 22.5) / 45) % 8
                direction = dirs[dir_idx]
                
                band = spot.get("band", "")
                draw.text((2, self.ROW1_Y), f"{callsign[:8]}", font=self.font, fill=(255, 255, 255))
                draw.text((70, self.ROW1_Y), f"{int(km):,}km", font=self.font, fill=(0, 255, 255))
                draw.text((130, self.ROW1_Y), f"{int(miles):,}mi", font=self.font, fill=(0, 200, 200))
                draw.text((2, self.ROW2_Y), f"{int(bearing)}° {direction}", font=self.font, fill=(255, 200, 0))
                draw.text((70, self.ROW2_Y), band, font=self.font, fill=self._color_for_band(band))
                return
        
        draw.text((2, self.ROW1_Y), "No coords", font=self.font, fill=(128, 128, 128))
    
    def _draw_stats_view(self, img: Image.Image, draw: ImageDraw.ImageDraw) -> None:
        """Activity stats summary"""
        draw.text((2, self.TITLE_Y), "STATS", font=self.font, fill=self.title_color)
        
        total = len(self.all_spots)
        filtered = len(self.spots)
        bands = len(self._get_band_counts())
        
        # Count unique callsigns
        calls = set(s.get("spotted", "") for s in self.all_spots)
        unique = len(calls)
        
        # Count countries
        countries = set()
        for spot in self.all_spots:
            c = self._get_country_code(spot.get("spotted", ""))
            if c:
                countries.add(c)
        
        draw.text((2, self.ROW1_Y), f"Spots:{total}", font=self.font, fill=(255, 255, 255))
        draw.text((70, self.ROW1_Y), f"SSB:{filtered}", font=self.font, fill=(100, 255, 100))
        draw.text((130, self.ROW1_Y), f"Bands:{bands}", font=self.font, fill=(255, 200, 0))
        
        draw.text((2, self.ROW2_Y), f"Calls:{unique}", font=self.font, fill=(0, 255, 255))
        draw.text((80, self.ROW2_Y), f"DXCC:{len(countries)}", font=self.font, fill=(255, 100, 255))


    # =========================================================================
    # ADDITIONAL VIEW CARDS
    # =========================================================================
    
    def _draw_pota_view(self, img: Image.Image, draw: ImageDraw.ImageDraw) -> None:
        """POTA/SOTA Activators"""
        draw.text((2, self.TITLE_Y), "POTA/SOTA", font=self.font, fill=(0, 255, 128))
        
        # Find POTA spots
        pota_spots = [s for s in self.all_spots if s.get("source") == "pota" or "POTA" in s.get("comment", "").upper()]
        sota_spots = [s for s in self.all_spots if "SOTA" in s.get("comment", "").upper()]
        
        if not pota_spots and not sota_spots:
            draw.text((2, self.ROW1_Y), "No activators", font=self.font, fill=(128, 128, 128))
            draw.text((2, self.ROW2_Y), "spotted", font=self.font, fill=(128, 128, 128))
            return
        
        # Show counts
        draw.text((100, self.TITLE_Y), f"P:{len(pota_spots)} S:{len(sota_spots)}", font=self.font, fill=(200, 200, 200))
        
        # Show first POTA
        y = self.ROW1_Y
        for spot in pota_spots[:1]:
            call = spot.get("spotted", "")[:8]
            band = spot.get("band", "")
            draw.text((2, y), "P", font=self.font, fill=(0, 255, 128))
            draw.text((12, y), call, font=self.font, fill=(255, 255, 255))
            draw.text((70, y), band, font=self.font, fill=self._color_for_band(band))
            y += 11
        
        # Show first SOTA
        for spot in sota_spots[:1]:
            call = spot.get("spotted", "")[:8]
            band = spot.get("band", "")
            draw.text((2, y), "S", font=self.font, fill=(255, 165, 0))
            draw.text((12, y), call, font=self.font, fill=(255, 255, 255))
            draw.text((70, y), band, font=self.font, fill=self._color_for_band(band))
    
    def _draw_space_weather_view(self, img: Image.Image, draw: ImageDraw.ImageDraw) -> None:
        """Space Weather Warnings"""
        draw.text((2, self.TITLE_Y), "SPACE WX", font=self.font, fill=self.title_color)
        
        # Get K-index and determine alert level
        k_index = self.solar_data.get('k_index', 'N/A')
        sfi = self.solar_data.get('sfi', 'N/A')
        a_index = self.solar_data.get('a_index', 'N/A')
        
        try:
            k_val = int(str(k_index).strip())
            if k_val >= 7:
                alert = "STORM!"
                alert_color = (255, 0, 0)
                status = "HF Blackout"
            elif k_val >= 5:
                alert = "WARNING"
                alert_color = (255, 100, 0)
                status = "Degraded"
            elif k_val >= 4:
                alert = "ACTIVE"
                alert_color = (255, 255, 0)
                status = "Unsettled"
            else:
                alert = "QUIET"
                alert_color = (0, 255, 0)
                status = "Normal"
        except:
            alert = "N/A"
            alert_color = (128, 128, 128)
            status = "Unknown"
        
        # Display
        draw.text((90, self.TITLE_Y), alert, font=self.font, fill=alert_color)
        
        draw.text((2, self.ROW1_Y), f"K:{k_index}", font=self.font, fill=alert_color)
        draw.text((45, self.ROW1_Y), f"A:{a_index}", font=self.font, fill=(200, 200, 200))
        draw.text((90, self.ROW1_Y), f"SFI:{sfi}", font=self.font, fill=(0, 255, 255))
        
        draw.text((2, self.ROW2_Y), f"HF: {status}", font=self.font, fill=alert_color)
        
        # Band recommendation based on SFI
        try:
            sfi_val = int(str(sfi).strip())
            if sfi_val >= 150:
                rec = "10-15m HOT"
            elif sfi_val >= 100:
                rec = "20m Good"
            else:
                rec = "40-80m Best"
            draw.text((100, self.ROW2_Y), rec, font=self.font, fill=(0, 255, 0))
        except:
            pass
    
    def _draw_longpath_view(self, img: Image.Image, draw: ImageDraw.ImageDraw) -> None:
        """Long Path Indicator"""
        draw.text((2, self.TITLE_Y), "PATH", font=self.font, fill=self.title_color)
        
        now = datetime.now(timezone.utc)
        hour = now.hour
        
        # Long path windows (approximate)
        # LP to Asia: ~12-16 UTC from NA
        # LP to Europe: ~20-00 UTC from NA
        # LP to Pacific: ~06-10 UTC from NA
        
        lp_asia = 12 <= hour <= 16
        lp_eu = 20 <= hour or hour <= 0
        lp_pacific = 6 <= hour <= 10
        
        draw.text((2, self.ROW1_Y), "Asia:", font=self.font, fill=(200, 200, 200))
        if lp_asia:
            draw.text((40, self.ROW1_Y), "LP NOW!", font=self.font, fill=(0, 255, 0))
        else:
            draw.text((40, self.ROW1_Y), "SP", font=self.font, fill=(128, 128, 128))
        
        draw.text((90, self.ROW1_Y), "EU:", font=self.font, fill=(200, 200, 200))
        if lp_eu:
            draw.text((115, self.ROW1_Y), "LP NOW!", font=self.font, fill=(0, 255, 0))
        else:
            draw.text((115, self.ROW1_Y), "SP", font=self.font, fill=(128, 128, 128))
        
        draw.text((2, self.ROW2_Y), "Pacific:", font=self.font, fill=(200, 200, 200))
        if lp_pacific:
            draw.text((55, self.ROW2_Y), "LP NOW!", font=self.font, fill=(0, 255, 0))
        else:
            draw.text((55, self.ROW2_Y), "SP", font=self.font, fill=(128, 128, 128))
        
        draw.text((120, self.ROW2_Y), f"{hour:02d}z", font=self.font, fill=(150, 150, 150))
    
    def _draw_beacon_view(self, img: Image.Image, draw: ImageDraw.ImageDraw) -> None:
        """NCDXF/IARU Beacon Monitor"""
        draw.text((2, self.TITLE_Y), "BEACONS", font=self.font, fill=self.title_color)
        
        now = datetime.now(timezone.utc)
        # 3-minute cycle, each beacon transmits for 10 seconds on each band
        cycle_second = (now.minute % 3) * 60 + now.second
        
        # Find current beacon
        current_beacon = None
        for call, (loc, start) in self.BEACON_SCHEDULE.items():
            if start <= cycle_second < start + 10:
                current_beacon = (call, loc)
                break
        
        # Current band in cycle (changes every 10 seconds within beacon's slot)
        band_idx = (cycle_second % 50) // 10
        if band_idx < len(self.BEACON_BANDS):
            current_band = self.BEACON_BANDS[band_idx]
            freq = self.BEACON_FREQS.get(current_band, 0)
        else:
            current_band = "20m"
            freq = 14.100
        
        if current_beacon:
            call, loc = current_beacon
            draw.text((2, self.ROW1_Y), f"{call}", font=self.font, fill=(0, 255, 255))
            draw.text((70, self.ROW1_Y), loc[:12], font=self.font, fill=(200, 200, 200))
        else:
            draw.text((2, self.ROW1_Y), "Between beacons", font=self.font, fill=(128, 128, 128))
        
        draw.text((2, self.ROW2_Y), f"{current_band}", font=self.font, fill=self._color_for_band(current_band))
        draw.text((40, self.ROW2_Y), f"{freq:.3f} MHz", font=self.font, fill=(255, 255, 255))
        
        # Next beacon
        next_second = (cycle_second + 10) % 180
        for call, (loc, start) in self.BEACON_SCHEDULE.items():
            if start <= next_second < start + 10:
                draw.text((130, self.ROW2_Y), f">{call[:6]}", font=self.font, fill=(150, 150, 150))
                break
    
    def _draw_muf_view(self, img: Image.Image, draw: ImageDraw.ImageDraw) -> None:
        """MUF Display - Maximum Usable Frequency prediction"""
        draw.text((2, self.TITLE_Y), "MUF", font=self.font, fill=self.title_color)
        
        # Estimate MUF based on SFI and time of day
        sfi = self.solar_data.get('sfi', 'N/A')
        now = datetime.now(timezone.utc)
        hour = now.hour
        
        # Daytime hours have higher MUF
        is_day = 12 <= hour <= 23 or hour <= 2  # Roughly
        
        try:
            sfi_val = int(str(sfi).strip())
            # Rough MUF estimation
            base_muf = 10 + (sfi_val - 70) * 0.15
            if is_day:
                base_muf *= 1.3
            muf = max(7, min(30, base_muf))
            
            draw.text((40, self.TITLE_Y), f"~{muf:.0f} MHz", font=self.font, fill=(0, 255, 255))
        except:
            muf = 14
            draw.text((40, self.TITLE_Y), "Est: 14 MHz", font=self.font, fill=(128, 128, 128))
        
        # Show which bands are likely open
        draw.text((2, self.ROW1_Y), "Open:", font=self.font, fill=(200, 200, 200))
        x = 40
        for band, freq in [("40m", 7), ("30m", 10), ("20m", 14), ("17m", 18), ("15m", 21), ("12m", 24), ("10m", 28)]:
            if freq <= muf:
                color = (0, 255, 0)
            else:
                color = (80, 80, 80)
            draw.text((x, self.ROW1_Y), band[:2], font=self.font, fill=color)
            x += 22
        
        draw.text((2, self.ROW2_Y), "SFI:", font=self.font, fill=(150, 150, 150))
        draw.text((30, self.ROW2_Y), str(sfi), font=self.font, fill=(255, 255, 0))
        draw.text((70, self.ROW2_Y), "Day" if is_day else "Night", font=self.font, fill=(100, 200, 255) if is_day else (100, 100, 200))
    
    def _draw_bestband_view(self, img: Image.Image, draw: ImageDraw.ImageDraw) -> None:
        """Best Band Right Now recommendation"""
        draw.text((2, self.TITLE_Y), "BEST BAND", font=self.font, fill=self.title_color)
        
        # Get band counts and conditions
        counts = self._get_band_counts()
        sfi = self.solar_data.get('sfi', 'N/A')
        k_index = self.solar_data.get('k_index', 'N/A')
        
        if not counts:
            draw.text((2, self.ROW1_Y), "No data", font=self.font, fill=(128, 128, 128))
            return
        
        # Score bands based on activity and conditions
        scores = {}
        for band, count in counts.items():
            score = count
            # Boost based on conditions
            try:
                sfi_val = int(str(sfi).strip())
                if band in ["10m", "12m", "15m"] and sfi_val >= 120:
                    score *= 1.5
                elif band in ["20m", "17m"] and sfi_val >= 90:
                    score *= 1.3
            except:
                pass
            scores[band] = score
        
        # Find best band
        best = max(scores.items(), key=lambda x: x[1])
        best_band = best[0]
        
        # Big recommendation
        color = self._color_for_band(best_band)
        draw.text((60, 8), best_band, font=self.font_large, fill=color)
        draw.text((2, self.ROW1_Y), "WORK", font=self.font, fill=(200, 200, 200))
        draw.text((130, 8), "NOW!", font=self.font, fill=(0, 255, 0))
        
        # Activity count
        draw.text((2, self.ROW2_Y), f"{counts.get(best_band, 0)} spots", font=self.font, fill=(150, 150, 150))
        
        # Second best
        sorted_bands = sorted(scores.items(), key=lambda x: -x[1])
        if len(sorted_bands) > 1:
            second = sorted_bands[1][0]
            draw.text((80, self.ROW2_Y), f"Also: {second}", font=self.font, fill=(100, 100, 100))

    def _draw_spot_row(self, img: Image.Image, draw: ImageDraw.ImageDraw, spot: Dict, y: int) -> None:
        callsign = spot.get("spotted", "???")[:8]
        band = spot.get("band", "")
        mode = self._get_mode(spot)
        flag = self._get_flag(callsign)
        is_pota = spot.get("source") == "pota"
        is_priority = self._is_priority_spot(spot)
        is_rare = self._is_rare_spot(spot)
        age = self._get_age(spot)
        
        # Color priority: Top 50 (red flash) > Rare (magenta) > POTA (green) > Normal
        if is_priority and int(time.time() * 2) % 2 == 0:
            call_color = self.priority_color
        elif is_rare and int(time.time() * 2) % 2 == 0:
            call_color = self.rare_color
        elif is_pota:
            call_color = self.pota_color
        else:
            call_color = (255, 255, 255)
        
        x = 1
        if is_priority:
            draw.text((x, y), "!", font=self.font, fill=self.priority_color)
            x += 6
        elif is_rare:
            draw.text((x, y), "*", font=self.font, fill=self.rare_color)
            x += 6
        elif is_pota:
            draw.text((x, y), "P", font=self.font, fill=self.pota_color)
            x += 6
        
        if flag:
            try:
                img.paste(flag, (x, y))
                x += self.SPOT_FLAG_WIDTH
            except:
                pass
        
        draw.text((x, y), callsign, font=self.font, fill=call_color)
        x += len(callsign) * self.SPOT_CHAR_WIDTH + self.SPOT_SPACING
        
        if self.show_frequency:
            try:
                freq_str = f"{float(spot.get('frequency', 0))/1000:.3f}"
                draw.text((x, y), freq_str, font=self.font, fill=(150, 150, 150))
                x += len(freq_str) * self.SPOT_CHAR_WIDTH + self.SPOT_SPACING
            except:
                pass
        
        if band:
            draw.text((x, y), band, font=self.font, fill=self._color_for_band(band))
            x += len(band) * self.SPOT_CHAR_WIDTH + self.SPOT_SPACING
        
        if mode and self.show_mode:
            draw.text((x, y), mode, font=self.font, fill=self._color_for_mode(mode))
        
        if age and self.show_age:
            age_color = (100, 255, 100) if age == "now" else (150, 150, 150)
            age_x = self.DISPLAY_WIDTH - len(age) * self.SPOT_CHAR_WIDTH - 2
            draw.text((age_x, y), age, font=self.font, fill=age_color)
    
    def _draw_spots_view(self, img: Image.Image, draw: ImageDraw.ImageDraw) -> None:
        draw.text((2, self.TITLE_Y), "DX SPOTS", font=self.font, fill=self.title_color)
        
        if not self.spots:
            draw.text((2, self.ROW1_Y), "No spots", font=self.font, fill=(128, 128, 128))
            return
        
        current_time = time.time()
        if current_time - self.last_page_change > self.page_duration:
            self.current_page = (self.current_page + 1) % max(1, (len(self.spots) + 1) // 2)
            self.last_page_change = current_time
        
        start = self.current_page * 2
        if start < len(self.spots):
            self._draw_spot_row(img, draw, self.spots[start], self.ROW1_Y)
        if start + 1 < len(self.spots):
            self._draw_spot_row(img, draw, self.spots[start + 1], self.ROW2_Y)
    
    def _draw_conditions_view(self, img: Image.Image, draw: ImageDraw.ImageDraw) -> None:
        draw.text((2, self.TITLE_Y), "SOLAR", font=self.font, fill=self.title_color)
        
        if not self.solar_data:
            draw.text((2, self.ROW1_Y), "Loading...", font=self.font, fill=(128, 128, 128))
            return
        
        sfi = self.solar_data.get('sfi', 'N/A')
        k_idx = self.solar_data.get('k_index', 'N/A')
        a_idx = self.solar_data.get('a_index', 'N/A')
        
        try:
            sfi_val = int(str(sfi).strip())
            sfi_color = (0, 255, 0) if sfi_val >= 150 else (255, 255, 0) if sfi_val >= 100 else (255, 100, 100)
        except:
            sfi_color = (200, 200, 200)
        
        try:
            k_val = int(str(k_idx).strip())
            k_color = (0, 255, 0) if k_val <= 2 else (255, 255, 0) if k_val <= 4 else (255, 0, 0)
        except:
            k_color = (200, 200, 200)
        
        draw.text((40, self.TITLE_Y), f"SFI:{sfi}", font=self.font, fill=sfi_color)
        draw.text((85, self.TITLE_Y), f"K:{k_idx}", font=self.font, fill=k_color)
        draw.text((110, self.TITLE_Y), f"A:{a_idx}", font=self.font, fill=(200, 200, 200))
        
        cond_80_40 = self.solar_data.get('band_80m_40m_day', 'N/A')
        cond_30_20 = self.solar_data.get('band_30m_20m_day', 'N/A')
        cond_17_15 = self.solar_data.get('band_17m_15m_day', 'N/A')
        cond_12_10 = self.solar_data.get('band_12m_10m_day', 'N/A')
        
        draw.text((2, self.ROW1_Y), "80-40:", font=self.font, fill=(150, 150, 150))
        draw.text((38, self.ROW1_Y), cond_80_40[:4], font=self.font, fill=self._color_for_condition(cond_80_40))
        draw.text((70, self.ROW1_Y), "30-20:", font=self.font, fill=(150, 150, 150))
        draw.text((106, self.ROW1_Y), cond_30_20[:4], font=self.font, fill=self._color_for_condition(cond_30_20))
        
        draw.text((2, self.ROW2_Y), "17-15:", font=self.font, fill=(150, 150, 150))
        draw.text((38, self.ROW2_Y), cond_17_15[:4], font=self.font, fill=self._color_for_condition(cond_17_15))
        draw.text((70, self.ROW2_Y), "12-10:", font=self.font, fill=(150, 150, 150))
        draw.text((106, self.ROW2_Y), cond_12_10[:4], font=self.font, fill=self._color_for_condition(cond_12_10))
    
    def _draw_hotspots_view(self, img: Image.Image, draw: ImageDraw.ImageDraw) -> None:
        draw.text((2, self.TITLE_Y), "HOT BANDS", font=self.font, fill=self.title_color)
        
        counts = self._get_band_counts()
        if not counts:
            draw.text((2, self.ROW1_Y), "No data", font=self.font, fill=(128, 128, 128))
            return
        
        sorted_bands = sorted(counts.items(), key=lambda x: -x[1])[:3]
        max_count = sorted_bands[0][1] if sorted_bands else 1
        
        y = self.HOTSPOT_START_Y
        for band, count in sorted_bands:
            color = self._color_for_band(band)
            draw.text((2, y), band, font=self.font, fill=color)
            bar_width = int((count / max_count) * self.HOTSPOT_BAR_MAX_WIDTH)
            draw.rectangle([self.HOTSPOT_BAR_X, y + 2, self.HOTSPOT_BAR_X + bar_width, y + 6], fill=color)
            draw.text((self.HOTSPOT_COUNT_X, y), str(count), font=self.font, fill=(200, 200, 200))
            y += self.HOTSPOT_ROW_HEIGHT
    
    def _draw_map_view(self, img: Image.Image, draw: ImageDraw.ImageDraw) -> None:
        img.paste(self.world_map, (0, 0))
        draw.text((2, 0), "DX MAP", font=self.font, fill=self.title_color)
        
        plotted = set()
        for spot in self.spots[:20]:
            callsign = spot.get("spotted", "")
            country = self._get_country_code(callsign)
            if country and country in self.COUNTRY_COORDS and country not in plotted:
                lat, lon = self.COUNTRY_COORDS[country]
                x, y = self._latlon_to_pixel(lat, lon)
                band = spot.get("band", "")
                color = self._color_for_band(band)
                draw.ellipse([x-1, y-1, x+1, y+1], fill=color)
                plotted.add(country)
        
        my_x, my_y = self._latlon_to_pixel(self.my_lat, self.my_lon)
        draw.rectangle([my_x-1, my_y-1, my_x+1, my_y+1], fill=(255, 255, 255))
    
    def _draw_grayline_view(self, img: Image.Image, draw: ImageDraw.ImageDraw) -> None:
        draw.text((2, self.TITLE_Y), "GRAY LINE", font=self.font, fill=self.title_color)
        
        now_utc = datetime.now(timezone.utc)
        now_local = datetime.now()  # Local time
        sunrise_utc, sunset_utc = self._calculate_sun_times(self.my_lat, self.my_lon, now_utc)
        
        # Calculate UTC offset in seconds for accurate conversion
        utc_offset_seconds = (now_local - now_utc.replace(tzinfo=None)).total_seconds()
        utc_offset = timedelta(seconds=utc_offset_seconds)
        
        # Convert sunrise/sunset to local time
        sunrise_local = sunrise_utc + utc_offset
        sunset_local = sunset_utc + utc_offset
        
        # Handle day wraparound
        if sunrise_local.hour >= 24:
            sunrise_local = sunrise_local - timedelta(hours=24)
        if sunset_local.hour >= 24:
            sunset_local = sunset_local - timedelta(hours=24)
        
        # Display times
        utc_str = now_utc.strftime("%H:%M")
        local_str = now_local.strftime("%H:%M")
        
        draw.text((90, self.TITLE_Y), f"UTC:{utc_str}", font=self.font, fill=(150, 150, 150))
        draw.text((145, self.TITLE_Y), f"L:{local_str}", font=self.font, fill=(100, 200, 100))
        
        # Sunrise/sunset with both UTC and local times (HH:MM format)
        sr_utc_str = sunrise_utc.strftime("%H:%M")
        sr_loc_str = f"{int(sunrise_local.hour):02d}:{int(sunrise_local.minute):02d}"
        ss_utc_str = sunset_utc.strftime("%H:%M")
        ss_loc_str = f"{int(sunset_local.hour):02d}:{int(sunset_local.minute):02d}"
        
        draw.text((2, self.ROW1_Y), f"Rise:{sr_utc_str}z {sr_loc_str}L", font=self.font, fill=(255, 200, 100))
        draw.text((2, self.ROW2_Y), f"Set: {ss_utc_str}z {ss_loc_str}L", font=self.font, fill=(255, 100, 100))
        
        hours_since_midnight = now_utc.hour + now_utc.minute / 60
        sr_hours = sunrise_utc.hour + sunrise_utc.minute / 60
        ss_hours = sunset_utc.hour + sunset_utc.minute / 60
        
        near_sunrise = abs(hours_since_midnight - sr_hours) < 0.5
        near_sunset = abs(hours_since_midnight - ss_hours) < 0.5
        
        if near_sunrise:
            status = "SUNRISE!"
            status_color = (255, 255, 0)
        elif near_sunset:
            status = "SUNSET!"
            status_color = (255, 150, 0)
        elif sr_hours < hours_since_midnight < ss_hours:
            status = "Day"
            status_color = (100, 200, 255)
        else:
            status = "Night"
            status_color = (100, 100, 200)
        
        draw.text((130, self.ROW1_Y), status, font=self.font, fill=status_color)
        
        gray_lon = self._get_gray_line_lon()
        region = "Asia/Pac" if gray_lon > 0 else "EU/Afr"
        draw.text((120, self.ROW2_Y), f"DX:{region}", font=self.font, fill=(0, 255, 0))
    
    # =========================================================================
    # MAIN DISPLAY METHODS
    # =========================================================================
    
    def get_vegas_content(self) -> Optional[List[Image.Image]]:
        """Return images - priority alert takes over if active"""
        self._check_test_priority()
        self._update_solar()
        
        # Check if priority alert should end - ONLY if call is no longer spotted
        # Skip if test_priority_spot is active (test controls its own lifecycle)
        # Skip if just DROPIN after timeout (let data refresh handle cleanup)
        if self.priority_active and not self.test_priority_spot:
            # Re-check if any top 50 still in current spots
            still_spotted = False
            for spot in self.all_spots:
                callsign = spot.get("spotted", "").upper()
                for prefix in self.TOP_50_WANTED:
                    if callsign.startswith(prefix):
                        still_spotted = True
                        break
                if still_spotted:
                    break
            
            if not still_spotted:
                self.priority_active = False
                self.priority_tier = None
                self.priority_spots = []
                self.logger.info("Priority alert ended - call no longer spotted")
        
        # If priority active, check timeout first
        if self.priority_active and self.priority_spots:
            alert_elapsed = time.time() - self.priority_start_time
            if alert_elapsed >= self._priority_max_duration:
                call = self.priority_callsign
                cooldown_secs = self._priority_cooldown_hours * 3600
                self._priority_cooldowns[call] = time.time() + cooldown_secs
                self.logger.info(f"Vegas: TAKEOVER timeout after {int(alert_elapsed)}s - {call} downgrading to DROPIN")
                self.priority_active = False
                self.priority_tier = "DROPIN"
                # Remove test file so _check_test_priority won't re-arm
                test_file = "/tmp/hamradio_test_priority.json"
                if os.path.exists(test_file):
                    try:
                        os.remove(test_file)
                        self.logger.info("Removed test priority file after timeout")
                    except Exception:
                        pass
                self.test_priority_spot = None
        
        # If still priority active after timeout check, return JACKPOT cards
        # TOP 10 TAKEOVER: return only jackpot celebration cards
        if self.priority_active and self.priority_spots and self.priority_tier == "TAKEOVER":
            images = self._generate_jackpot_cards()
            self.logger.info(f"Vegas: MEGA JACKPOT! TOP 10 TAKEOVER - {self.priority_callsign} - {len(images)} cards!")
            return images
        
        # Normal mode - return all views
        images = []
        for view in self.vegas_views:
            img = Image.new('RGB', (self.DISPLAY_WIDTH, self.DISPLAY_HEIGHT), (0, 0, 0))
            draw = ImageDraw.Draw(img)
            
            if view == "spots":
                self._draw_spots_view(img, draw)
            elif view == "conditions":
                self._draw_conditions_view(img, draw)
            elif view == "hotspots":
                self._draw_hotspots_view(img, draw)
            elif view == "map":
                self._draw_map_view(img, draw)
            elif view == "grayline":
                self._draw_grayline_view(img, draw)
            elif view == "continents":
                self._draw_continents_view(img, draw)
            elif view == "bandopen":
                self._draw_band_opening_view(img, draw)
            elif view == "rate":
                self._draw_qso_rate_view(img, draw)
            elif view == "clock":
                self._draw_clock_view(img, draw)
            elif view == "distance":
                self._draw_distance_view(img, draw)
            elif view == "stats":
                self._draw_stats_view(img, draw)
            elif view == "pota":
                self._draw_pota_view(img, draw)
            elif view == "spacewx":
                self._draw_space_weather_view(img, draw)
            elif view == "longpath":
                self._draw_longpath_view(img, draw)
            elif view == "beacon":
                self._draw_beacon_view(img, draw)
            elif view == "muf":
                self._draw_muf_view(img, draw)
            elif view == "bestband":
                self._draw_bestband_view(img, draw)
            else:
                self._draw_spots_view(img, draw)
            
            images.append(img)
        
        # DROPIN (Top 11-50): Insert priority card at front of rotation
        # Vegas will hold this card for priority_display_duration (STATIC mode)
        # then resume normal rotation
        if self.priority_tier == "DROPIN" and self.priority_spots:
            dropin_cards = self._generate_dropin_card()
            if dropin_cards:
                # Insert at position 0 so it shows first
                for i, card in enumerate(dropin_cards):
                    images.insert(i, card)
                self.logger.info(
                    f"Vegas: DROP-IN card for #{self.priority_spots[0].get('priority_rank', '?')} "
                    f"{self.priority_callsign} - will hold for "
                    f"{self.config.get('priority_display_duration', 15)}s")

        self.logger.info(f"Vegas: returning {len(images)} views")
        return images
    
    def _build_priority_ticker(self) -> None:
        """Pre-render clean scrolling ticker for priority DX alert."""
        if not self.priority_spots:
            self._pri_ticker_img = None
            return

        spot = self.priority_spots[0]
        callsign = spot.get("spotted", "???")
        band = spot.get("band", "20m")
        freq = spot.get("frequency", "14195")
        mode = spot.get("mode", "SSB")
        name = spot.get("priority_name", "RARE DX")
        rank = spot.get("priority_rank", 1)

        try:
            freq_str = f"{float(freq)/1000:.3f}"
        except Exception:
            freq_str = str(freq)

        CW = UX.CHAR_WIDTH
        band_color = self.BAND_COLORS.get(band, (255, 255, 0))
        mode_color = self._color_for_mode(mode)
        flag = self._get_flag(callsign)

        # Workability info
        w_score = spot.get("workability_score", 0)
        w_na = spot.get("workability_na_count", 0)
        na_text = f"NA:{w_na}" if w_na > 0 else "No NA"
        score_color = (0, 255, 0) if w_score >= 70 else (255, 255, 0)

        SEP = "  -  "
        sep_color = (80, 80, 80)

        segments = [
            ("flag", None),
            ("  ", (0, 0, 0)),
            (callsign, (255, 255, 255)),
            (SEP, sep_color),
            (f"#{rank} Most Wanted", (255, 80, 80)),
            (SEP, sep_color),
            (name, (255, 200, 0)),
            (SEP, sep_color),
            (freq_str, band_color),
            ("  ", (0, 0, 0)),
            (band, band_color),
            ("  ", (0, 0, 0)),
            (mode, mode_color),
            (SEP, sep_color),
            (na_text, (0, 200, 255)),
            ("  ", (0, 0, 0)),
            (f"{w_score}%", score_color),
            ("     ", (0, 0, 0)),
        ]

        flag_w = 14 if flag else 0
        total_w = flag_w
        for text, color in segments:
            if text == "flag":
                continue
            total_w += len(text) * CW

        if total_w < self.DISPLAY_WIDTH:
            total_w = self.DISPLAY_WIDTH + 50

        ticker_h = 21
        self._pri_ticker_img = Image.new('RGB', (total_w, ticker_h), (0, 0, 0))
        draw = ImageDraw.Draw(self._pri_ticker_img)

        x = 0
        for text, color in segments:
            if text == "flag":
                if flag:
                    self._pri_ticker_img.paste(flag, (x, 1))
                    x += flag_w
                continue
            draw.text((x, 0), text, font=self.font, fill=color)
            x += len(text) * CW

        self._pri_ticker_width = total_w
        self._pri_ticker_loop_width = total_w + self._pri_ticker_gap
        self._pri_ticker_key = callsign
        self._scroll_start_time = time.time()
        self.logger.info(f"Built priority ticker: {total_w}px for {callsign}")

    def _paste_pri_ticker(self, target: Image.Image, x_offset: int, y_offset: int) -> None:
        """Paste pre-rendered priority ticker at offset, clipping to display."""
        W = self.DISPLAY_WIDTH
        if self._pri_ticker_img is None:
            return
        src_left = max(0, -x_offset)
        src_right = min(self._pri_ticker_width, W - x_offset)
        if src_left >= src_right:
            return
        dst_x = max(0, x_offset)
        cropped = self._pri_ticker_img.crop((src_left, 0, src_right, self._pri_ticker_img.height))
        target.paste(cropped, (dst_x, y_offset))

    def display(self, display_mode: str = None, force_clear: bool = False) -> None:
        """Stateless one-frame-per-call renderer. 125 FPS during priority alerts."""
        now = time.time()

        # Throttle update() during 125 FPS
        if now - self._last_update_time >= self._update_throttle:
            self._update_solar()
            self._last_update_time = now

        width = self.display_manager.matrix.width
        height = self.display_manager.matrix.height
        img = Image.new('RGB', (width, height), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Priority alert: attention + scroll phases at 125 FPS
        if self.priority_active and self.priority_spots:
            # Check max duration timeout (5 min default)
            alert_elapsed = now - self.priority_start_time
            if alert_elapsed >= self._priority_max_duration:
                call = self.priority_callsign
                cooldown_secs = self._priority_cooldown_hours * 3600
                self._priority_cooldowns[call] = now + cooldown_secs
                self.logger.info(f"Priority alert timeout after {int(alert_elapsed)}s - "
                               f"{call} on cooldown for {self._priority_cooldown_hours}h")
                self.priority_active = False
                self.priority_tier = None
                self.priority_spots = []
                self.enable_scrolling = False
                self._priority_phase = "attn"
                self._attn_start = None
                self._scroll_start_time = None
                # Fall through to normal display below
            else:
                self.enable_scrolling = True

                # Init phase tracking
                if self._attn_start is None:
                    self._priority_phase = "attn"
                    self._attn_start = now

                # ---- ATTENTION PHASE ----
                if self._priority_phase == "attn":
                    elapsed = now - self._attn_start
                    if elapsed >= self._attn_duration:
                        self._priority_phase = "scroll"
                        self._scroll_start_time = now
                        self._build_priority_ticker()
                    else:
                        card_dur = self._attn_duration / 4.0
                        card_num = min(int(elapsed / card_dur), 3)
                        self._draw_priority_alert(img, draw, frame=card_num)
                        self.display_manager.image = img
                        self.display_manager.update_display()
                        return

                # ---- SCROLL PHASE ----
                if self._priority_phase == "scroll":
                    if self._pri_ticker_img is None:
                        self._build_priority_ticker()

                    elapsed = now - self._scroll_start_time

                    # Instant cut: when text scrolls off → back to attention
                    right_edge = int(self._pri_ticker_width - elapsed * self._pri_scroll_speed)
                    if right_edge < 0:
                        self._priority_phase = "attn"
                        self._attn_start = now
                        self._scroll_start_time = None
                        self._pri_ticker_key = None  # Force rebuild with fresh times
                        self._draw_priority_alert(img, draw, frame=0)
                        self.display_manager.image = img
                        self.display_manager.update_display()
                        return

                    # Static title row with flashing
                    scheme = int(now * 2) % 4
                    if scheme == 0:
                        title_color = (255, 255, 0)
                        border_color = (255, 0, 0)
                    elif scheme == 1:
                        title_color = (255, 0, 0)
                        border_color = (255, 255, 0)
                    elif scheme == 2:
                        title_color = (0, 255, 0)
                        border_color = (255, 255, 255)
                    else:
                        title_color = (255, 255, 255)
                        border_color = (0, 255, 0)

                    draw.rectangle([0, 0, self.DISPLAY_WIDTH - 1, self.DISPLAY_HEIGHT - 1], outline=border_color)
                    draw.text((6, 1), "TOP 50 DX!", font=self.font, fill=title_color)
                    spot = self.priority_spots[0]
                    rank = spot.get("priority_rank", 0)
                    draw.text((120, 1), f"#{rank}", font=self.font, fill=title_color)

                    # Scrolling ticker below title
                    raw_x = elapsed * self._pri_scroll_speed
                    scroll_x = int(-raw_x)
                    self._paste_pri_ticker(img, scroll_x, self.ROW1_Y)
                    second_x = scroll_x + self._pri_ticker_loop_width
                    if second_x < self.DISPLAY_WIDTH:
                        self._paste_pri_ticker(img, second_x, self.ROW1_Y)

                self.display_manager.image = img
                self.display_manager.update_display()
                return

        # DROPIN (Top 11-50): Render drop-in card, Vegas STATIC holds for 15s
        if getattr(self, 'priority_tier', None) == "DROPIN" and self.priority_spots:
            self.enable_scrolling = False
            cards = self._generate_dropin_card()
            if cards:
                # Alternate between the 2 cards every 5 seconds
                card_idx = int(time.time() / 5) % len(cards)
                self.display_manager.image = cards[card_idx]
                self.display_manager.update_display()
                return

        # No priority alert - disable scrolling, normal display
        self.enable_scrolling = False
        self._priority_phase = "attn"
        self._attn_start = None
        self._scroll_start_time = None

        if self.display_mode == "rotate":
            view = self.vegas_views[self.vegas_view_index % len(self.vegas_views)]
            self.vegas_view_index += 1
            if view == "spots":
                self._draw_spots_view(img, draw)
            elif view == "conditions":
                self._draw_conditions_view(img, draw)
            elif view == "hotspots":
                self._draw_hotspots_view(img, draw)
            elif view == "map":
                self._draw_map_view(img, draw)
            elif view == "grayline":
                self._draw_grayline_view(img, draw)
            else:
                self._draw_spots_view(img, draw)
        else:
            self._draw_spots_view(img, draw)

        self.display_manager.image = img
        self.display_manager.update_display()
    
    def get_vegas_display_mode(self):
        """Always FIXED_SEGMENT - priority alerts are handled through
        get_vegas_content() which returns jackpot cards when active.
        STATIC mode doesn't work because Vegas calls display() not get_vegas_content().
        """
        try:
            from src.plugin_system.base_plugin import VegasDisplayMode
            return VegasDisplayMode.FIXED_SEGMENT
        except ImportError:
            return None

    def get_display_duration(self) -> int:
        """Return display duration based on priority tier.
        TAKEOVER (Top 10): priority_max_duration for full celebration
        DROPIN (Top 11-50): priority_display_duration for quick hold
        Normal: display_duration
        """
        tier = getattr(self, 'priority_tier', None)
        if tier == "TAKEOVER" and getattr(self, 'priority_active', False):
            duration = self.config.get("priority_max_duration", 300)
            self.logger.debug("TAKEOVER active - duration: %ds", duration)
            return duration
        elif tier == "DROPIN":
            duration = self.config.get("priority_display_duration", 15)
            self.logger.debug("DROPIN active - hold for %ds", duration)
            return duration
        return self.config.get("display_duration", 30)
    
    def cleanup(self) -> None:
        self.spots = []
        self.all_spots = []
        self.priority_spots = []
        self.rare_spots = []
        self.solar_data = {}
        self.enable_scrolling = False
        self._pri_ticker_img = None
        self._pri_ticker_key = None
        self._attn_start = None
        self._scroll_start_time = None
        self._priority_cooldowns = {}
        self.priority_tier = None


    def _check_test_priority(self) -> None:
        """Check for test priority alert file - clears when file removed"""
        import json
        test_file = "/tmp/hamradio_test_priority.json"
        
        # If test file is gone, clear alert
        if self.test_priority_spot and not os.path.exists(test_file):
            self.test_priority_spot = None
            self.priority_tier = None
            self.priority_spots = []
            self.priority_active = False
            self.logger.info("Test priority alert cleared!")
            return
        
        # If test file exists, activate alert (or update if callsign changed)
        if os.path.exists(test_file):
            try:
                with open(test_file, 'r') as f:
                    data = json.load(f)
                if data.get("test_priority"):
                    new_call = data.get("callsign", "P5DX")
                    # Only activate if not already running this exact test
                    if not self.test_priority_spot or self.test_priority_spot.get("spotted") != new_call:
                        self.test_priority_alert(
                            callsign=new_call,
                            rank=data.get("rank", 1),
                            name=data.get("name", "North Korea"),
                            band=data.get("band", "20m"),
                            freq=data.get("freq", "14195000"),
                            mode=data.get("mode", "SSB")
                        )
            except Exception as e:
                self.logger.error(f"Test priority check failed: {e}")

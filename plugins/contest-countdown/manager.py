"""
Contest Countdown Plugin for LEDMatrix
Loads contest calendar from JSON file for easy updates.
Shows countdown timers for upcoming contests, ON THE AIR during active contests.

v2.2.0: Active contests get attention phase (dramatic ON THE AIR strobe) + 
        smooth scrolling ticker with contest details at 125 FPS.
        Upcoming contests remain static countdown cards.
"""
import logging
import json
import time
import math
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

from src.plugin_system.base_plugin import BasePlugin
from ux_constants import UX, load_fonts, get_mode_color, get_sponsor_color

logger = logging.getLogger(__name__)
__version__ = "2.2.0"
class ContestCountdownPlugin(BasePlugin):
    """Contest countdown with attention + scroll phases for active contests"""

    DISPLAY_WIDTH = UX.WIDTH
    DISPLAY_HEIGHT = UX.HEIGHT

    # Colors (from shared UX constants)
    COLOR_TITLE = UX.TITLE_COLOR
    COLOR_CONTEST_NAME = (0, 255, 255)
    COLOR_ACTIVE = UX.ALERT_GREEN
    COLOR_DIM = UX.TEXT_DIM
    COLOR_EU_STAR = UX.EU_STAR_COLOR

    MODE_COLORS = UX.MODE_COLORS
    SPONSOR_COLORS = UX.SPONSOR_COLORS

    def __init__(self, plugin_id, config, display_manager, cache_manager, plugin_manager):
        super().__init__(plugin_id, config, display_manager, cache_manager, plugin_manager)

        self.countdown_days = config.get("countdown_days", 7)
        self.show_always = config.get("show_always", True)
        self.show_eu = config.get("show_eu", True)

        self.contests = []
        self._load_fonts()
        self._load_contests()

        # =====================================================================
        # SMOOTH SCROLLING STATE (v2.2.0)
        # =====================================================================
        # Controller checks this for 125 FPS
        self.enable_scrolling = False

        # Phase state (active contests only)
        self._phase = "attn"             # "attn" or "scroll"
        self._attn_start = None          # When attention phase began
        self._attn_duration = config.get("attention_duration", 8.0)  # 4 cards x 2s
        self._scroll_start = None        # When scroll phase began
        self._scroll_speed = config.get("scroll_speed", 45)  # px/sec

        # Pre-rendered ticker for active contest
        self._ticker_img = None
        self._ticker_width = 0
        self._ticker_gap = 80
        self._ticker_loop_width = 0
        self._ticker_contest_key = None  # Cache key

        # Throttle update() during 125 FPS
        self._last_update_time = 0
        self._update_throttle = 2.0

        logger.info(f"Contest Countdown v{__version__} init, {len(self.contests)} contests loaded")

    def _load_fonts(self):
        self.font, self.font_large = load_fonts(__file__)

    def _load_contests(self):
        """Load contests from perpetual calendar generator"""
        self.contests = []
        try:
            from contest_calendar import get_upcoming_contests
            data = get_upcoming_contests(days_ahead=120)
            for c in data:
                try:
                    start = datetime.fromisoformat(c["start"].replace("Z", "+00:00"))
                    end = datetime.fromisoformat(c["end"].replace("Z", "+00:00"))
                    self.contests.append({
                        "name": c["name"],
                        "short": c.get("short", c["name"][:12]),
                        "start": start,
                        "end": end,
                        "mode": c.get("mode", "ALL"),
                        "sponsor": c.get("sponsor", "OTHER"),
                    })
                except Exception as e:
                    logger.warning(f"Skipping contest entry: {e}")
            self.contests.sort(key=lambda x: x["start"])
            logger.info(f"Loaded {len(self.contests)} contests from perpetual calendar")
        except Exception as e:
            logger.error(f"Failed to generate contest calendar: {e}")

        except Exception as e:
            logger.error(f"Failed to load contest calendar: {e}")

    def _get_active_and_upcoming(self):
        """Get active contests and upcoming within countdown window"""
        now = datetime.now(timezone.utc)
        window = timedelta(days=self.countdown_days)

        active = []
        upcoming = []

        for c in self.contests:
            if c["start"] <= now <= c["end"]:
                active.append(c)
            elif now < c["start"] <= (now + window):
                upcoming.append(c)
            elif now < c["start"] and not upcoming and self.show_always:
                upcoming.append(c)

        return active, upcoming

    def _format_countdown(self, delta):
        total = int(delta.total_seconds())
        if total < 0:
            return "NOW!"
        days = total // 86400
        hours = (total % 86400) // 3600
        mins = (total % 3600) // 60
        if days > 0:
            return f"{days}d {hours}h"
        elif hours > 0:
            return f"{hours}h {mins}m"
        else:
            return f"{mins}m"

    def _countdown_color(self, delta):
        days = delta.total_seconds() / 86400
        if days > 3:
            return UX.TEXT_SECONDARY
        elif days > 1:
            return UX.ALERT_YELLOW
        elif days > 0.25:
            return UX.ALERT_ORANGE
        else:
            return UX.ALERT_RED

    # =========================================================================
    # ACTIVE CONTEST TICKER (v2.2.0)
    # =========================================================================

    def _contest_key(self, contest) -> str:
        """Cache key for a contest."""
        return f"{contest['short']}_{contest['start'].isoformat()}"

    def _build_active_ticker(self, contest) -> None:
        """Pre-render scrolling ticker image for an active contest."""
        now = datetime.now(timezone.utc)
        name = contest["short"]
        mode = contest["mode"]
        sponsor = contest["sponsor"]
        remaining = contest["end"] - now
        elapsed = (now - contest["start"]).total_seconds()
        total = (contest["end"] - contest["start"]).total_seconds()
        pct = int((elapsed / total) * 100) if total > 0 else 0
        hours_left = int(remaining.total_seconds() // 3600)
        mins_left = int((remaining.total_seconds() % 3600) // 60)

        # Build ticker text segments with colors
        CW = UX.CHAR_WIDTH
        SP = UX.SPACING

        segments = [
            ("ON THE AIR", (0, 255, 0)),
            ("  \u2022  ", UX.TEXT_DIM),
            (name, self.COLOR_CONTEST_NAME),
            ("  ", (0, 0, 0)),
            (mode, self.MODE_COLORS.get(mode, (255, 255, 255))),
            ("  ", (0, 0, 0)),
            (sponsor, self.SPONSOR_COLORS.get(sponsor, UX.TEXT_SECONDARY)),
            ("  \u2022  ", UX.TEXT_DIM),
            (f"{hours_left}h{mins_left:02d}m left", UX.ALERT_RED),
            ("  ", (0, 0, 0)),
            (f"{pct}% complete", (0, 200, 0)),
            ("  \u2022  ", UX.TEXT_DIM),
            (f"{contest['name']}", (200, 200, 200)),
            ("   ", (0, 0, 0)),
        ]

        # Calculate total width
        total_w = sum(len(text) * CW for text, _ in segments)
        if total_w < self.DISPLAY_WIDTH:
            total_w = self.DISPLAY_WIDTH + 50  # Ensure scrolling happens

        # Render
        ticker_h = 21  # rows 1-2 height
        self._ticker_img = Image.new('RGB', (total_w, ticker_h), (0, 0, 0))
        draw = ImageDraw.Draw(self._ticker_img)

        x = 0
        for text, color in segments:
            draw.text((x, 0), text, font=self.font, fill=color)
            x += len(text) * CW

        self._ticker_width = total_w
        self._ticker_loop_width = total_w + self._ticker_gap
        self._ticker_contest_key = self._contest_key(contest)

        logger.debug(f"Built active contest ticker: {total_w}px wide")

    def _draw_attn_card(self, img, draw, contest, card_num, now):
        """Draw dramatic ON THE AIR attention card."""
        name = contest["short"]
        mode = contest["mode"]
        sponsor = contest["sponsor"]
        remaining = contest["end"] - now
        elapsed = (now - contest["start"]).total_seconds()
        total = (contest["end"] - contest["start"]).total_seconds()
        pct = elapsed / total if total > 0 else 0
        hours_left = int(remaining.total_seconds() // 3600)
        mins_left = int((remaining.total_seconds() % 3600) // 60)

        mc = self.MODE_COLORS.get(mode, (255, 255, 255))
        sc = self.SPONSOR_COLORS.get(sponsor, UX.TEXT_SECONDARY)

        if card_num % 4 == 0:
            # Bright green flash - ON THE AIR
            draw.rectangle([0, 0, self.DISPLAY_WIDTH, self.DISPLAY_HEIGHT], fill=(0, 40, 0))
            draw.rectangle([0, 0, self.DISPLAY_WIDTH - 1, self.DISPLAY_HEIGHT - 1], outline=(0, 255, 0))
            draw.rectangle([2, 2, self.DISPLAY_WIDTH - 3, self.DISPLAY_HEIGHT - 3], outline=(0, 255, 0))
            cx = max(4, (self.DISPLAY_WIDTH - len("ON THE AIR") * UX.CHAR_WIDTH) // 2)
            draw.text((cx, 2), "ON THE AIR", font=self.font, fill=(0, 255, 0))
            draw.text((6, 12), name, font=self.font, fill=self.COLOR_CONTEST_NAME)
            draw.text((100, 12), mode, font=self.font, fill=mc)
            draw.text((6, 22), f"{hours_left}h{mins_left:02d}m", font=self.font, fill=UX.ALERT_RED)
            draw.text((70, 22), f"{int(pct*100)}%", font=self.font, fill=(0, 200, 0))

        elif card_num % 4 == 1:
            # White flash - contest name focus
            draw.rectangle([0, 0, self.DISPLAY_WIDTH, self.DISPLAY_HEIGHT], fill=(30, 30, 30))
            draw.rectangle([0, 0, self.DISPLAY_WIDTH - 1, self.DISPLAY_HEIGHT - 1], outline=(255, 255, 255))
            draw.text((6, 2), ">> ON THE AIR <<", font=self.font, fill=(0, 255, 0))
            cx = max(4, (self.DISPLAY_WIDTH - len(name) * UX.CHAR_WIDTH) // 2)
            draw.text((cx, 12), name, font=self.font, fill=self.COLOR_CONTEST_NAME)
            draw.text((6, 22), sponsor, font=self.font, fill=sc)
            draw.text((80, 22), mode, font=self.font, fill=mc)

        elif card_num % 4 == 2:
            # Green progress bar focus
            pulse = abs(math.sin(time.time() * 2)) * 0.4 + 0.6
            green = int(255 * pulse)
            draw.text((2, UX.TITLE_Y), "ON THE AIR", font=self.font, fill=(0, green, 0))
            mode_x = UX.WIDTH - UX.MARGIN_RIGHT - len(mode) * UX.CHAR_WIDTH
            draw.text((mode_x, UX.TITLE_Y), mode, font=self.font, fill=mc)
            draw.text((2, UX.ROW1_Y), name, font=self.font, fill=UX.TITLE_COLOR)
            draw.text((100, UX.ROW1_Y), sponsor, font=self.font, fill=sc)
            # Progress bar
            bar_x, bar_y, bar_w, bar_h = 2, 21, 140, 5
            draw.rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], fill=(40, 40, 40))
            fill_w = int(bar_w * pct)
            if fill_w > 0:
                draw.rectangle([bar_x, bar_y, bar_x + fill_w, bar_y + bar_h], fill=(0, 200, 0))
            time_str = f"{hours_left}h{mins_left:02d}m"
            draw.text((2, 27), time_str, font=self.font, fill=UX.ALERT_RED)
            draw.text((60, 27), f"{int(pct*100)}%", font=self.font, fill=(0, green, 0))

        else:
            # Alternating arrows
            draw.rectangle([0, 0, self.DISPLAY_WIDTH - 1, self.DISPLAY_HEIGHT - 1], outline=(0, 200, 0))
            draw.text((6, 2), ">>", font=self.font, fill=(0, 255, 0))
            draw.text((170, 2), "<<", font=self.font, fill=(0, 255, 0))
            cx = max(30, (self.DISPLAY_WIDTH - len("CONTEST ACTIVE") * UX.CHAR_WIDTH) // 2)
            draw.text((cx, 2), "CONTEST ACTIVE", font=self.font, fill=(0, 255, 0))
            draw.text((6, 12), name, font=self.font, fill=self.COLOR_CONTEST_NAME)
            draw.text((6, 22), f"{mode} {sponsor} {hours_left}h{mins_left:02d}m", font=self.font, fill=UX.TEXT_SECONDARY)

    def _paste_ticker(self, target, x_offset, y_offset):
        """Paste pre-rendered ticker at offset, clipping to display bounds."""
        W = self.DISPLAY_WIDTH
        if self._ticker_img is None:
            return
        src_left = max(0, -x_offset)
        src_right = min(self._ticker_width, W - x_offset)
        if src_left >= src_right:
            return
        dst_x = max(0, x_offset)
        cropped = self._ticker_img.crop((src_left, 0, src_right, self._ticker_img.height))
        target.paste(cropped, (dst_x, y_offset))

    # =========================================================================
    # DISPLAY - STATELESS FRAME RENDERER
    # =========================================================================

    def display(self, display_mode=None, force_clear=False):
        """Render ONE frame per call. No loops, no sleep."""
        now_time = time.time()

        # Throttle update()
        if now_time - self._last_update_time >= self._update_throttle:
            self._load_contests()
            self._last_update_time = now_time

        active, upcoming = self._get_active_and_upcoming()

        if active:
            # Active contest: attention + scroll phases at 125 FPS
            self.enable_scrolling = True
            contest = active[0]
            now = datetime.now(timezone.utc)

            img = Image.new("RGB", (self.DISPLAY_WIDTH, self.DISPLAY_HEIGHT), (0, 0, 0))
            draw = ImageDraw.Draw(img)

            # Init phase tracking
            if self._attn_start is None:
                self._phase = "attn"
                self._attn_start = now_time

            # ---- ATTENTION PHASE ----
            if self._phase == "attn":
                elapsed = now_time - self._attn_start
                if elapsed >= self._attn_duration:
                    # Transition to scroll
                    self._phase = "scroll"
                    self._scroll_start = now_time
                    # Build/rebuild ticker
                    self._build_active_ticker(contest)
                else:
                    card_dur = self._attn_duration / 4.0
                    card_num = min(int(elapsed / card_dur), 3)
                    self._draw_attn_card(img, draw, contest, card_num, now)
                    self.display_manager.image = img
                    self.display_manager.update_display()
                    return True

            # ---- SCROLL PHASE ----
            if self._phase == "scroll":
                if self._ticker_img is None:
                    self._build_active_ticker(contest)

                elapsed = now_time - self._scroll_start

                # Check if text has scrolled off screen → back to attention
                right_edge = int(self._ticker_width - elapsed * self._scroll_speed)
                if right_edge < 0:
                    self._phase = "attn"
                    self._attn_start = now_time
                    self._scroll_start = None
                    # Rebuild ticker with updated times
                    self._ticker_contest_key = None
                    self._draw_attn_card(img, draw, contest, 0, now)
                    self.display_manager.image = img
                    self.display_manager.update_display()
                    return True

                # Static title row
                pulse = abs(math.sin(now_time * 2)) * 0.4 + 0.6
                green = int(255 * pulse)
                draw.text((2, UX.TITLE_Y), "ON THE AIR", font=self.font, fill=(0, green, 0))
                mc = self.MODE_COLORS.get(contest["mode"], (255, 255, 255))
                mode_x = UX.WIDTH - UX.MARGIN_RIGHT - len(contest["mode"]) * UX.CHAR_WIDTH
                draw.text((mode_x, UX.TITLE_Y), contest["mode"], font=self.font, fill=mc)

                # Scrolling ticker
                raw_x = elapsed * self._scroll_speed
                scroll_x = int(-raw_x)
                self._paste_ticker(img, scroll_x, UX.ROW1_Y)
                # Trailing copy
                second_x = scroll_x + self._ticker_loop_width
                if second_x < self.DISPLAY_WIDTH:
                    self._paste_ticker(img, second_x, UX.ROW1_Y)

            self.display_manager.image = img
            self.display_manager.update_display()
            return True

        elif upcoming:
            # Upcoming contests: static card, no scrolling needed
            self.enable_scrolling = False
            self._phase = "attn"
            self._attn_start = None
            self._scroll_start = None

            img = self._draw_countdown_card(upcoming)
            self.display_manager.image = img
            self.display_manager.update_display()
            return True

        else:
            # Nothing to show
            self.enable_scrolling = False
            return False

    # =========================================================================
    # STATIC CARDS (for Vegas mode and upcoming countdown)
    # =========================================================================

    def _draw_active_card(self, contest):
        """Draw static ON THE AIR card (used by Vegas mode)."""
        img = Image.new("RGB", (self.DISPLAY_WIDTH, self.DISPLAY_HEIGHT), (0, 0, 0))
        draw = ImageDraw.Draw(img)
        now = datetime.now(timezone.utc)

        name = contest["short"]
        mode = contest["mode"]
        sponsor = contest["sponsor"]
        start = contest["start"]
        end = contest["end"]

        elapsed = (now - start).total_seconds()
        total = (end - start).total_seconds()
        remaining = end - now
        pct = elapsed / total if total > 0 else 0
        hours_left = int(remaining.total_seconds() // 3600)
        mins_left = int((remaining.total_seconds() % 3600) // 60)

        pulse = abs(math.sin(time.time() * 2)) * 0.4 + 0.6
        green = int(255 * pulse)

        draw.text((2, UX.TITLE_Y), "ON THE AIR", font=self.font, fill=(0, green, 0))
        mc = self.MODE_COLORS.get(mode, (255, 255, 255))
        mode_x = UX.WIDTH - UX.MARGIN_RIGHT - len(mode) * UX.CHAR_WIDTH
        draw.text((mode_x, UX.TITLE_Y), mode, font=self.font, fill=mc)
        draw.text((2, UX.ROW1_Y), name, font=self.font, fill=UX.TITLE_COLOR)
        sc = self.SPONSOR_COLORS.get(sponsor, UX.TEXT_SECONDARY)
        draw.text((100, UX.ROW1_Y), sponsor, font=self.font, fill=sc)
        bar_x, bar_y, bar_w, bar_h = 2, 21, 140, 5
        draw.rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], fill=(40, 40, 40))
        fill_w = int(bar_w * pct)
        if fill_w > 0:
            draw.rectangle([bar_x, bar_y, bar_x + fill_w, bar_y + bar_h], fill=(0, 200, 0))
        time_str = f"{hours_left}h{mins_left:02d}m"
        draw.text((2, 27), time_str, font=self.font, fill=UX.ALERT_RED)
        draw.text((60, 27), f"{int(pct * 100)}%", font=self.font, fill=(0, green, 0))

        return img

    def _draw_countdown_card(self, upcoming_list):
        """Draw countdown card for upcoming contests"""
        img = Image.new("RGB", (self.DISPLAY_WIDTH, self.DISPLAY_HEIGHT), (0, 0, 0))
        draw = ImageDraw.Draw(img)
        now = datetime.now(timezone.utc)

        draw.text((UX.MARGIN_LEFT, UX.TITLE_Y), "CONTEST COUNTDOWN", font=self.font, fill=self.COLOR_TITLE)

        y = 9
        for i, contest in enumerate(upcoming_list[:3]):
            if y > 26:
                break

            name = contest["short"]
            mode = contest["mode"]
            sponsor = contest["sponsor"]
            delta = contest["start"] - now

            cd_str = self._format_countdown(delta)
            cd_color = self._countdown_color(delta)
            mc = self.MODE_COLORS.get(mode, (255, 255, 255))

            name_x = 2
            if sponsor == "EU" and self.show_eu:
                draw.rectangle([1, y + 2, 3, y + 4], fill=self.COLOR_EU_STAR)
                name_x = 5

            draw.text((name_x, y), name, font=self.font, fill=self.COLOR_CONTEST_NAME)
            draw.text((100, y), mode, font=self.font, fill=mc)
            draw.text((130, y), cd_str, font=self.font, fill=cd_color)

            y += 8

        return img

    def _draw_next_contests_card(self, upcoming_list):
        """Draw a card showing next upcoming contests (for show_always mode)"""
        img = Image.new("RGB", (self.DISPLAY_WIDTH, self.DISPLAY_HEIGHT), (0, 0, 0))
        draw = ImageDraw.Draw(img)
        now = datetime.now(timezone.utc)

        draw.text((UX.MARGIN_LEFT, UX.TITLE_Y), "NEXT CONTESTS", font=self.font, fill=self.COLOR_TITLE)

        y = 9
        for contest in upcoming_list[:3]:
            if y > 26:
                break

            name = contest["short"]
            mode = contest["mode"]
            sponsor = contest["sponsor"]
            date_str = contest["start"].strftime("%b %d")
            delta = contest["start"] - now

            mc = self.MODE_COLORS.get(mode, (255, 255, 255))
            cd_str = self._format_countdown(delta)

            name_x = 2
            if sponsor == "EU" and self.show_eu:
                draw.rectangle([1, y + 2, 3, y + 4], fill=self.COLOR_EU_STAR)
                name_x = 5

            draw.text((name_x, y), name, font=self.font, fill=self.COLOR_CONTEST_NAME)
            draw.text((90, y), date_str, font=self.font, fill=UX.TEXT_SECONDARY)
            draw.text((140, y), cd_str, font=self.font, fill=UX.TEXT_DIM)

            y += 8

        return img

    # =========================================================================
    # BasePlugin interface
    # =========================================================================

    def update(self) -> bool:
        """Reload contest data periodically"""
        self._load_contests()
        return True

    def get_vegas_content(self) -> Optional[List[Image.Image]]:
        """Return images for Vegas mode rotation"""
        active, upcoming = self._get_active_and_upcoming()
        images = []

        if active:
            images.append(self._draw_active_card(active[0]))
        elif upcoming:
            now = datetime.now(timezone.utc)
            window = timedelta(days=self.countdown_days)

            in_window = [c for c in upcoming if c["start"] <= now + window]

            if in_window:
                images.append(self._draw_countdown_card(in_window))
            elif self.show_always and upcoming:
                images.append(self._draw_next_contests_card(upcoming))

        if not images:
            return None

        return images

    def get_vegas_content_type(self) -> str:
        return 'static'

    def get_display_duration(self) -> int:
        return self.config.get("display_duration", 8)

    def cleanup(self) -> None:
        self.contests = []
        self.enable_scrolling = False
        self._ticker_img = None
        self._attn_start = None
        self._scroll_start = None

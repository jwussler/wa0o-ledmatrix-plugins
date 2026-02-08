"""
LEDMatrix Shared UX Constants
==============================
Single source of truth for layout, colors, fonts, and drawing helpers
across all custom plugins (hamradio-spots, wavelog-qsos, contest-countdown,
weather-alerts).

Place this file at:  ~/LEDMatrix/plugin-repos/ux_constants.py
Then import from any plugin:
    from ux_constants import UX, draw_title_row, draw_text_right, load_fonts

Version: 1.0.0
"""

from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
from typing import Tuple, Optional


# =============================================================================
# DISPLAY GEOMETRY
# =============================================================================
class UX:
    """All shared layout constants for 192x32 LED matrix with 4x6 font."""

    # Display dimensions
    WIDTH = 192
    HEIGHT = 32

    # Standard 3-row grid (4x6 font at size 8 = ~8px tall, rows spaced 11px)
    TITLE_Y = 0      # Row 0: title/header
    ROW1_Y = 11      # Row 1: primary data
    ROW2_Y = 22      # Row 2: secondary data

    # Left margin for text
    MARGIN_LEFT = 2
    MARGIN_RIGHT = 2

    # Character metrics for 4x6-font.ttf at size 8
    CHAR_WIDTH = 5    # pixels per character
    SPACING = 6       # pixels between logical field groups
    CHAR_ADVANCE = 6  # CHAR_WIDTH + 1px kerning (for centering/right-align math)

    # Framed card layout (inside 2px border + 4px margin)
    BORDER_PX = 2
    FRAME_MARGIN = 4
    FRAME_INNER_WIDTH = WIDTH - 2 * BORDER_PX - 2 * FRAME_MARGIN  # 180px
    CHARS_PER_LINE = 30  # FRAME_INNER_WIDTH // CHAR_ADVANCE

    # =========================================================================
    # COLOR PALETTE - Shared across all plugins
    # =========================================================================

    # --- Title colors ---
    TITLE_COLOR = (255, 200, 0)         # Warm yellow - standard header
    TITLE_COLOR_ALT = (0, 180, 255)     # Cyan-blue - alternate header

    # --- Text colors ---
    TEXT_PRIMARY = (255, 255, 255)       # White
    TEXT_SECONDARY = (200, 200, 200)     # Light gray
    TEXT_DIM = (100, 100, 100)           # Dim gray (labels, inactive)
    TEXT_MUTED = (80, 80, 80)           # Very dim (empty states)

    # --- Callsign / identity ---
    CALL_COLOR = (255, 255, 0)          # Yellow for callsigns

    # --- Frequency / band ---
    FREQ_COLOR = (0, 255, 100)          # Green for frequencies

    # --- Time / age ---
    TIME_COLOR = (180, 180, 180)        # Gray for timestamps

    # --- Alert levels ---
    ALERT_RED = (255, 50, 50)           # Critical / imminent
    ALERT_ORANGE = (255, 165, 0)        # Warning / soon
    ALERT_YELLOW = (255, 255, 0)        # Caution
    ALERT_GREEN = (0, 255, 0)           # Active / good

    # --- Band colors (consistent across all plugins) ---
    BAND_COLORS = {
        "160m": (128, 0, 128),    # Purple
        "80m":  (0, 0, 255),      # Blue
        "60m":  (0, 128, 128),    # Teal
        "40m":  (0, 255, 0),      # Green
        "30m":  (128, 255, 0),    # Yellow-green
        "20m":  (255, 255, 0),    # Yellow
        "17m":  (255, 165, 0),    # Orange
        "15m":  (255, 100, 0),    # Dark orange
        "12m":  (255, 50, 0),     # Red-orange
        "10m":  (255, 0, 0),      # Red
        "6m":   (255, 0, 128),    # Pink
        "2m":   (200, 200, 200),  # White-gray
        "70cm": (128, 128, 255),  # Light blue
    }

    # --- Mode colors (consistent across all plugins) ---
    MODE_COLORS = {
        # Voice
        "SSB":  (100, 255, 100),  # Green
        "USB":  (100, 255, 100),
        "LSB":  (100, 255, 100),
        "AM":   (100, 255, 100),
        "FM":   (100, 255, 100),
        # CW
        "CW":   (255, 100, 100),  # Red
        # Digital
        "FT8":  (0, 255, 255),    # Cyan
        "FT4":  (0, 200, 200),    # Dark cyan
        "JS8":  (0, 200, 200),
        "RTTY": (255, 150, 0),    # Orange
        "PSK":  (200, 100, 255),  # Purple
        "PSK31": (200, 100, 255),
        "JT65": (0, 180, 180),
        "JT9":  (0, 180, 180),
        "MFSK": (0, 180, 180),
        "OLIVIA": (0, 180, 180),
        "VARA": (0, 180, 180),
        "WSPR": (0, 180, 180),
        "DIGI": (0, 180, 180),    # Generic digital
        # Contest
        "ALL":  (255, 255, 255),  # White
        "EVENT": (255, 0, 255),   # Magenta
    }

    # --- Sponsor colors (contest plugin) ---
    SPONSOR_COLORS = {
        "ARRL":  (0, 100, 255),
        "CQ":    (255, 165, 0),
        "NCJ":   (0, 200, 100),
        "DARC":  (200, 200, 0),
        "REF":   (100, 100, 255),
        "EDR":   (200, 100, 0),
        "RSGB":  (150, 0, 0),
    }

    # --- Special colors ---
    POTA_COLOR = (0, 255, 128)          # POTA/SOTA green
    RARE_COLOR = (255, 0, 255)          # Magenta for rare DX
    PRIORITY_COLOR = (255, 0, 0)        # Red for top-priority
    EU_STAR_COLOR = (255, 204, 0)       # EU contest indicator


# =============================================================================
# FONT LOADING
# =============================================================================

def load_fonts(plugin_file: str = None) -> Tuple[ImageFont.FreeTypeFont, ImageFont.FreeTypeFont]:
    """
    Load standard fonts. Returns (font_regular, font_large).

    Args:
        plugin_file: __file__ from the calling plugin, used to locate fonts
                     relative to the plugin-repos directory.
    """
    font_paths = []

    # Try relative to plugin file first
    if plugin_file:
        p = Path(plugin_file).parent.parent.parent / 'assets' / 'fonts' / '4x6-font.ttf'
        font_paths.append(p)

    # Fallback absolute paths
    font_paths.extend([
        Path("/home/jwussler/LEDMatrix/assets/fonts/4x6-font.ttf"),
        Path("assets/fonts/4x6-font.ttf"),
    ])

    for font_path in font_paths:
        if font_path.exists():
            font = ImageFont.truetype(str(font_path), 8)
            font_large = ImageFont.truetype(str(font_path), 10)
            return font, font_large

    # Last resort
    font = ImageFont.load_default()
    return font, font


# =============================================================================
# DRAWING HELPERS
# =============================================================================

def new_image() -> Tuple[Image.Image, ImageDraw.Draw]:
    """Create a new blank 192x32 RGB image and draw context."""
    img = Image.new('RGB', (UX.WIDTH, UX.HEIGHT), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    return img, draw


def text_width(text: str) -> int:
    """Calculate pixel width of text string using standard char metrics."""
    return len(text) * UX.CHAR_WIDTH


def text_right_x(text: str) -> int:
    """Calculate x position to right-align text with standard margin."""
    return UX.WIDTH - UX.MARGIN_RIGHT - len(text) * UX.CHAR_WIDTH


def text_center_x(text: str) -> int:
    """Calculate x position to center text on display."""
    return max(UX.MARGIN_LEFT, (UX.WIDTH - len(text) * UX.CHAR_WIDTH) // 2)


def draw_title_row(draw: ImageDraw.Draw, title: str, font: ImageFont.FreeTypeFont,
                   color: tuple = None, right_text: str = None,
                   right_color: tuple = None):
    """
    Draw a standard title row at y=TITLE_Y.
    Optionally adds right-aligned text (e.g. count, status).
    """
    if color is None:
        color = UX.TITLE_COLOR
    draw.text((UX.MARGIN_LEFT, UX.TITLE_Y), title, font=font, fill=color)

    if right_text:
        rx = text_right_x(right_text)
        draw.text((rx, UX.TITLE_Y), right_text, font=font,
                  fill=right_color or UX.TEXT_SECONDARY)


def draw_text_at(draw: ImageDraw.Draw, x: int, y: int, text: str,
                 font: ImageFont.FreeTypeFont, color: tuple):
    """Draw text at exact position."""
    draw.text((x, y), text, font=font, fill=color)


def draw_text_right(draw: ImageDraw.Draw, y: int, text: str,
                    font: ImageFont.FreeTypeFont, color: tuple):
    """Draw right-aligned text at given y position."""
    draw.text((text_right_x(text), y), text, font=font, fill=color)


def draw_text_center(draw: ImageDraw.Draw, y: int, text: str,
                     font: ImageFont.FreeTypeFont, color: tuple):
    """Draw center-aligned text at given y position."""
    draw.text((text_center_x(text), y), text, font=font, fill=color)


def draw_border(draw: ImageDraw.Draw, color: tuple, thickness: int = 2):
    """Draw a border frame around the full display."""
    for i in range(thickness):
        draw.rectangle(
            [i, i, UX.WIDTH - 1 - i, UX.HEIGHT - 1 - i],
            outline=color
        )


def advance_x(text: str, extra_gap: bool = False) -> int:
    """
    Calculate how many pixels to advance x after drawing text.
    Use extra_gap=True for logical field group boundaries.
    """
    spacing = UX.SPACING if extra_gap else (UX.CHAR_WIDTH + 1)
    return len(text) * UX.CHAR_WIDTH + spacing


def get_band_color(band: str) -> tuple:
    """Get standardized band color. Handles case-insensitive lookup."""
    return UX.BAND_COLORS.get(band.lower(), (200, 200, 200))


def get_mode_color(mode: str) -> tuple:
    """Get standardized mode color. Handles case-insensitive lookup."""
    m = mode.upper()
    if m in UX.MODE_COLORS:
        return UX.MODE_COLORS[m]
    # Fuzzy fallback for voice modes
    if m in ("SSB", "USB", "LSB", "AM", "FM"):
        return UX.MODE_COLORS["SSB"]
    return UX.TEXT_PRIMARY


def get_sponsor_color(sponsor: str) -> tuple:
    """Get contest sponsor color."""
    for key, color in UX.SPONSOR_COLORS.items():
        if key in sponsor.upper():
            return color
    return UX.TEXT_SECONDARY

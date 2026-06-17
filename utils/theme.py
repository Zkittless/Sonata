# ── Sonata Theme ─────────────────────────────────────────────────────────────
# Holographic pink palette

PINK_MAIN    = 0xFF8EC8   # Soft holographic pink
PINK_HOT     = 0xFF4DA6   # Hot pink accent
PINK_LIGHT   = 0xFFD6EC   # Light blush
PINK_ERROR   = 0xFF6B8A   # Muted rose for errors
PINK_SUCCESS = 0xC084FC   # Lavender-purple for success

SPARKLE = "✦"
NOTE    = "🎵"
WAVE    = "🌊"

def bar(position: float, total: float, length: int = 18) -> str:
    """Returns a holographic-style progress bar."""
    if total == 0:
        filled = 0
    else:
        filled = int((position / total) * length)
    bar_filled   = "━" * filled
    bar_empty    = "─" * (length - filled)
    cursor       = "⬤"
    return f"`{bar_filled}{cursor}{bar_empty}`"

def fmt_duration(seconds: int) -> str:
    """Formats seconds into mm:ss or hh:mm:ss."""
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"

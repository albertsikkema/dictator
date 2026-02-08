"""Generate menu bar icons for the Dictator app."""

from pathlib import Path

from PIL import Image, ImageDraw

ICONS_DIR = Path(__file__).parent / "icons"


def generate_icons() -> None:
    """Generate menu bar icons."""
    ICONS_DIR.mkdir(exist_ok=True)
    size = 22  # Standard menu bar icon size
    padding = 4

    # Ready icon (gray circle)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([padding, padding, size - padding, size - padding], fill=(100, 100, 100, 255))
    img.save(ICONS_DIR / "ready.png")

    # Transcribing icon (blue circle)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([padding, padding, size - padding, size - padding], fill=(30, 136, 229, 255))
    img.save(ICONS_DIR / "transcribing.png")

    # Recording icons at different levels (red -> orange -> yellow)
    for i in range(6):
        level = i / 5.0
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Color: red -> orange -> yellow
        r = 229
        g = int(57 + level * 198)
        b = int(53 - level * 53)

        # Size based on level
        level_padding = int(padding - level * 2)
        draw.ellipse(
            [level_padding, level_padding, size - level_padding, size - level_padding],
            fill=(r, g, b, 255),
        )
        img.save(ICONS_DIR / f"recording_{i}.png")


if __name__ == "__main__":
    generate_icons()

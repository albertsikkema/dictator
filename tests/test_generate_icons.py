"""Tests for generate_icons module."""

from PIL import Image

import generate_icons


def test_generate_icons_creates_all_files(tmp_path, monkeypatch):
    """Verify all 8 PNG files are created."""
    icons_dir = tmp_path / "icons"
    monkeypatch.setattr(generate_icons, "ICONS_DIR", icons_dir)

    generate_icons.generate_icons()

    expected = ["ready.png", "transcribing.png"] + [f"recording_{i}.png" for i in range(6)]
    for name in expected:
        assert (icons_dir / name).exists(), f"Missing icon: {name}"


def test_generate_icons_creates_valid_pngs(tmp_path, monkeypatch):
    """Verify each file is a valid 22x22 RGBA PNG."""
    icons_dir = tmp_path / "icons"
    monkeypatch.setattr(generate_icons, "ICONS_DIR", icons_dir)

    generate_icons.generate_icons()

    all_icons = ["ready.png", "transcribing.png"] + [f"recording_{i}.png" for i in range(6)]
    for name in all_icons:
        img = Image.open(icons_dir / name)
        assert img.size == (22, 22), f"{name} has wrong size: {img.size}"
        assert img.mode == "RGBA", f"{name} has wrong mode: {img.mode}"


def test_generate_icons_creates_directory(tmp_path, monkeypatch):
    """Verify ICONS_DIR is created if it doesn't exist."""
    icons_dir = tmp_path / "new_icons"
    monkeypatch.setattr(generate_icons, "ICONS_DIR", icons_dir)
    assert not icons_dir.exists()

    generate_icons.generate_icons()

    assert icons_dir.exists()

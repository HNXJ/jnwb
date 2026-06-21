"""Tests for canonical omission palette helpers."""

from src.analysis.lfp.lfp_constants import (
    BANDS,
    BLUE,
    GOLD,
    GREEN,
    OMISSION_PALETTE_ORDER,
    RED,
    VIOLET,
    BLACK,
    colors_for_bands,
    omission_palette_hex,
)


def test_palette_order_length():
    assert len(OMISSION_PALETTE_ORDER) == 13
    assert OMISSION_PALETTE_ORDER[0] == "GOLD"
    assert OMISSION_PALETTE_ORDER[-1] == "WHITE"


def test_omission_palette_hex_indices():
    assert omission_palette_hex(0) == GOLD
    assert omission_palette_hex(1) == BLUE
    assert omission_palette_hex(2) == VIOLET
    assert omission_palette_hex(3) == RED


def test_colors_for_bands_mapping():
    colors = colors_for_bands(BANDS)
    assert colors["Theta"] == GOLD
    assert colors["Alpha"] == BLUE
    assert colors["l-beta"] == VIOLET
    assert colors["h-beta"] == RED
    assert colors["Gamma_L"] == GREEN
    assert colors["Gamma_H"] == BLACK

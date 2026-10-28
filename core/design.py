"""
Curated design presets offered in the admin.

The editor picks from these lists instead of typing font names or hex codes,
so any combination still looks right. To add a preset, add an entry here
(no migration needed: the DB only stores the key).
"""

FONT_PRESETS = {
    "inter_fraunces": {
        "label": "Inter + Fraunces (müasir, zərif kursiv)",
        "sans": "'Inter', system-ui, sans-serif",
        "serif": "'Fraunces', Georgia, serif",
        "google": "family=Inter:wght@400;500;600;700;800&family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,500;1,9..144,400;1,9..144,500",
    },
    "manrope_playfair": {
        "label": "Manrope + Playfair Display (klassik jurnal)",
        "sans": "'Manrope', system-ui, sans-serif",
        "serif": "'Playfair Display', Georgia, serif",
        "google": "family=Manrope:wght@400;500;600;700;800&family=Playfair+Display:ital,wght@0,400;0,600;1,400;1,600",
    },
    "dmsans_lora": {
        "label": "DM Sans + Lora (yumşaq, oxunaqlı)",
        "sans": "'DM Sans', system-ui, sans-serif",
        "serif": "'Lora', Georgia, serif",
        "google": "family=DM+Sans:wght@400;500;600;700;800&family=Lora:ital,wght@0,400;0,600;1,400;1,600",
    },
    "worksans_cormorant": {
        "label": "Work Sans + Cormorant (ədəbi, nəfis)",
        "sans": "'Work Sans', system-ui, sans-serif",
        "serif": "'Cormorant Garamond', Georgia, serif",
        "google": "family=Work+Sans:wght@400;500;600;700;800&family=Cormorant+Garamond:ital,wght@0,500;0,600;1,500;1,600",
    },
}

# accent = links / italic headline, accent_soft = tag & button backgrounds.
COLOR_PRESETS = {
    "green": {"label": "Zümrüd yaşılı", "accent": "#1f6b5c", "accent_soft": "#d9efe8", "accent_bright": "#7fd6c2"},
    "blue": {"label": "Dərin mavi", "accent": "#24508f", "accent_soft": "#dde7f6", "accent_bright": "#8db4ee"},
    "burgundy": {"label": "Bordo", "accent": "#8a2b3c", "accent_soft": "#f4dde1", "accent_bright": "#ee9aab"},
    "terracotta": {"label": "Terrakota", "accent": "#a5502d", "accent_soft": "#f6e2d7", "accent_bright": "#f0a882"},
    "ink": {"label": "Mürəkkəb (qara-boz)", "accent": "#2e3440", "accent_soft": "#e4e6ea", "accent_bright": "#c2c8d2"},
}

FONT_CHOICES = [(key, value["label"]) for key, value in FONT_PRESETS.items()]
COLOR_CHOICES = [(key, value["label"]) for key, value in COLOR_PRESETS.items()]

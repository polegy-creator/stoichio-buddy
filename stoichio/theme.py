"""Shared color tokens for the Streamlit UI."""


def theme_colors(mode):
    if mode == "Dark":
        return {
            "accent": "#f59f3a",
            "accent_soft": "#3a2a17",
            "background": "#0d151b",
            "surface": "#111f28",
            "panel": "#152834",
            "sidebar": "#0a1218",
            "border": "#2d4655",
            "text": "#ecf5f8",
            "muted": "#9eb1bc",
            "input": "#132532",
            "control_bg": "#132532",
            "control_text": "#edf8fb",
            "control_border": "#416171",
            "button_bg": "#f59f3a",
            "button_text": "#1f1308",
            "primary_text": "#1f1308",
            "table_bg": "#10212c",
            "table_header": "#183442",
        }

    return {
        "accent": "#f59f3a",
        "accent_soft": "#fff2df",
        "background": "#ffffff",
        "surface": "#ffffff",
        "panel": "#f7fafb",
        "sidebar": "#f7fafb",
        "border": "#d7dee4",
        "text": "#16232e",
        "muted": "#5d6b78",
        "input": "#ffffff",
        "control_bg": "#ffffff",
        "control_text": "#16232e",
        "control_border": "#c8d2da",
        "button_bg": "#f59f3a",
        "button_text": "#1f1308",
        "primary_text": "#1f1308",
        "table_bg": "#eef6fa",
        "table_header": "#dbeaf1",
    }

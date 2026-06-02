"""Reusable Streamlit UI components."""

import html
import re

import streamlit.components.v1 as components

from stoichio.theme import theme_colors


def display_dataframe(
    df,
    theme_mode,
    row_class_func=None,
    *,
    wrap_columns=None,
    full_text_columns=None,
    row_height=74,
    max_height=12000,
    **kwargs,
):
    """Render a readable, copy-friendly HTML data table.

    Streamlit's built-in dataframe is canvas based, which makes dark theme text,
    link clicking, and copying awkward. This renderer keeps ordinary text and
    anchors in the DOM while supporting horizontal panning from the table frame.
    """
    colors = theme_colors(theme_mode)
    row_count = len(df.index)
    content_height = row_height * (row_count + 1) + 28
    frame_height = min(max_height, max(220, content_height))
    full_text_column_terms = tuple(full_text_columns or ("reference", "source"))
    wrap_column_terms = tuple(
        wrap_columns
        or (
            "check",
            "composition",
            "density source",
            "note",
            "origin",
            "phase",
            "reason",
            "record",
            "reference",
            "source",
            "status",
            "warning",
        )
    )

    def is_full_text_column(column):
        column_text = str(column).strip().lower()
        return any(term in column_text for term in full_text_column_terms)

    def column_class(column):
        column_text = str(column).strip().lower()
        if is_full_text_column(column):
            return "sb-cell-full"
        if any(term in column_text for term in wrap_column_terms):
            return "sb-cell-wrap"
        return "sb-cell-compact"

    def is_note_column(column):
        return "note" in str(column).strip().lower()

    def highlight_empty_note_html(escaped_text):
        return re.sub(
            r"\bempty\b",
            lambda match: f'<span class="sb-note-empty">{match.group(0)}</span>',
            escaped_text,
            flags=re.IGNORECASE,
        )

    def linkify_text(text):
        parts = []
        position = 0
        for match in re.finditer(r"https?://[^\s<>\"]+", text):
            url = match.group(0)
            parts.append(html.escape(text[position:match.start()]))
            parts.append(
                f'<a href="{html.escape(url, quote=True)}" '
                f'target="_blank" rel="noopener noreferrer">{html.escape(url)}</a>'
            )
            position = match.end()
        parts.append(html.escape(text[position:]))
        return "".join(parts)

    def cell_html(column, value):
        text = str(value)
        title = html.escape(text, quote=True)
        cell_class = column_class(column)
        if is_note_column(column):
            escaped = highlight_empty_note_html(html.escape(text))
        else:
            escaped = (
                linkify_text(text)
                if column in {"Reference", "Source"} or "http://" in text or "https://" in text
                else html.escape(text)
            )

        return f'<td class="{cell_class}" title="{title}"><span class="sb-cell-content">{escaped}</span></td>'

    table_rows = []
    headers = "".join(
        f'<th class="{column_class(column)}" title="{html.escape(str(column), quote=True)}">'
        f"{html.escape(str(column))}</th>"
        for column in df.columns
    )
    table_rows.append(f"<tr>{headers}</tr>")

    for _, row in df.iterrows():
        row_class = row_class_func(row) if row_class_func else ""
        class_attr = f' class="{html.escape(row_class)}"' if row_class else ""
        cells = "".join(cell_html(column, row[column]) for column in df.columns)
        table_rows.append(f"<tr{class_attr}>{cells}</tr>")

    table_html = "".join(table_rows)
    components.html(
        f"""
        <!doctype html>
        <html>
        <head>
        <style>
            :root {{
                --sb-accent: {colors["accent"]};
                --sb-bg: {colors["background"]};
                --sb-border: {colors["border"]};
                --sb-panel: {colors["panel"]};
                --sb-table-bg: {colors["table_bg"]};
                --sb-table-header: {colors["table_header"]};
                --sb-text: {colors["text"]};
            }}

            html,
            body {{
                margin: 0;
                padding: 0;
                background: transparent;
                color: var(--sb-text);
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                overflow: hidden;
            }}

            .sb-table-shell {{
                position: relative;
                width: 100%;
                padding: 0 12px;
                border: 1px solid var(--sb-border);
                border-radius: 8px;
                background: var(--sb-table-bg);
                box-sizing: border-box;
            }}

            .sb-table-wrap {{
                width: 100%;
                max-height: none;
                overflow: auto;
                overscroll-behavior: contain;
                border: 0;
                border-radius: 0;
                background: var(--sb-table-bg);
                scrollbar-width: thin;
                scrollbar-color: color-mix(in srgb, var(--sb-accent) 42%, transparent) transparent;
                scrollbar-gutter: stable;
                box-sizing: border-box;
            }}

            .sb-table-pan-zone {{
                position: absolute;
                top: 0;
                bottom: 8px;
                width: 18px;
                z-index: 10;
                cursor: grab;
                background: transparent;
            }}

            .sb-table-pan-zone.left {{
                left: 0;
            }}

            .sb-table-pan-zone.right {{
                right: 0;
            }}

            .sb-table-pan-zone.dragging {{
                cursor: grabbing !important;
                user-select: none !important;
                -webkit-user-select: none !important;
            }}

            .sb-table-wrap::-webkit-scrollbar {{
                width: 8px;
                height: 8px;
            }}

            .sb-table-wrap::-webkit-scrollbar-track {{
                background: transparent;
                border-radius: 999px;
            }}

            .sb-table-wrap::-webkit-scrollbar-thumb {{
                background: color-mix(in srgb, var(--sb-accent) 38%, transparent);
                border: 2px solid transparent;
                background-clip: padding-box;
                border-radius: 999px;
            }}

            .sb-table-wrap::-webkit-scrollbar-thumb:hover {{
                background: color-mix(in srgb, var(--sb-accent) 76%, transparent);
                background-clip: padding-box;
            }}

            .sb-table {{
                min-width: 100%;
                border-collapse: collapse;
                background: var(--sb-table-bg);
                color: var(--sb-text);
                font-size: 0.94rem;
            }}

            .sb-table a {{
                color: var(--sb-accent);
                font-weight: 700;
                text-decoration: underline;
                text-underline-offset: 2px;
            }}

            .sb-table th {{
                background: var(--sb-table-header);
                color: var(--sb-text);
                font-weight: 750;
                text-align: left;
                position: sticky;
                top: 0;
                z-index: 2;
                padding: 0.8rem 0.95rem;
                border-bottom: 1px solid var(--sb-border);
                line-height: 1.35;
                vertical-align: top;
                white-space: nowrap;
            }}

            .sb-table td {{
                background: var(--sb-table-bg);
                color: var(--sb-text);
                padding: 0.85rem 0.95rem;
                border-bottom: 1px solid var(--sb-border);
                line-height: 1.45;
                vertical-align: top;
                white-space: nowrap;
            }}

            .sb-table th.sb-cell-wrap,
            .sb-table td.sb-cell-wrap {{
                min-width: 180px;
                max-width: 520px;
                white-space: normal;
                overflow-wrap: anywhere;
            }}

            .sb-table th.sb-cell-full,
            .sb-table td.sb-cell-full {{
                min-width: 260px;
                max-width: none;
                white-space: nowrap;
                overflow-wrap: normal;
            }}

            .sb-table td .sb-cell-content {{
                display: block;
            }}

            .sb-table td.sb-cell-wrap .sb-cell-content {{
                display: -webkit-box;
                max-height: 4.35em;
                overflow: hidden;
                -webkit-box-orient: vertical;
                -webkit-line-clamp: 3;
            }}

            .sb-table td.sb-cell-full .sb-cell-content {{
                display: block;
                max-height: none;
                overflow: visible;
                -webkit-line-clamp: unset;
            }}

            .sb-table td.sb-cell-full a {{
                white-space: nowrap;
                overflow-wrap: normal;
            }}

            .sb-table td.sb-cell-wrap a {{
                overflow-wrap: anywhere;
            }}

            .sb-table td:first-child,
            .sb-table th:first-child {{
                padding-left: 1rem;
            }}

            .sb-table td:last-child,
            .sb-table th:last-child {{
                padding-right: 1rem;
            }}

            .sb-table tr:last-child td {{
                border-bottom: 0;
            }}

            .sb-table tr.stock-low td {{
                background: color-mix(in srgb, var(--sb-accent) 18%, var(--sb-table-bg)) !important;
            }}

            .sb-table tr.stock-short td,
            .sb-table tr.stock-empty td,
            .sb-table tr.stock-missing td {{
                background: color-mix(in srgb, #d64a4a 22%, var(--sb-table-bg)) !important;
            }}

            .sb-note-empty {{
                display: inline-block;
                padding: 0.02rem 0.28rem;
                border: 1px solid color-mix(in srgb, #ff7668 55%, transparent);
                border-radius: 5px;
                background: color-mix(in srgb, #ff7668 18%, transparent);
                color: #ff7668;
                font-weight: 850;
            }}

            .sb-table tr.codex-seeded td {{
                background: color-mix(in srgb, #2f80ed 18%, var(--sb-table-bg)) !important;
            }}
        </style>
        </head>
        <body>
            <div class="sb-table-shell">
                <div class="sb-table-wrap" aria-label="Scrollable data table">
                    <table class="sb-table">{table_html}</table>
                </div>
                <div class="sb-table-pan-zone left" title="Drag the table frame to move" aria-label="Drag table left frame"></div>
                <div class="sb-table-pan-zone right" title="Drag the table frame to move" aria-label="Drag table right frame"></div>
            </div>
            <script>
            (() => {{
                const wrap = document.querySelector(".sb-table-wrap");
                const panZones = document.querySelectorAll(".sb-table-pan-zone");
                let drag = null;
                let suppressClick = false;

                panZones.forEach((panZone) => panZone.addEventListener("mousedown", (event) => {{
                    if (event.button !== 0 || event.ctrlKey || event.metaKey || event.altKey) {{
                        return;
                    }}
                    drag = {{
                        startX: event.clientX,
                        startY: event.clientY,
                        scrollLeft: wrap.scrollLeft,
                        scrollTop: wrap.scrollTop,
                        moved: false,
                        panZone
                    }};
                    panZone.classList.add("dragging");
                    event.preventDefault();
                }}));

                window.addEventListener("mousemove", (event) => {{
                    if (!drag) {{
                        return;
                    }}
                    const dx = event.clientX - drag.startX;
                    const dy = event.clientY - drag.startY;
                    if (Math.abs(dx) > 2 || Math.abs(dy) > 2) {{
                        drag.moved = true;
                        suppressClick = true;
                    }}
                    wrap.scrollLeft = drag.scrollLeft - dx;
                    wrap.scrollTop = drag.scrollTop - dy;
                    event.preventDefault();
                }});

                function endDrag() {{
                    if (drag && drag.panZone) {{
                        drag.panZone.classList.remove("dragging");
                    }}
                    drag = null;
                    setTimeout(() => {{
                        suppressClick = false;
                    }}, 0);
                }}

                window.addEventListener("mouseup", endDrag);
                window.addEventListener("mouseleave", endDrag);
                panZones.forEach((panZone) => panZone.addEventListener("click", (event) => {{
                    if (!suppressClick) {{
                        return;
                    }}
                    suppressClick = false;
                    event.preventDefault();
                    event.stopPropagation();
                }}, true));
            }})();
            </script>
        </body>
        </html>
        """,
        height=frame_height,
        scrolling=False,
    )

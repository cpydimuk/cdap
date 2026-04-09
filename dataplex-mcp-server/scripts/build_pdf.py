#!/usr/bin/env python3
"""Build a single PDF from the Dataplex MCP Server documentation.

Reads the Markdown files under ``docs/`` in navigation order, converts
them to HTML with the same extension set as ``mkdocs.yml``, applies a
print-friendly stylesheet, and writes a single PDF to
``dataplex-mcp-server-docs.pdf`` at the module root.

Usage:
    python scripts/build_pdf.py              # default output path
    python scripts/build_pdf.py -o out.pdf   # custom output path

Requires: markdown, pymdown-extensions, weasyprint.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

import markdown
from weasyprint import CSS, HTML

HERE = Path(__file__).resolve().parent
MODULE_ROOT = HERE.parent
DOCS_DIR = MODULE_ROOT / "docs"

# Keep in sync with the ``nav`` block in mkdocs.yml.
DOC_ORDER: list[tuple[str, str]] = [
    ("index.md", "Overview"),
    ("getting-started.md", "Getting Started"),
    ("configuration.md", "Configuration"),
    ("tools-reference.md", "Tool Reference"),
    ("architecture.md", "Architecture"),
    ("development.md", "Development"),
    ("troubleshooting.md", "Troubleshooting"),
]

MARKDOWN_EXTENSIONS = [
    "admonition",
    "attr_list",
    "def_list",
    "footnotes",
    "md_in_html",
    "tables",
    "toc",
    "pymdownx.details",
    "pymdownx.highlight",
    "pymdownx.inlinehilite",
    "pymdownx.superfences",
    "pymdownx.tasklist",
]

MARKDOWN_EXTENSION_CONFIGS = {
    "toc": {"permalink": False},
    "pymdownx.highlight": {
        "anchor_linenums": False,
        "pygments_lang_class": True,
        "use_pygments": True,
    },
    "pymdownx.tasklist": {"custom_checkbox": True},
}

# Print stylesheet. Tuned for letter-size pages with comfortable margins,
# a monospace stack for code, and readable table borders.
PRINT_CSS = """
@page {
    size: Letter;
    margin: 22mm 18mm 22mm 18mm;
    @bottom-right {
        content: counter(page) " / " counter(pages);
        font-family: "Helvetica", "Arial", sans-serif;
        font-size: 9pt;
        color: #666;
    }
    @bottom-left {
        content: "Dataplex MCP Server \\2014 Technical Documentation";
        font-family: "Helvetica", "Arial", sans-serif;
        font-size: 9pt;
        color: #666;
    }
}

@page :first {
    margin: 0;
    @bottom-right { content: ""; }
    @bottom-left  { content: ""; }
}

html { font-size: 11pt; }

body {
    font-family: "Helvetica", "Arial", sans-serif;
    color: #1a1a1a;
    line-height: 1.45;
}

.cover {
    page: cover;
    page-break-after: always;
    padding: 60mm 25mm 25mm 25mm;
    background: linear-gradient(180deg, #3f51b5 0%, #303f9f 100%);
    color: white;
    height: 100vh;
    box-sizing: border-box;
}
.cover h1 {
    font-size: 36pt;
    margin: 0 0 8mm 0;
    border: none;
    color: white;
    letter-spacing: -0.5px;
}
.cover .subtitle {
    font-size: 16pt;
    font-weight: 300;
    opacity: 0.92;
    margin-bottom: 40mm;
}
.cover .meta {
    font-size: 11pt;
    opacity: 0.85;
    line-height: 1.8;
}
.cover .meta strong { font-weight: 600; }

.toc-page { page-break-after: always; }
.toc-page h1 {
    font-size: 24pt;
    margin-top: 0;
    border-bottom: 2px solid #3f51b5;
    padding-bottom: 4mm;
}
.toc-page ol {
    font-size: 12pt;
    line-height: 2;
    list-style-position: inside;
    padding-left: 0;
}
.toc-page ol a {
    color: #1a1a1a;
    text-decoration: none;
}

h1, h2, h3, h4, h5, h6 {
    color: #1a237e;
    font-weight: 600;
    page-break-after: avoid;
}

.chapter { page-break-before: always; }
.chapter > h1 {
    font-size: 22pt;
    border-bottom: 2px solid #3f51b5;
    padding-bottom: 3mm;
    margin-top: 0;
}

h2 {
    font-size: 15pt;
    margin-top: 8mm;
    border-bottom: 1px solid #e0e0e0;
    padding-bottom: 1.5mm;
}
h3 { font-size: 12.5pt; margin-top: 6mm; }
h4 { font-size: 11.5pt; margin-top: 5mm; }

p { margin: 0 0 3mm 0; }

a { color: #3f51b5; text-decoration: none; }

code {
    font-family: "Menlo", "Consolas", "DejaVu Sans Mono", monospace;
    font-size: 9.5pt;
    background: #f5f5f5;
    border: 1px solid #e0e0e0;
    border-radius: 2px;
    padding: 0 3px;
}

pre {
    background: #f7f7f9;
    border: 1px solid #e0e0e0;
    border-left: 3px solid #3f51b5;
    border-radius: 3px;
    padding: 3mm 4mm;
    font-size: 9pt;
    line-height: 1.4;
    overflow-x: auto;
    white-space: pre-wrap;
    word-wrap: break-word;
    page-break-inside: avoid;
}
pre code {
    background: transparent;
    border: none;
    padding: 0;
    font-size: 9pt;
}

table {
    border-collapse: collapse;
    width: 100%;
    font-size: 10pt;
    margin: 3mm 0 5mm 0;
    page-break-inside: avoid;
}
th, td {
    border: 1px solid #cfd8dc;
    padding: 2mm 3mm;
    text-align: left;
    vertical-align: top;
}
th {
    background: #eceff1;
    font-weight: 600;
    color: #1a237e;
}

blockquote {
    border-left: 3px solid #ffa726;
    background: #fff8e1;
    margin: 3mm 0;
    padding: 3mm 5mm;
    color: #3e2723;
}
blockquote p:last-child { margin-bottom: 0; }

ul, ol {
    margin: 0 0 3mm 0;
    padding-left: 6mm;
}
li { margin-bottom: 1mm; }

hr {
    border: none;
    border-top: 1px solid #e0e0e0;
    margin: 6mm 0;
}

/* Admonition blocks from python-markdown. */
.admonition {
    border: 1px solid #cfd8dc;
    border-left: 4px solid #3f51b5;
    background: #f5f7fb;
    padding: 3mm 4mm;
    margin: 3mm 0;
    border-radius: 2px;
    page-break-inside: avoid;
}
.admonition-title {
    font-weight: 600;
    color: #1a237e;
    margin: 0 0 2mm 0;
}
.admonition.warning { border-left-color: #f57c00; background: #fff3e0; }
.admonition.warning .admonition-title { color: #e65100; }
.admonition.note { border-left-color: #0288d1; background: #e1f5fe; }
.admonition.note .admonition-title { color: #01579b; }

/* Avoid orphaned headings and awkward table breaks. */
h1, h2, h3 { break-after: avoid-page; }
"""


def render_markdown(text: str) -> str:
    md = markdown.Markdown(
        extensions=MARKDOWN_EXTENSIONS,
        extension_configs=MARKDOWN_EXTENSION_CONFIGS,
        output_format="html5",
    )
    return md.convert(text)


def strip_internal_links(html: str) -> str:
    """Rewrite cross-document links so they don't dangle in the PDF.

    MkDocs uses relative ``.md`` links; in a single-PDF context those
    files don't exist at the same paths, so we convert them to plain
    text while preserving the link label.
    """
    import re

    # Match href="something.md" or href="something.md#anchor"
    return re.sub(
        r'<a\s+href="([^"]+\.md)(#[^"]*)?"[^>]*>(.*?)</a>',
        lambda m: f"<span class=\"xref\">{m.group(3)}</span>",
        html,
        flags=re.DOTALL,
    )


def build_toc() -> str:
    items = "\n".join(
        f'<li>{title}</li>' for _, title in DOC_ORDER
    )
    return f"""
<div class="toc-page">
    <h1>Table of Contents</h1>
    <ol>
        {items}
    </ol>
</div>
"""


def build_cover() -> str:
    today = dt.date.today().isoformat()
    return f"""
<div class="cover">
    <h1>Dataplex MCP Server</h1>
    <div class="subtitle">Technical Documentation</div>
    <div class="meta">
        <div><strong>Version:</strong> 0.1.0</div>
        <div><strong>Status:</strong> Alpha</div>
        <div><strong>License:</strong> Apache-2.0</div>
        <div><strong>Generated:</strong> {today}</div>
    </div>
</div>
"""


def build_html() -> str:
    sections: list[str] = [build_cover(), build_toc()]
    for filename, title in DOC_ORDER:
        path = DOCS_DIR / filename
        if not path.exists():
            print(f"warning: missing {path}", file=sys.stderr)
            continue
        raw = path.read_text(encoding="utf-8")
        body = render_markdown(raw)
        body = strip_internal_links(body)
        sections.append(f'<section class="chapter">{body}</section>')

    combined = "\n".join(sections)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Dataplex MCP Server — Technical Documentation</title>
</head>
<body>
{combined}
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=MODULE_ROOT / "dataplex-mcp-server-docs.pdf",
        help="Output PDF path (default: dataplex-mcp-server-docs.pdf).",
    )
    args = parser.parse_args()

    html_text = build_html()
    HTML(string=html_text, base_url=str(DOCS_DIR)).write_pdf(
        target=str(args.output),
        stylesheets=[CSS(string=PRINT_CSS)],
    )
    size_kb = args.output.stat().st_size / 1024
    print(f"Wrote {args.output} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()

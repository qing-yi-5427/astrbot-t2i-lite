"""Convert a safe subset of Markdown AST into the Codex-inspired Typst layout."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import mistune
from mistune.plugins.table import table_in_quote


_MARKDOWN = mistune.create_markdown(
    renderer="ast", plugins=["table", table_in_quote, "strikethrough", "task_lists", "url"]
)
# Parse deeper than Mistune's six-level default, while keeping recursion bounded.
# The layout flattens excessive indentation before the remaining width runs out.
_MARKDOWN.block.max_nested_level = 16
_TEMPLATE = (Path(__file__).parent / "codex_style.typ").read_text(encoding="utf-8")
_STATUS_SYMBOLS = re.compile(r"(✅|❌|✔️|✖️|[☑☐][\ufe0e\ufe0f]?|⚠️|⚠|🟢|🔴)")
_STATUS_RENDERING = {
    "✅": ('✓', '#238a5a'),
    "✔️": ('✓', '#238a5a'),
    "❌": ('×', '#b84040'),
    "✖️": ('×', '#b84040'),
    "⚠️": ('⚠', '#a16b00'),
    "⚠": ('⚠', '#a16b00'),
    "🟢": ('●', '#238a5a'),
    "🔴": ('●', '#b84040'),
}


def _literal(value: str) -> str:
    """A quoted Typst string: all user content remains data, never Typst source."""
    return json.dumps(value, ensure_ascii=False).replace("\u2028", "\\u{2028}").replace(
        "\u2029", "\\u{2029}"
    )


def _children(node: dict) -> list[dict]:
    return node.get("children") or []


def _checkbox(checked: bool, dark: bool = False) -> str:
    """Draw a crisp checkbox, independent of font glyphs or emoji styling."""
    if checked:
        fill = stroke = '#6dc8ff' if dark else '#28658e'
        check_color = '#142e46' if dark else '#ffffff'
    else:
        fill = 'none'
        stroke = '#a5bdc9' if dark else '#81949e'
        check_color = ''
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20">'
        f'<rect x="1.5" y="1.5" width="17" height="17" rx="3" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
    )
    if checked:
        svg += (
            '<polyline points="5.2,10.3 8.7,13.7 14.7,6.5" fill="none" '
            f'stroke="{check_color}" stroke-width="2.2" '
            'stroke-linecap="round" stroke-linejoin="round"/>'
        )
    svg += '</svg>'
    label = '已完成' if checked else '未完成'
    return (
        '#box(width: 0.95em, height: 0.95em, baseline: 20%)['
        f'#image(bytes({_literal(svg)}), format: "svg", width: 100%, height: 100%, '
        f'alt: {_literal(label)})]'
    )


def _plain_text(raw: str, dark: bool = False) -> str:
    parts = []
    for piece in _STATUS_SYMBOLS.split(raw):
        if not piece:
            continue
        if piece[0] in {'☑', '☐'}:
            parts.append(_checkbox(piece[0] == '☑', dark))
        elif piece in _STATUS_RENDERING:
            symbol, color = _STATUS_RENDERING[piece]
            parts.append(f'#text({_literal(symbol)}, fill: rgb("{color}"), weight: "bold")')
        else:
            parts.append(f"#text({_literal(piece)})")
    return "".join(parts)


def _inline(nodes: list[dict], dark: bool = False) -> str:
    parts: list[str] = []
    for node in nodes:
        kind = node.get("type")
        children = _children(node)
        if kind == "text":
            parts.append(_plain_text(node.get("raw", ""), dark))
        elif kind in {"strong", "emphasis", "strikethrough"}:
            inner = _inline(children, dark)
            if kind == "strong":
                color = "accent" if dark else "accentdeep"
                parts.append(f"#text(weight: \"bold\", fill: {color})[{inner}]")
            elif kind == "emphasis":
                parts.append(f"#emph[{inner}]")
            else:
                parts.append(f"#strike[{inner}]")
        elif kind == "codespan":
            raw = node.get("raw", "")
            parts.append(
                "#box(fill: accentsoft, radius: 2pt, "
                f"inset: (x: 3pt, y: 1pt))[#text({_literal(raw)}, "
                f"font: (\"DejaVu Sans Mono\", \"Noto Sans SC\", \"Noto Color Emoji\"), size: 10pt, fill: accentdeep)]"
            )
        elif kind in {"link", "auto_link"}:
            label = _inline(children, dark) or f"#text({_literal(node.get('attrs', {}).get('url', ''))})"
            color = "accent" if dark else "accentdeep"
            parts.append(f"#text(fill: {color})[{label}]")
        elif kind == "image":
            label = _inline(children, dark) or '#text("图片")'
            color = "accent" if dark else "muted"
            parts.append(f'#text(fill: {color})[#text("图片（外链未加载）："){label}]')
        elif kind == "linebreak":
            parts.append("#linebreak()")
        elif kind == "softbreak":
            parts.append('#text(" ")')
        elif kind in {"inline_html", "html_inline"}:
            raw = node.get("raw", "")
            if re.fullmatch(r"<br\s*/?>", raw, re.IGNORECASE):
                parts.append("#linebreak()")
        elif kind == "escape":
            parts.append(f"#text({_literal(node.get('raw', ''))})")
        elif children:
            parts.append(_inline(children, dark))
        elif node.get("raw"):
            parts.append(f"#text({_literal(node['raw'])})")
    return "".join(parts)


def _table(node: dict) -> str:
    rows: list[tuple[bool, list[dict]]] = []
    for section in _children(node):
        if section.get("type") == "table_head":
            rows.append((True, _children(section)))
        elif section.get("type") == "table_body":
            for row in _children(section):
                rows.append((False, _children(row)))
    if not rows:
        return ""
    columns = max(len(cells) for _, cells in rows)
    if columns > 5:
        # A very wide table becomes a readable vertical set of rows on QQ.
        return "\n".join(
            _block(" / ".join(_inline(_children(cell)) for cell in cells), 7, 7)
            for _, cells in rows
        )
    widths = ["1fr"] * columns
    if columns == 3:
        widths[2] = "1.5fr"
    pieces = [
        f"#table(columns: ({', '.join(widths)}), "
        "inset: 5pt, stroke: 0.5pt + linecolor, "
        "fill: (x, y) => if y == 0 { tableheadbg } else if calc.even(y) { soft } else { paper },"
    ]
    for is_header, cells in rows:
        for cell in cells:
            contents = _inline(_children(cell)) or '#text("")'
            if is_header:
                contents = f"#text(weight: \"bold\", fill: accentdeep)[{contents}]"
            align = cell.get("attrs", {}).get("align")
            if align in {"left", "center", "right"}:
                contents = f"#align({align})[{contents}]"
            pieces.append(f"  [#text(size: 9.5pt)[{contents}]],")
        for _ in range(columns - len(cells)):
            pieces.append('  [#text("")],')
    pieces.append(")")
    return "#block(above: 10pt, below: 10pt)[#text(fill: ink)[" + "\n".join(pieces) + "]]"


def _block(content: str, above: int = 8, below: int = 8) -> str:
    return f"#block(width: 100%, above: {above}pt, below: {below}pt)[{content}]"


def _list(node: dict, depth: int = 0, dark: bool = False, quote_depth: int = 0, available_width: float = 290) -> str:
    ordered = node.get("attrs", {}).get("ordered", False)
    start = int(node.get("attrs", {}).get("start", 1))
    rows = []
    for index, item in enumerate(_children(node)):
        marker = f"{start + index}." if ordered else "•"
        color = "accent" if dark else "accentdeep"
        if item.get("type") == "task_list_item":
            marker_content = _checkbox(bool(item.get("attrs", {}).get("checked")), dark)
        else:
            marker_content = f'#text({_literal(marker)}, fill: {color}, weight: "bold")'
        text_parts = []
        flattened_lists = []
        for child in _children(item):
            if child.get("type") in {"block_text", "paragraph"}:
                paragraph = _inline(_children(child), dark)
                text_parts.append(_block(paragraph, 6, 6) if text_parts else paragraph)
            elif child.get("type") == "list":
                if available_width > 125:
                    text_parts.append(_list(child, depth + 1, dark, quote_depth, available_width - 21))
                else:
                    # Flatten excessive nesting onto the current list level.
                    flattened_lists.append(_list(child, depth, dark, quote_depth, available_width))
            else:
                text_parts.append(_render_nodes([child], dark=dark, quote_depth=quote_depth, available_width=available_width - 21))
        body = "\n".join(text_parts) or '#text("")'
        rows.append(
            _block(
                "#grid(columns: (18pt, 1fr), column-gutter: 3pt, "
                f"[{marker_content}], "
                f"[{body}])",
                5,
                5,
            )
        )
        rows.extend(flattened_lists)
    return _block("\n".join(rows), 7, 7)


def _bot_aside(nodes: list[dict], available_width: float = 290) -> str:
    """The legacy five-space intro is bot commentary, not a Markdown quote."""
    body = _render_nodes(nodes, dark=True, available_width=available_width - 24)
    return _block(
        '#block(width: 100%, fill: asidebg, radius: 5pt, inset: (x: 12pt, y: 11pt))['
        '#let accent = asideaccent\n'
        '#set text(size: 11pt, fill: asideink)\n'
        '#set par(first-line-indent: 0pt, leading: 0.85em, justify: false, linebreaks: "simple")\n'
        + _block('#text("AMADEUS / 个人旁白", size: 8pt, fill: asidelabel, weight: "bold")', 0, 6)
        + body + ']', 0, 15,
    )


def _quote(nodes: list[dict], depth: int = 0, available_width: float = 290) -> str:
    """Light mint quote; nesting has its own inset and thinner side rule."""
    if depth and available_width < 125:
        return _render_nodes(nodes, quote_depth=depth + 1, available_width=available_width)
    body = _render_nodes(nodes, quote_depth=depth + 1, available_width=available_width - (16 if depth else 22))
    label = '' if depth else _block('#text("引用", size: 8pt, fill: quoteink, weight: "bold")', 0, 8)
    return _block(
        '#block(width: 100%, fill: quotebg, radius: 4pt, '
        f'stroke: (left: {1.5 if depth else 2.5}pt + quoteline), '
        f'inset: (x: {8 if depth else 11}pt, y: {8 if depth else 10}pt))['
        '#let accentdeep = quoteink\n'
        '#set text(size: 11pt, fill: quoteink)\n'
        '#set par(first-line-indent: 0pt, leading: 0.85em, justify: false, linebreaks: "simple")\n'
        + label + body + ']', 10, 10,
    )


def _parse_markdown(markdown: str, legacy_reply_prefix: bool = False) -> list[dict]:
    """Translate only the known Codex five-space reply prefix into a bot aside.

    Other clients and real indented/fenced code keep their Markdown semantics.
    Strip the prefix before parsing, so headings/lists/fences stay structural.
    """
    prefix = re.match(r"\A(?:[ \t]*\r?\n)*( {5})(?=\S)", markdown) if legacy_reply_prefix else None
    if prefix:
        markdown = markdown[:prefix.start(1)] + markdown[prefix.end(1):]
    nodes = _MARKDOWN(markdown)
    if prefix:
        for index, node in enumerate(nodes):
            if node.get("type") == "blank_line":
                continue
            if node.get("type") == "paragraph":
                nodes[index] = {"type": "dark_quote", "children": [node]}
            break
    return nodes


def _render_nodes(nodes: list[dict], dark: bool = False, quote_depth: int = 0, available_width: float = 290) -> str:
    out: list[str] = []
    for node in nodes:
        kind = node.get("type")
        if kind in {"blank_line", "html_block", "block_html"}:
            continue
        if kind in {"paragraph", "block_text"}:
            spacing = 6 if dark or quote_depth else 8
            out.append(_block(_inline(_children(node), dark) or '#text("")', spacing, spacing))
        elif kind == "heading":
            level = int(node.get("attrs", {}).get("level", 1))
            size = {1: 20, 2: 15, 3: 13}.get(level, 12)
            above = 4 if level == 1 else 15 if level == 2 else 12
            label = '#text("研究记录", size: 8pt, fill: accentdeep, weight: "bold")\n#v(5pt)\n' if level == 1 and not dark and not quote_depth else ''
            color = "asideink" if dark else "quoteink" if quote_depth else "ink"
            out.append(
                _block(
                    label + f"#text(font: (\"Noto Sans SC\", \"Noto Sans CJK SC\", \"Noto Color Emoji\"), size: {size}pt, "
                    f"weight: \"bold\", fill: {color})[{_inline(_children(node), dark)}]",
                    above,
                    8,
                )
            )
        elif kind == "dark_quote":
            out.append(_bot_aside(_children(node), available_width))
        elif kind == "block_quote":
            out.append(_quote(_children(node), quote_depth, available_width))
        elif kind == "block_code":
            code = node.get("raw", "").rstrip("\n")
            # Keep long lines inside the 720 px card without silently clipping text.
            limit = max(8, min(46, int((available_width - 24) / 5.8)))
            code = "\n".join(_wrap_code_line(line, limit) for line in code.splitlines())
            info = (node.get("attrs", {}).get("info") or "").split()
            lang = info[0] if info else "CODE"
            lang = lang if re.fullmatch(r"[A-Za-z0-9_+#.-]{1,24}", lang) else "CODE"
            header = (
                '#block(width: 100%, fill: codehead, inset: (x: 11pt, y: 8pt))['
                '#grid(columns: (5pt, 5pt, 5pt, 1fr), column-gutter: 4pt, '
                '[#circle(radius: 2pt, fill: rgb("#ee9a9a"))], '
                '[#circle(radius: 2pt, fill: rgb("#e5c189"))], '
                '[#circle(radius: 2pt, fill: rgb("#98c6ad"))], '
                f'[#align(right)[#text({_literal(lang.upper())}, size: 8pt, fill: rgb("#c8cbdc"))]])]'
            )
            out.append(
                _block(
                    '#block(width: 100%, fill: codebg, radius: 5pt, clip: true)['
                    + header + '#block(width: 100%, inset: (x: 11pt, y: 11pt))['
                    '#text(font: ("DejaVu Sans Mono", "Noto Sans SC", "Noto Color Emoji"), size: 9.5pt, '
                    f"fill: codeink)[#raw({_literal(code)}, block: true, theme: none)]"
                    "]]",
                    10,
                    10,
                )
            )
        elif kind == "list":
            out.append(_list(node, dark=dark, quote_depth=quote_depth, available_width=available_width))
        elif kind == "table":
            out.append(_table(node))
        elif kind == "thematic_break":
            out.append(_block("#block(width: 100%, height: 0.6pt, fill: linecolor)", 15, 15))
        elif node.get("raw"):
            out.append(_block(f"#text({_literal(node['raw'])})"))
    return "\n".join(out)


def _wrap_code_line(line: str, limit: int = 46) -> str:
    """Wrap display columns, not code points; CJK is approximately two columns."""
    parts: list[str] = []
    current = ''
    columns = 0
    for char in line:
        if char == '\t':
            char = ' ' * (4 - columns % 4)
        width = sum(0 if unicodedata.combining(c) or c in {'\u200d', '\ufe0e', '\ufe0f'} else 2 if unicodedata.east_asian_width(c) in {'W', 'F'} else 1 for c in char)
        if columns + width > limit and current:
            parts.append(current)
            current, columns = '  ', 2
        current += char
        columns += width
    parts.append(current)
    return "\n".join(parts)


def to_typst(markdown: str, version: str = "", model_name: str = "", *, legacy_reply_prefix: bool = False) -> str:
    blocks = _render_nodes(_parse_markdown(markdown, legacy_reply_prefix))
    if not blocks:
        blocks = _block('#text(fill: muted)[暂时没有可显示的内容]')
    # Model metadata is data, never executable Typst markup. Replace template
    # tokens in one pass so token-looking user text cannot alter other fields.
    model = " ".join(model_name.split())[:160] if isinstance(model_name, str) else ""
    footer = f"回复模型：{model}" if model else "AMADEUS  ·  POWERED BY ASTRBOT"
    values = {"VERSION": _literal(version[:32]), "FOOTER": _literal(footer), "CONTENT": blocks}
    return re.sub(r"\{\{(VERSION|FOOTER|CONTENT)\}\}", lambda match: values[match[1]], _TEMPLATE)

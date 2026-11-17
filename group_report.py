"""Reflow known group-analysis HTML as local Typst, without executing HTML/CSS."""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser

from markdown_typst import _style_literal
from theme_package import ThemePackage, parse_theme_package

PROJECT = "astrbot_plugin_qq_group_daily_analysis"
VOID = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}
IGNORED = {"head", "style", "script", "svg", "noscript", "template", "iframe", "object"}
STAT_GROUPS = {"stats-grid", "stats-row", "stats-container", "statistics-grid"}
SECTION_TITLES = {
    "section-title",
    "section-title-text",
    "section-heading",
    "section-label",
    "peak-label",
    "highlight-label",
}
ITEM_TITLES = {
    "topic-title",
    "u-name",
    "user-name",
    "q-sender-name",
    "theme-title-badge",
    "dim-sticker-title",
}
CHART_ROWS = {"chart-column", "activity-col", "sf-chart-col", "hour-bar-container"}
HOUR_LABELS = {
    "chart-label-xaxis",
    "activity-tick",
    "activity-label-hour",
    "sf-chart-tick",
    "hour-label",
}
COUNT_LABELS = {
    "chart-value-top",
    "activity-val-top",
    "activity-col-count",
    "sf-chart-val",
    "hourly-value-inside",
    "hourly-value-outside",
}


@dataclass(eq=False)
class Node:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list[Node | str] = field(default_factory=list)
    parent: Node | None = None
    hidden: bool = False

    @property
    def classes(self):
        return set(self.attrs.get("class", "").split())


class Document(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.root = Node("document")
        self.stack = [self.root]
        self.count = 0
        self.feed(source)
        self.close()

    def handle_starttag(self, tag, attrs):
        self.count += 1
        if self.count > 40000 or len(self.stack) > 128:
            raise ValueError("群分析 HTML 结构过大或嵌套过深")
        values = {
            k: v or ""
            for k, v in attrs
            if k in {"class", "style", "title", "aria-hidden", "hidden"}
        }
        hidden = (
            self.stack[-1].hidden
            or tag in IGNORED
            or "hidden" in values
            or values.get("aria-hidden") == "true"
            or bool(
                re.search(
                    r"(?:display\s*:\s*none|visibility\s*:\s*hidden)",
                    values.get("style", ""),
                    re.IGNORECASE,
                )
            )
        )
        node = Node(tag, values, parent=self.stack[-1], hidden=hidden)
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        if not self.stack[-1].hidden:
            self.stack[-1].children.append(data.replace("\ufeff", ""))


def nodes(root):
    """Walk visible nodes once; CSS/JS/SVG content never enters the report."""
    todo = [root]
    while todo:
        node = todo.pop()
        if node.hidden:
            continue
        yield node
        todo.extend(reversed([c for c in node.children if isinstance(c, Node)]))


def plain(root):
    parts = []

    def collect(node):
        if isinstance(node, str):
            parts.append(node)
        elif not node.hidden:
            for child in node.children:
                collect(child)

    collect(root)
    return " ".join(" ".join(parts).split())


def number(text):
    text = text.strip().replace(",", "")
    if not re.fullmatch(r"\d{1,10}", text) or int(text) > 1_000_000_000:
        raise ValueError("群分析活动图数值无效")
    return int(text)


def activity_chart(body):
    """Recover exact hourly counts from all nine currently shipped templates."""
    visible = list(nodes(body))
    rows = [n for n in visible if n.classes & CHART_ROWS]
    if rows:
        points = []
        for row in rows:
            label = next((plain(n) for n in nodes(row) if n.classes & HOUR_LABELS), "")
            count = (
                next((plain(n) for n in nodes(row) if n.classes & COUNT_LABELS), "0")
                or "0"
            )
            match = re.fullmatch(r"(\d{1,2})(?::00)?", label)
            if not match:
                return None, []
            points.append((int(match[1]), number(count)))
        parents = {row.parent for row in rows}
        if len(parents) == 1:
            return next(iter(parents)), checked_points(points)
    miku = next((n for n in visible if "miku-activity-chart" in n.classes), None)
    if miku:
        groups = [n for n in miku.children if isinstance(n, Node)]
        if len(groups) >= 2:
            bars = [n for n in groups[0].children if isinstance(n, Node)]
            labels = [n for n in groups[1].children if isinstance(n, Node)]
            if len(bars) == len(labels) == 24:
                points = []
                for label, bar in zip(labels, bars):
                    hour = re.fullmatch(r"(\d{1,2})(?::00|\s*时)?", plain(label))
                    if not hour:
                        raise ValueError("群分析活动图小时标签无效")
                    points.append((int(hour[1]), number(plain(bar) or "0")))
                return miku, checked_points(points)
    # ATRI puts the exact data in each bar's title rather than a class.
    titled = []
    for node in visible:
        match = re.fullmatch(
            r"(\d{1,2})时\s*-\s*(\d+)条消息", node.attrs.get("title", "")
        )
        if match:
            titled.append((node, (int(match[1]), number(match[2]))))
    if titled:
        root = next(
            (
                n
                for n in visible
                if "chart-container" in n.classes
                and any(x is titled[0][0] for x in nodes(n))
            ),
            None,
        )
        if root:
            return root, checked_points([point for _, point in titled])
    # The minimal template uses unclassed horizontal rows, each with HH:00/count.
    for root in visible:
        children = [n for n in root.children if isinstance(n, Node) and not n.hidden]
        if len(children) != 24:
            continue
        points = []
        for child in children:
            match = re.fullmatch(r"(\d{1,2}):00\s+(\d+)", plain(child))
            if not match:
                break
            points.append((int(match[1]), number(match[2])))
        if len(points) == 24:
            return root, checked_points(points)
    return None, []


def checked_points(points):
    if len(points) != 24 or sorted(hour for hour, _ in points) != list(range(24)):
        raise ValueError("群分析活动图必须包含完整且不重复的 24 小时")
    return sorted(points)


def chart_svg(points):
    maximum = max((count for _, count in points), default=1) or 1
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="780" height="190" viewBox="0 0 780 190">',
        '<path d="M10 151H770" stroke="#cfdeea"/>',
    ]
    for hour, count in points:
        x = 12 + hour * 31.5
        height = count / maximum * 120
        parts.append(
            f'<rect x="{x:.2f}" y="{150 - height:.2f}" width="21" height="{max(1, height):.2f}" rx="3" fill="{"#2186bd" if count == maximum else "#7fbdd5"}"/>'
        )
        if count:
            parts.append(
                f'<text x="{x + 10.5:.2f}" y="{143 - height:.2f}" text-anchor="middle" font-family="DejaVu Sans" font-size="10" fill="#355369">{count}</text>'
            )
        parts.append(
            f'<text x="{x + 10.5:.2f}" y="174" text-anchor="middle" font-family="DejaVu Sans" font-size="11" fill="#61788c">{hour:02d}</text>'
        )
    return ("".join(parts) + "</svg>").encode()


def escape(text):
    return re.sub(r"([\\`*_[\]<>|])", r"\\\1", re.sub(r"\s+", " ", text))


def markdown(node, skip):
    if isinstance(node, str):
        return escape(node)
    if (
        node.hidden
        or node in skip
        or node.tag == "img"
        or any(c.startswith("deco-") for c in node.classes)
    ):
        return ""
    inner = "".join(markdown(child, skip) for child in node.children).strip()
    if node.tag == "br":
        return "\n"
    if node.tag == "hr":
        return "\n\n---\n\n"
    if not inner:
        return ""
    if re.fullmatch(r"h[1-6]", node.tag):
        return (
            "\n\n"
            + "#" * max(2, int(node.tag[1]))
            + " "
            + re.sub(r"\s+", " ", inner)
            + "\n\n"
        )
    if node.classes & SECTION_TITLES:
        return "\n\n## " + re.sub(r"\s+", " ", inner) + "\n\n"
    if node.classes & ITEM_TITLES:
        return "\n\n### " + re.sub(r"\s+", " ", inner) + "\n\n"
    if node.tag in {"strong", "b"}:
        return "**" + inner + "**"
    if node.tag in {"em", "i"}:
        return "*" + inner + "*"
    if node.tag == "li":
        return "\n- " + re.sub(r"\s+", " ", inner) + "\n"
    if node.tag == "blockquote" or "q-content" in node.classes:
        return "\n\n> " + inner.replace("\n", "\n> ") + "\n\n"
    if node.tag in {
        "div",
        "section",
        "article",
        "header",
        "footer",
        "p",
        "ul",
        "ol",
        "table",
        "tr",
    }:
        return "\n\n" + inner + "\n\n"
    return inner + " "


@dataclass
class Report:
    text: str
    theme: ThemePackage
    hourly_counts: list[tuple[int, int]]


def adapt_group_report(source: str) -> Report | None:
    """Recognize the plugin's report only; ordinary/custom HTML keeps its route."""
    if PROJECT not in source or "<body" not in source.lower():
        return None
    document = Document(source)
    body = next((n for n in nodes(document.root) if n.tag == "body"), None)
    if body is None:
        return None
    content = plain(body)
    if not re.search(r"消息|Message", content, re.IGNORECASE) or not re.search(
        r"参与|人数|Participant|Users", content, re.IGNORECASE
    ):
        return None
    visible = list(nodes(body))
    heading = next((n for n in visible if n.tag == "h1"), None)
    if heading is None:
        return None
    title = plain(heading)[:64] or "群聊分析报告"
    date = re.search(r"20\d{2}(?:年|-|/)\d{1,2}(?:月|-|/)\d{1,2}日?", content)
    skip = {heading}
    header = next(
        (n for n in visible if "header" in n.classes and heading in list(nodes(n))),
        None,
    )
    if header:
        skip.add(header)
    stats = []
    for node in visible:
        if not node.classes & STAT_GROUPS:
            continue
        for child in node.children:
            if not isinstance(child, Node) or child.hidden:
                continue
            match = re.fullmatch(r"([\d,]+)\s*(.{1,24})", plain(child))
            if match:
                stats.append((str(number(match[1])), match[2]))
        if len(stats) >= 2:
            skip.add(node)
            break
        stats.clear()
    chart_root, points = activity_chart(body)
    if chart_root:
        skip.add(chart_root)
    text = markdown(body, skip)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text or len(text) > 100000:
        raise ValueError("群分析正文为空或超过 100000 字符")
    cards = ",\n".join(
        "block(fill: white, radius: 7pt, inset: 10pt, width: 100%)[#text("
        + _style_literal(value)
        + ', size: 23pt, weight: "bold", fill: accentdeep) #parbreak() #text('
        + _style_literal(label)
        + ", size: 8pt, fill: muted)]"
        for value, label in stats
    )
    stats_source = (
        "#grid(columns: ("
        + ",".join("1fr" for _ in stats)
        + "), gutter: 7pt,"
        + cards
        + ")\n#v(9pt)\n"
        if cards
        else ""
    )
    chart_source = (
        '#block(fill: white, radius: 7pt, inset: 10pt)[#text("24 小时活跃分布", weight: "bold", fill: accentdeep) #v(6pt) #image("assets/activity.svg", width: 100%)]\n#v(10pt)\n'
        if points
        else ""
    )
    theme_source = (
        """
#let canvas = rgb("#eef4f8")
#let paper = white
#let ink = rgb("#243b50")
#let accentdeep = rgb("#246987")
#set page(width: 440pt, height: auto, margin: 18pt, fill: canvas)
#set text(size: 12pt, fill: ink)
#set par(leading: 0.65em)
#block(width: 100%, fill: rgb("#1d3e55"), radius: 8pt, inset: 14pt)[
  #text(brand, size: 22pt, weight: "bold", fill: white)
  #v(5pt)
  #text(subtitle, size: 9pt, fill: rgb("#b9d9e8"))
]
#v(10pt)
"""
        + stats_source
        + chart_source
        + "{{CONTENT}}"
    )
    files = (
        {"assets/activity.svg": base64.b64encode(chart_svg(points)).decode()}
        if points
        else {}
    )
    theme = parse_theme_package(
        {
            "id": "group-analysis-report",
            "source": theme_source,
            "meta": {
                "brand_name": title,
                "subtitle": (date[0] + "  ·  群聊分析报告") if date else "群聊分析报告",
            },
            "files": files,
        }
    )
    return Report(text, theme, points)

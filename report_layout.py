"""Structured report cards which inherit the selected chat theme's palette/header."""

from dataclasses import dataclass
import re

from group_report import Document, nodes, plain
from markdown_typst import _style_literal as literal


def text(value, limit=16000, *, html=False):
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError("群分析报告文字无效或过长")
    if html:
        value = plain(Document("<body>" + value + "</body>").root)
    return value.strip()


def integer(value, maximum=1_000_000_000):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError("群分析统计数值无效")
    return value


def items(value, maximum=64):
    if (
        not isinstance(value, list)
        or len(value) > maximum
        or any(not isinstance(x, dict) for x in value)
    ):
        raise ValueError("群分析报告列表无效或过长")
    return value


@dataclass
class StructuredReport:
    summary: dict
    hours: list
    topics: list
    people: list
    quotes: list
    quality: dict
    names: tuple = ()

    @classmethod
    def parse(cls, value):
        if (
            not isinstance(value, dict)
            or type(value.get("schema")) is not int
            or value["schema"] != 1
        ):
            raise ValueError("不支持的结构化群分析报告协议")
        raw = value.get("summary")
        if not isinstance(raw, dict):
            raise ValueError("群分析报告缺少统计")
        summary = {
            key: integer(raw.get(key, 0))
            for key in (
                "message_count",
                "participant_count",
                "total_characters",
                "emoji_count",
                "total_tokens",
                "prompt_tokens",
                "completion_tokens",
            )
        }
        summary.update(
            {
                key: text(raw.get(key, ""), 96)
                for key in ("current_date", "current_datetime", "most_active_period")
            }
        )
        hours = [
            (integer(x.get("hour"), 23), integer(x.get("count")))
            for x in items(value.get("hours", []), 24)
        ]
        if hours and (
            len(hours) != 24 or sorted(h for h, _ in hours) != list(range(24))
        ):
            raise ValueError("活动图应为完整的 24 小时")
        topics = [
            {
                key: text(x.get(key, ""), html=key in {"detail", "contributors"})
                for key in ("title", "contributors", "detail")
            }
            for x in items(value.get("topics", []))
        ]
        people = [
            {
                key: text(x.get(key, ""), html=key == "reason")
                for key in ("name", "title", "profile_display", "mbti", "reason")
            }
            for x in items(value.get("people", []))
        ]
        quotes = [
            {
                key: text(x.get(key, ""), html=key == "reason")
                for key in ("sender", "content", "reason")
            }
            for x in items(value.get("quotes", []))
        ]
        quality = value.get("quality", {})
        if not isinstance(quality, dict):
            raise ValueError("质量锐评格式无效")
        review = {
            key: text(quality.get(key, ""), html=key == "summary")
            for key in ("title", "subtitle", "summary")
        }
        dimensions = []
        for dimension in items(quality.get("dimensions", []), 24):
            percentage = dimension.get("percentage", 0)
            if type(percentage) not in (int, float) or not 0 <= percentage <= 100:
                raise ValueError("锐评维度百分比无效")
            dimensions.append(
                {
                    "name": text(dimension.get("name", ""), 96),
                    "comment": text(dimension.get("comment", ""), html=True),
                    "percentage": percentage,
                }
            )
        review["dimensions"] = dimensions
        if sum(len(str(x)) for x in (summary, topics, people, quotes, review)) > 100000:
            raise ValueError("群分析报告正文过长")
        names = {item["name"] for item in people if item["name"]}
        names.update(item["sender"] for item in quotes if item["sender"])
        for item in topics:
            names.update(
                name.strip()
                for name in item["contributors"].split("、")
                if name.strip()
            )
        # The original plugin explicitly marks person references. Preserve those
        # identities after stripping the presentation HTML and inline avatars.
        fragments = [item.get("detail", "") for item in value.get("topics", [])]
        fragments += [item.get("reason", "") for item in value.get("people", [])]
        fragments += [item.get("reason", "") for item in value.get("quotes", [])]
        for fragment in fragments:
            if "user-capsule" in fragment:
                names.update(
                    plain(node)
                    for node in nodes(Document(fragment).root)
                    if "user-capsule" in node.classes and plain(node)
                )
        names = tuple(
            sorted(
                (
                    name
                    for name in names
                    if 2 <= len(name) <= 128
                    and name not in {"我们", "你们", "他们", "大家", "群友", "用户"}
                ),
                key=lambda name: (-len(name), name),
            )[:256]
        )
        return cls(summary, sorted(hours), topics, people, quotes, review, names)

    @property
    def footer(self):
        return "群聊分析报告  ·  " + self.summary["current_date"]


def identifier(value, size=11.5):
    # A text highlight can wrap across lines; an inline box would overflow on
    # long QQ nicknames, especially in the two-column portrait cards.
    return (
        "#highlight(fill: accentsoft, extent: 1.2pt, radius: 1.5pt)["
        + f'#text({literal(value)}, size: {size}pt, fill: accentdeep, weight: "bold")]'
    )


def mention_pattern(names):
    parts = []
    for name in names:
        escaped = re.escape(name)
        if re.fullmatch(r"[A-Za-z0-9_]+", name):
            escaped = r"(?<![A-Za-z0-9_])" + escaped + r"(?![A-Za-z0-9_])"
        parts.append(escaped)
    return re.compile("|".join(parts)) if parts else None


def content_text(
    value, size=11.5, *, fill="ink", bold=False, mentions=None, as_identifier=False
):
    if as_identifier:
        return identifier(value, size)
    if mentions is not None and mentions.search(value):
        pieces = []
        offset = 0
        for match in mentions.finditer(value):
            if match.start() > offset:
                pieces.append("#text(" + literal(value[offset : match.start()]) + ")")
            pieces.append(identifier(match[0], size))
            offset = match.end()
        if offset < len(value):
            pieces.append("#text(" + literal(value[offset:]) + ")")
        return f"#text(size: {size}pt, fill: {fill})[" + "".join(pieces) + "]"
    return (
        f"#text({literal(value)}, size: {size}pt, fill: {fill}"
        + (', weight: "bold"' if bold else "")
        + ")"
    )


def paragraph(value, size=11.5, fill="ink", mentions=None):
    return (
        "#block(width: 100%)[#set par(leading: 0.62em, spacing: 0pt)\n"
        + content_text(value, size, fill=fill, mentions=mentions)
        + "]"
    )


def section(number, title, count=""):
    return (
        "#v(15pt)\n#grid(columns: (auto, 1fr, auto), column-gutter: 7pt, align: horizon,"
        f"[#box(fill: accentdeep, radius: 3pt, inset: (x: 5pt, y: 3pt))[{content_text(number, 8, fill='paper', bold=True)}]],"
        f"[{content_text(title, 14, fill='accentdeep', bold=True)}], [{content_text(count, 8.5, fill='inksoft')}])\n#v(8pt)\n"
    )


def card(body, *, fill="soft", inset="10pt", border=True):
    return (
        f"block(width: 100%, fill: {fill}, radius: 5pt, inset: {inset}"
        + (", stroke: 0.5pt + linecolor" if border else "")
        + ")["
        + body
        + "]"
    )


def render_report(report):
    """Return trusted Typst layout; every report string stays inside a literal."""
    s = report.summary
    mentions = mention_pattern(report.names)
    output = [
        content_text("群聊观察报告", 18, fill="accentdeep", bold=True),
        "#v(4pt)",
        content_text(s["current_date"], 9, fill="inksoft"),
        "#v(11pt)",
    ]
    stats = []
    for label, key in [
        ("消息", "message_count"),
        ("参与群友", "participant_count"),
        ("表情", "emoji_count"),
        ("总字符", "total_characters"),
    ]:
        stats.append(
            card(
                content_text(str(s[key]), 17, fill="accentdeep", bold=True)
                + "#v(4pt)"
                + content_text(label, 8.2, fill="inksoft"),
                inset="7pt",
            )
        )
    output.append(
        "#grid(columns: (1fr,1fr,1fr,1fr), gutter: 5pt," + ",".join(stats) + ")"
    )
    if report.hours:
        maximum = max(n for _, n in report.hours) or 1
        bars = []
        for hour, count in report.hours:
            color = "accentdeep" if count == maximum else "accent"
            height = max(0.7, count / maximum * 52)
            bars.append(
                "stack(dir: ttb, spacing: 3pt,"
                "[#box(height: 9pt)["
                + (
                    content_text(str(count), 5.2, fill="inksoft")
                    if count >= maximum * 0.45 and count
                    else ""
                )
                + "]],"
                f"[#box(height: 54pt, width: 100%)[#align(bottom)[#block(width: 100%, height: {height:.3f}pt, fill: {color}, radius: (top: 1.5pt))]]],"
                "[" + content_text(f"{hour:02}", 5.4, fill="inksoft") + "])"
            )
        peak = s["most_active_period"] or "—"
        chart = (
            content_text("24 小时活跃轨迹", 11, fill="accentdeep", bold=True)
            + "#h(1fr)"
            + content_text("峰值 " + peak, 8.5, fill="inksoft")
            + "#v(8pt)"
        )
        chart += (
            "#grid(columns: (1fr,)*24, column-gutter: 1.4pt," + ",".join(bars) + ")"
        )
        output.extend(["#v(8pt)", "#" + card(chart, fill="paper", inset="8pt")])
    index = 0
    if report.topics:
        index += 1
        output.append(
            section(f"{index:02}", "话题手记", f"{len(report.topics)} 个话题")
        )
        for i, item in enumerate(report.topics, 1):
            body = content_text(
                f"{i:02}  " + item["title"], 12.5, fill="accentdeep", bold=True
            )
            if item["contributors"]:
                participants = [
                    name.strip()
                    for name in item["contributors"].split("、")
                    if name.strip()
                ]
                body += (
                    "#v(6pt)#block(width:100%)["
                    + content_text("参与：", 9.5, fill="inksoft")
                    + '#text("、")'.join(identifier(name, 9.8) for name in participants)
                    + "]"
                )
            if item["detail"]:
                body += "#v(7pt)" + paragraph(item["detail"], mentions=mentions)
            output.extend(["#" + card(body), "#v(8pt)"])
    if report.people:
        index += 1
        output.append(
            section(f"{index:02}", "群友观察", f"{len(report.people)} 位群友")
        )
        people = []
        for item in report.people:
            body = (
                content_text(
                    item["name"] or "群友",
                    11.5,
                    bold=True,
                    as_identifier=bool(item["name"]),
                )
                + "#v(5pt)"
                + content_text(item["title"], 10.5, fill="accentdeep", bold=True)
            )
            profile = item["profile_display"] or item["mbti"]
            if profile:
                body += "#v(4pt)" + content_text(profile, 8.5, fill="inksoft")
            if item["reason"]:
                body += "#v(7pt)" + paragraph(item["reason"], 10.5, mentions=mentions)
            people.append(card(body, fill="paper", inset="9pt"))
        output.append("#grid(columns: (1fr,1fr), gutter: 8pt," + ",".join(people) + ")")
    if report.quotes:
        index += 1
        output.append(
            section(f"{index:02}", "群聊摘录", f"{len(report.quotes)} 条金句")
        )
        for item in report.quotes:
            body = (
                content_text(
                    item["sender"] or "群友",
                    10.5,
                    fill="accentdeep",
                    bold=True,
                    as_identifier=bool(item["sender"]),
                )
                + "#v(6pt)"
            )
            body += (
                "#block(width: 100%, fill: quotebg, inset: 9pt, radius: 4pt, stroke: (left: 2pt + quoteline))["
                + paragraph(item["content"], 11.5, "quoteink", mentions=mentions)
                + "]"
            )
            if item["reason"]:
                body += (
                    "#v(7pt)"
                    + content_text("点评", 8.5, fill="accentdeep", bold=True)
                    + "#v(3pt)"
                    + paragraph(item["reason"], 10.5, mentions=mentions)
                )
            output.extend(["#" + card(body, fill="paper"), "#v(8pt)"])
    review = report.quality
    if review["title"] or review["summary"] or review["dimensions"]:
        index += 1
        output.append(section(f"{index:02}", "今日锐评"))
        body = content_text(
            review["title"], 12, fill="accentdeep", bold=True, mentions=mentions
        )
        if review["subtitle"]:
            body += "#v(5pt)" + paragraph(review["subtitle"], 10, mentions=mentions)
        if review["summary"]:
            body += "#v(7pt)" + paragraph(review["summary"], 11, mentions=mentions)
        output.append("#" + card(body, fill="accentsoft"))
        for dimension in review["dimensions"]:
            width = f"{max(0, dimension['percentage']):.3f}%"
            body = (
                "#grid(columns:(1fr,auto),align:horizon,["
                + content_text(dimension["name"], 10.5, bold=True)
                + "],["
                + content_text(
                    f"{dimension['percentage']:g}%", 9.5, fill="accentdeep", bold=True
                )
                + "])"
            )
            body += (
                "#v(5pt)#block(width:100%,height:3pt,fill:linecolor,radius:1.5pt)[#block(width:"
                + width
                + ",height:3pt,fill:accent,radius:1.5pt)]"
            )
            if dimension["comment"]:
                body += "#v(5pt)" + paragraph(
                    dimension["comment"], 10.5, mentions=mentions
                )
            output.extend(["#v(7pt)", "#" + card(body, fill="paper", inset="8pt")])
    output.extend(
        [
            "#v(12pt)",
            content_text(
                f"分析消耗 {s['total_tokens']:,} Token  ·  " + s["current_datetime"],
                7.5,
                fill="inksoft",
            ),
        ]
    )
    return "\n".join(output)

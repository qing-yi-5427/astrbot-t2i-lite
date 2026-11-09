"""Decode self-contained Typst themes received from the local AstrBot plugin."""

from __future__ import annotations

import base64
import binascii
import re
from dataclasses import dataclass
from pathlib import PurePosixPath

from themes import TEMPLATE_CATALOG

THEME_ID = re.compile(r"[a-z][a-z0-9_-]{0,47}\Z")
MAX_SOURCE_BYTES = 256 * 1024
MAX_ASSET_BYTES = 2 * 1024 * 1024
MAX_ASSETS = 64


@dataclass(frozen=True)
class ThemePackage:
    """A validated source and regular-file assets, never server file paths."""

    id: str
    source: str
    catalog: dict
    files: dict[str, bytes]
    avatar: str | None


def parse_theme_package(value: object) -> ThemePackage:
    """Validate transport boundaries without prescribing a visual design.

    Args:
        value: JSON object constructed by the repository plugin.

    Returns:
        A package whose files can be written under a temporary project root.

    Raises:
        ValueError: If identity, source, resource paths or size bounds are invalid.
    """
    if not isinstance(value, dict) or type(value.get("schema", 1)) is not int or value.get("schema", 1) != 1:
        raise ValueError("不支持的主题传输协议")
    identity = value.get("id")
    source = value.get("source")
    if not isinstance(identity, str) or not THEME_ID.fullmatch(identity):
        raise ValueError("主题目录名须为小写字母开头的英文 ID，可含数字、下划线和连字符")
    if not isinstance(source, str) or len(source.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise ValueError("主题源码无效或超过 256 KiB")
    if "{{CONTENT}}" not in source:
        raise ValueError("主题缺少正文入口 {{CONTENT}}")
    metadata = value.get("meta", {})
    encoded_files = value.get("files", {})
    if not isinstance(metadata, dict) or not isinstance(encoded_files, dict) or len(encoded_files) > MAX_ASSETS:
        raise ValueError("主题信息或资源列表无效")
    files = {}
    total = 0
    for name, encoded in encoded_files.items():
        if not isinstance(name, str) or not 0 < len(name) <= 256 or "\\" in name:
            raise ValueError("主题资源路径无效")
        path = PurePosixPath(name)
        if not path.parts or path.is_absolute() or str(path) != name or ".." in path.parts or any(ord(c) < 32 for c in name):
            raise ValueError("主题资源必须位于自己的目录内")
        if path.parts[0] in {"render.typ", "render.png"}:
            raise ValueError("主题资源名与渲染输出冲突")
        if not isinstance(encoded, str) or len(encoded) > 4 * ((MAX_ASSET_BYTES + 2) // 3):
            raise ValueError("主题资源过大")
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("主题资源不是有效的 Base64") from exc
        total += len(raw)
        if total > MAX_ASSET_BYTES:
            raise ValueError("单主题资源总量超过 2 MiB")
        files[name] = raw
    fallback = next((item for item in TEMPLATE_CATALOG if item["id"] == identity), {})
    catalog = {"id": identity}
    for key, default, limit in (
        ("name", identity, 64),
        ("description", "Git 仓库主题", 256),
        ("default_brand_name", fallback.get("default_brand_name", identity), 64),
        ("default_subtitle", fallback.get("default_subtitle", ""), 96),
    ):
        alias = {"default_brand_name": "brand_name", "default_subtitle": "subtitle"}.get(key, key)
        text = metadata.get(alias, metadata.get(key, default))
        if not isinstance(text, str) or len(text) > limit or any(not c.isprintable() for c in text):
            raise ValueError(f"主题信息 {alias} 无效或过长")
        catalog[key] = text
    avatar = value.get("avatar")
    if avatar is None:
        avatar = next((name for name in ("avatar.webp", "avatar.png", "avatar.jpg", "avatar.jpeg") if name in files), None)
    if avatar is not None and (not isinstance(avatar, str) or avatar not in files):
        raise ValueError("指定的主题头像不存在")
    catalog["has_default_avatar"] = avatar is not None
    return ThemePackage(identity, source, catalog, files, avatar)


# Authors may override any of these values, or provide a completely new layout.
# Only the Markdown body needs a stable set of color names to render reliably.
THEME_PRELUDE = '''
#let canvas = rgb("#eef2f8")
#let paper = rgb("#fafdff")
#let soft = rgb("#f2f6fc")
#let ink = rgb("#203045")
#let inksoft = rgb("#70829b")
#let muted = rgb("#70829b")
#let linecolor = rgb("#d9e3ef")
#let accent = rgb("#6dc8ff")
#let accentsoft = rgb("#e9f3ff")
#let accentdeep = rgb("#28658e")
#let asidebg = rgb("#142e46")
#let asideink = rgb("#eef6ff")
#let asideaccent = rgb("#80cfff")
#let asidelabel = rgb("#e6c58d")
#let quotebg = rgb("#edf8f2")
#let quoteink = rgb("#2c5140")
#let quoteline = rgb("#65a88a")
#let codebg = rgb("#25262e")
#let codehead = rgb("#333541")
#let codeink = rgb("#edf0fb")
#let tableheadbg = rgb("#e1edf9")
#let brand = {{BRAND}}
#let subtitle = {{SUBTITLE}}
#let version = {{VERSION}}
#let footer = {{FOOTER}}
#let av = {{SHOW_AVATAR}}
#let ft = {{SHOW_FOOTER}}
#set page(width: 360pt, height: auto, margin: (x: 14pt, y: 17pt), fill: canvas)
#set text(font: ("Source Han Sans SC", "Noto Sans CJK SC", "Noto Color Emoji"), size: 12pt, fill: ink)
#set par(leading: 0.7em, spacing: 0pt)
'''

VALIDATION_MARKDOWN = '''     主题试渲染，**加粗与旁白**。

# 中文标题 English 123 📡

普通正文、*斜体*、~~删除线~~、[链接](https://example.com)、`行内代码`。

> 引用与 **强调**。

- [x] 已完成
- [ ] 待完成

| 项目 | 状态 |
|---|---|
| 正文 | ✅ 正常 |

```python
print("中文代码")
```
'''

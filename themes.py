"""Public, strict style schema shared by the renderer and HTTP service.

Avatar bytes belong to the HTTP layer. No template name or style field is ever
used as a filesystem path, and normalized styles contain only presentation data.
"""

from __future__ import annotations


TEMPLATE_CATALOG = [
    {"id": "codex", "name": "Codex 经典", "description": "兼容默认的蓝白研究卡片，横向品牌栏与柔和圆角。", "default_brand_name": "Amadeus", "default_subtitle": "powered by Astrbot", "has_default_avatar": True},
    {"id": "miku", "name": "初音未来", "description": "青绿电子舞台、五线谱与耳机式头像框；非官方主题。", "default_brand_name": "初音未来", "default_subtitle": "HATSUNE MIKU · VIRTUAL SINGER", "has_default_avatar": True},
    {"id": "genshin", "name": "原神", "description": "羊皮纸冒险手册、星纹罗盘与衬线正文；非官方主题。", "default_brand_name": "派蒙", "default_subtitle": "AD ASTRA ABYSSOSQUE", "has_default_avatar": True},
    {"id": "starrail", "name": "星穹铁道", "description": "星轨、列车与车票档案结构；非官方主题。", "default_brand_name": "帕姆", "default_subtitle": "TRAILBLAZER · ASTRAL EXPRESS", "has_default_avatar": True},
    {"id": "zzz", "name": "绝区零", "description": "黑黄撞色、录像带与伊埃斯；非官方主题。", "default_brand_name": "伊埃斯", "default_subtitle": "NEW ERIDU · RANDOM PLAY", "has_default_avatar": True},
    {"id": "rio", "name": "蔚蓝档案 · 调月莉音", "description": "黑白红科技档案、几何光环与千年工程网格；非官方主题。", "default_brand_name": "调月莉音", "default_subtitle": "TSUKATSUKI RIO · MILLENNIUM", "has_default_avatar": True},
]
_TEMPLATE_IDS = frozenset(item["id"] for item in TEMPLATE_CATALOG)
_THEME_DEFAULTS = {
    item["id"]: {"brand_name": item["default_brand_name"], "subtitle": item["default_subtitle"]}
    for item in TEMPLATE_CATALOG
}
# Paths are selected from a fixed map, never formed from an untrusted request.
THEME_AVATAR_FILES = {
    "miku": "miku.webp", "genshin": "genshin.webp", "starrail": "starrail.webp",
    "zzz": "zzz.webp", "rio": "rio.webp",
}
_DEFAULTS = {
    "template": "codex",
    "brand_name": "Amadeus",
    "subtitle": "powered by Astrbot",
    "show_avatar": True,
    "show_footer": True,
}


def normalize_style(style: dict | None, theme=None) -> dict:
    """Return independent defaults plus validated overrides, or raise ValueError.

    ``avatar_base64`` is accepted only as a string for callers sharing the wire
    schema; validation/decoding is the service's responsibility. It is deliberately
    discarded here so encoded image data never enters generated Typst source.
    Unknown keys are rejected, including arbitrary image/template path fields.
    """
    if style is None and theme is None:
        return dict(_DEFAULTS)
    if style is None:
        style = {"template": theme.id}
    if not isinstance(style, dict):
        raise ValueError("style 必须是对象")
    if any(key not in _DEFAULTS and key != "avatar_base64" for key in style):
        raise ValueError("未知 style 字段")
    if "avatar_base64" in style and not isinstance(style["avatar_base64"], str):
        raise ValueError("avatar_base64 必须是字符串")
    template = style.get("template", "codex")
    if not isinstance(template, str) or (template not in _TEMPLATE_IDS and (theme is None or theme.id != template)):
        raise ValueError("未知 template")
    if theme is not None and theme.id != template:
        raise ValueError("主题源码与选中的模板 ID 不一致")
    result = dict(_DEFAULTS)
    if theme is None:
        result.update(_THEME_DEFAULTS[template])
    else:
        result.update({"brand_name": theme.catalog["default_brand_name"], "subtitle": theme.catalog["default_subtitle"]})
        result["template"] = template
    result.update({key: value for key, value in style.items() if key in _DEFAULTS})
    for key, limit in (("brand_name", 64), ("subtitle", 96)):
        if not isinstance(result[key], str) or len(result[key]) > limit:
            raise ValueError(f"{key} 必须是长度不超过 {limit} 的字符串")
    for key in ("show_avatar", "show_footer"):
        if type(result[key]) is not bool:
            raise ValueError(f"{key} 必须是布尔值")
    return result


__all__ = ["TEMPLATE_CATALOG", "THEME_AVATAR_FILES", "normalize_style"]

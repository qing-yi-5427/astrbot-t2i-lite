"""Style schema, byte-compatible defaults, and real Typst rendering regressions.

Rendering checks skip if the Typst CLI is unavailable. For bundled local fonts,
set TYPST_FONT_PATHS to the repository's fonts directory before running tests.
"""

import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from markdown_typst import _style_literal, to_typst
from themes import TEMPLATE_CATALOG, normalize_style


ROOT = Path(__file__).resolve().parents[1]
IDS = ("codex", "miku", "genshin", "starrail", "zzz", "rio")
SAMPLE = "# 中文标题\n\n> 引用 **重点**\n\n- [x] 完成\n\n```python\nprint(1)\n```"


class StyleSchemaTests(unittest.TestCase):
    def test_catalog_is_complete_and_descriptive(self):
        self.assertEqual(tuple(item["id"] for item in TEMPLATE_CATALOG), IDS)
        for item in TEMPLATE_CATALOG:
            self.assertEqual(set(item), {"id", "name", "description", "default_brand_name", "default_subtitle", "has_default_avatar"})
            self.assertTrue(item["name"])
            self.assertTrue(item["description"])
            self.assertTrue(item["has_default_avatar"])
            self.assertEqual(normalize_style({"template": item["id"]})["brand_name"], item["default_brand_name"])
            self.assertEqual(normalize_style({"template": item["id"]})["subtitle"], item["default_subtitle"])

    def test_defaults_are_independent_and_input_is_not_mutated(self):
        expected = {"template": "codex", "brand_name": "Amadeus", "subtitle": "powered by Astrbot", "show_avatar": True, "show_footer": True}
        self.assertEqual(normalize_style(None), expected)
        self.assertEqual(normalize_style({}), expected)
        source = {"template": "rio", "brand_name": "中文品牌"}
        result = normalize_style(source)
        result["show_footer"] = False
        self.assertEqual(source, {"template": "rio", "brand_name": "中文品牌"})
        self.assertEqual(normalize_style(None), expected)

    def test_all_ids_and_exact_boundary_strings_are_valid(self):
        for template in IDS:
            style = normalize_style({"template": template, "brand_name": "中" * 64, "subtitle": "文" * 96, "show_avatar": False, "show_footer": False})
            self.assertEqual(style["template"], template)
        self.assertEqual(normalize_style({"brand_name": "", "subtitle": ""})["brand_name"], "")

    def test_theme_defaults_and_explicit_overrides(self):
        expected = {
            "miku": ("初音未来", "HATSUNE MIKU · VIRTUAL SINGER"),
            "genshin": ("派蒙", "AD ASTRA ABYSSOSQUE"),
            "starrail": ("帕姆", "TRAILBLAZER · ASTRAL EXPRESS"),
            "zzz": ("伊埃斯", "NEW ERIDU · RANDOM PLAY"),
            "rio": ("调月莉音", "TSUKATSUKI RIO · MILLENNIUM"),
        }
        for template, (brand, subtitle) in expected.items():
            with self.subTest(template=template):
                selected = normalize_style({"template": template})
                self.assertEqual((selected["brand_name"], selected["subtitle"]), (brand, subtitle))
                overridden = normalize_style({"template": template, "brand_name": "自定义", "subtitle": ""})
                self.assertEqual((overridden["brand_name"], overridden["subtitle"]), ("自定义", ""))
                self.assertIn(_style_literal(brand), to_typst("正文", style={"template": template}))
        for retired in ("midnight", "sakura", "forest", "paper"):
            with self.assertRaises(ValueError):
                normalize_style({"template": retired})

    def test_invalid_top_level_types(self):
        for style in (False, True, "codex", [], 0, 1):
            with self.subTest(style=style), self.assertRaises(ValueError):
                normalize_style(style)

    def test_invalid_fields_and_traversal(self):
        for style in (
            {"template": "../codex_style"}, {"template": "/etc/passwd"},
            {"template": "Codex"}, {"template": ""}, {"template": None},
            {"template": []}, {"template": True},
            {"brand_name": "x" * 65}, {"subtitle": "x" * 97},
            {"brand_name": None}, {"brand_name": 0}, {"subtitle": []},
            {"show_avatar": "false"}, {"show_avatar": 0}, {"show_avatar": None},
            {"show_footer": 1}, {"show_footer": "true"},
            {"avatar_path": "/etc/passwd"}, {"unknown": True},
            {"avatar_base64": 123},
        ):
            with self.subTest(style=style), self.assertRaises(ValueError):
                normalize_style(style)

    def test_avatar_wire_data_never_enters_normalized_style_or_source(self):
        encoded = "secret-encoded-avatar-data"
        style = {"template": "miku", "avatar_base64": encoded}
        self.assertNotIn("avatar_base64", normalize_style(style))
        self.assertNotIn(encoded, to_typst("正文", style=style))
        self.assertEqual(style["avatar_base64"], encoded)


class ThemeSourceTests(unittest.TestCase):
    def test_every_formal_theme_uses_source_han_sans(self):
        for template in IDS:
            source = to_typst(SAMPLE, style={"template": template})
            self.assertIn('font: ("Source Han Sans SC",', source)
            self.assertNotIn('"Noto Serif SC"', source)

    def test_six_structurally_distinct_layouts_keep_markdown(self):
        sources = []
        for template in IDS:
            source = to_typst(SAMPLE + "\n\n| 中文 | 状态 |\n|---|---|\n| 项目 | ✅ |", style={"template": template})
            sources.append(source)
            for marker in ('text("中文标题")', 'text("重点")', '#table(', '#raw("print(1)"', '<polyline'):
                self.assertIn(marker, source)
        self.assertEqual(len(set(sources)), 6)
        for index, marker in enumerate(("radius: 8pt", '"MIKU / VIRTUAL SINGER"', '"TEYVAT / 旅途手记"', '"ASTRAL EXPRESS"', '"ZZZ / NEW ERIDU"', '"MILLENNIUM / SEMINAR"')):
            self.assertIn(marker, sources[index])

    def test_user_data_is_quoted_and_replaced_once(self):
        injection = '"] #read("/etc/passwd") {{CONTENT}} {{FOOTER}}'
        subtitle = "{{BRAND}} {{SUBTITLE}} \\ #include(\"evil.typ\")"
        for template in IDS:
            result = to_typst("{{VERSION}} {{BRAND}} {{CONTENT}}", "{{SUBTITLE}}", "{{BRAND}}", style={"template": template, "brand_name": injection, "subtitle": subtitle})
            self.assertIn(_style_literal(injection), result)
            self.assertIn(_style_literal(subtitle), result)
            self.assertIn('text("{{VERSION}} {{BRAND}} {{CONTENT}}")', result)
            self.assertIn('"回复模型：{{BRAND}}"', result)
            self.assertNotIn('#read("/etc/passwd")', result)

    def test_control_characters_are_valid_typst_strings(self):
        self.assertEqual(_style_literal('"\\\n\t\r\x00\x08\x0c\u2028\u2029'), '"\\"\\\\\\n\\t\\r\\u{0}\\u{8}\\u{c}\\u{2028}\\u{2029}"')

    def test_aside_label_uses_selected_brand_and_preserves_user_text(self):
        for template in IDS:
            brand = normalize_style({"template": template})["brand_name"]
            label = "AMADEUS / 个人旁白" if template == "codex" else brand + " / 个人旁白"
            source = to_typst("     普通文字 **重点**\n\n正文 AMADEUS / 个人旁白", legacy_reply_prefix=True, style={"template": template})
            self.assertIn(f'#text({_style_literal(label)}, size: 8pt, fill: asidelabel', source)
            self.assertIn('text("正文 AMADEUS / 个人旁白")', source)
            if template != "codex":
                self.assertNotIn('#text("AMADEUS / 个人旁白", size: 8pt', source)

    def test_custom_aside_brand_is_escaped_as_data(self):
        brand = '"] #read("/etc/passwd")'
        source = to_typst("     当前旁白", legacy_reply_prefix=True, style={"template": "zzz", "brand_name": brand})
        self.assertIn(f'#text({_style_literal(brand + " / 个人旁白")}, size: 8pt', source)
        self.assertNotIn('#read("/etc/passwd")', source)

    def test_model_footer_wins_over_custom_brand(self):
        result = to_typst("正文", model_name="model-name", style={"template": "genshin", "brand_name": "自定义品牌"})
        self.assertIn('"回复模型：model-name"', result)
        self.assertNotIn('"自定义品牌  ·  powered by Astrbot"', result)

    def test_custom_footer_uses_custom_brand_and_subtitle(self):
        result = to_typst("正文", style={"brand_name": "我的品牌", "subtitle": "副标题"})
        self.assertIn('"我的品牌  ·  副标题"', result)
        self.assertNotIn('"AMADEUS  ·  POWERED BY ASTRBOT"', result)


@unittest.skipUnless(shutil.which("typst"), "Typst CLI is not available")
class ThemeRenderTests(unittest.TestCase):
    def test_default_headers_use_sixty_to_seventy_five_percent_of_previous_height(self):
        # Measured on deployed 2.0.2, excluding page margin and body inset.
        baseline = {"codex": 60.5, "miku": 190.597, "genshin": 170.3509,
                    "starrail": 169.529, "zzz": 151.995, "rio": 187.2738571428571}
        offsets = {"codex": 36, "miku": 31, "genshin": 33,
                   "starrail": 33, "zzz": 31, "rio": 32}
        for template in IDS:
            with self.subTest(template=template), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = to_typst("HEADER_PROBE", style={"template": template})
                source = source.replace('#text("HEADER_PROBE")',
                                        '#context [#metadata(here().position().y.pt()) <header-probe>]')
                (root / "render.typ").write_text(source, encoding="utf-8")
                shutil.copyfile(ROOT / "assets" / "avatar.webp", root / "avatar.webp")
                result = subprocess.run(
                    ["typst", "query", str(root / "render.typ"), "<header-probe>", "--field", "value"],
                    capture_output=True, text=True, check=True, timeout=25,
                )
                height = json.loads(result.stdout)[0] - offsets[template]
                self.assertGreaterEqual(height / baseline[template], 0.60)
                self.assertLessEqual(height / baseline[template], 0.75)

    @staticmethod
    def render(source, *, avatar=True):
        from PIL import Image
        with tempfile.TemporaryDirectory(prefix="t2i-theme-test-") as directory:
            root = Path(directory)
            if avatar:
                shutil.copyfile(ROOT / "assets" / "avatar.webp", root / "avatar.webp")
            (root / "render.typ").write_text(source, encoding="utf-8")
            result = subprocess.run(
                ["typst", "compile", "--format", "png", "--ppi", "144", str(root / "render.typ"), str(root / "render.png")],
                capture_output=True, text=True, timeout=25,
            )
            if result.returncode:
                raise AssertionError(result.stderr)
            with Image.open(root / "render.png") as image:
                return image.convert("RGB").copy()

    def test_all_themes_compile_rich_chinese_markdown(self):
        text = "     旁白 **强调**\n\n" + SAMPLE + "\n\n| 项目 | 状态 |\n|---|---|\n| 中文 | ✅ 正常 |\n\n> - [ ] 引用任务\n>\n> ```python\n> print('中文')\n> ```"
        images = []
        for template in IDS:
            with self.subTest(template=template):
                image = self.render(to_typst(text, "v4.28.2", legacy_reply_prefix=True, style={"template": template}))
                self.assertEqual(image.width, 720)
                self.assertGreater(image.height, 250)
                images.append(image)
        self.assertEqual(len({image.getpixel((0, 0)) for image in images}), 6)
        self.assertGreaterEqual(len({image.height for image in images}), 4)

    def test_avatar_off_compiles_without_image_and_shrinks_header(self):
        for template in IDS:
            with self.subTest(template=template):
                visible = self.render(to_typst("正文", style={"template": template}))
                hidden = self.render(to_typst("正文", style={"template": template, "show_avatar": False}), avatar=False)
                self.assertLessEqual(hidden.height, visible.height)
                self.assertNotEqual(hidden.tobytes(), visible.tobytes())

    def test_footer_off_really_removes_footer_height(self):
        for template in IDS:
            with self.subTest(template=template):
                visible = self.render(to_typst("正文", style={"template": template}))
                hidden = self.render(to_typst("正文", style={"template": template, "show_footer": False}))
                self.assertLess(hidden.height, visible.height)

    def test_injection_and_control_strings_compile_as_data(self):
        style = {"template": "rio", "brand_name": '"] #read("/etc/passwd") {{CONTENT}}', "subtitle": "换行\n制表\t引号\"\\\x00\x08\x0c\u2028\u2029", "show_avatar": False}
        image = self.render(to_typst("正文 #read(\"/etc/passwd\") {{FOOTER}}", style=style), avatar=False)
        self.assertEqual(image.width, 720)

    def test_default_pixels_equal_original_template(self):
        import markdown_typst as converter
        blocks = converter._render_nodes(converter._parse_markdown(SAMPLE))
        values = {"VERSION": json.dumps("v4.28.2"), "FOOTER": json.dumps("回复模型：test", ensure_ascii=False), "CONTENT": blocks}
        legacy = re.sub(r"\{\{(VERSION|FOOTER|CONTENT)\}\}", lambda match: values[match[1]], (ROOT / "codex_style.typ").read_text(encoding="utf-8"))
        expected = self.render(legacy)
        actual = self.render(to_typst(SAMPLE, "v4.28.2", "test", style={}))
        self.assertEqual(actual.size, expected.size)
        self.assertEqual(actual.tobytes(), expected.tobytes())


if __name__ == "__main__":
    unittest.main()

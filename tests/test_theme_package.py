"""Render flexible Git themes and reject resource access outside their project."""

import base64
import io
import json
import shutil
import unittest
from pathlib import Path

from PIL import Image

import service
from markdown_typst import to_typst
from theme_package import parse_theme_package
from themes import normalize_style


def package(source="{{CONTENT}}", **extra):
    return {"id": "custom-theme", "source": source, **extra}


class ThemePackageTests(unittest.TestCase):
    def test_only_source_and_id_are_required(self):
        theme = parse_theme_package(package())
        self.assertEqual(theme.catalog["name"], "custom-theme")
        self.assertEqual(theme.files, {})
        self.assertIsNone(theme.avatar)
        self.assertEqual(normalize_style({"template": theme.id}, theme)["template"], theme.id)

    def test_unknown_metadata_and_layout_settings_are_not_rejected(self):
        theme = parse_theme_package(package(meta={"notes": {"layout": "anything"}, "brand_name": "自定义"}))
        self.assertEqual(theme.catalog["default_brand_name"], "自定义")

    def test_builtin_identity_has_compatible_defaults(self):
        theme = parse_theme_package({"id": "genshin", "source": "{{CONTENT}}"})
        self.assertEqual(theme.catalog["default_brand_name"], "派蒙")

    def test_identity_does_not_become_a_server_path(self):
        for identity in ("../x", "/tmp/x", "a/b", "A", "a" * 49, [], None):
            with self.subTest(identity=identity), self.assertRaises(ValueError):
                parse_theme_package({"id": identity, "source": "{{CONTENT}}"})

    def test_missing_body_and_oversize_source_are_rejected(self):
        for source in (None, "#text(\"missing\")", "{{CONTENT}}" + "a" * (256 * 1024)):
            with self.subTest(source=str(source)[:20]), self.assertRaises(ValueError):
                parse_theme_package(package(source))

    def test_resources_are_regular_relative_project_paths(self):
        for name in (".", "/etc/passwd", "../x", "assets/../../x", "assets//x", "a\\b", "render.typ", "render.png", "x\x00y"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                parse_theme_package(package(files={name: base64.b64encode(b"data").decode()}))
        theme = parse_theme_package(package(files={"assets/part.typ": base64.b64encode(b"#let x = 1").decode()}))
        self.assertEqual(theme.files["assets/part.typ"], b"#let x = 1")

    def test_invalid_encoding_and_missing_avatar_are_rejected(self):
        for extra in ({"files": {"assets/a": "bad!"}}, {"avatar": "missing.png"}, {"schema": True}, {"meta": {"name": []}}):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                parse_theme_package(package(**extra))

    def test_reply_metadata_is_still_data_and_is_replaced_once(self):
        theme = parse_theme_package(package("#text(brand)\n{{CONTENT}}\n#text(footer)", meta={"brand_name": '{{CONTENT}} "] #read("/etc/passwd")'}))
        source = to_typst("正文 {{BRAND}}", model_name="model-real", style={"template": theme.id}, theme=theme)
        self.assertIn('text("正文 {{BRAND}}")', source)
        self.assertIn('"回复模型：model-real"', source)
        self.assertIn('\\"] #read(\\"/etc/passwd\\")', source)
        with self.assertRaises(ValueError):
            to_typst("正文", style={"template": "other"}, theme=theme)


@unittest.skipUnless(shutil.which("typst"), "Typst is required")
class RealGitThemeTests(unittest.TestCase):
    def test_minimal_theme_renders_rich_markdown_without_a_palette(self):
        data, mime = service._render({"tmpl": "", "tmpldata": {"text": "# 中文 📡\n\n> 引用 **重点**\n\n- [x] 完成\n\n| 项目 | 状态 |\n|---|---|\n| 中文 | ✅ |\n\n```python\nprint(1)\n```", "t2i_theme": package()}, "options": {"type": "png"}})
        self.assertEqual(mime, "image/png")
        with Image.open(io.BytesIO(data)) as image:
            self.assertEqual(image.width, 720)

    def test_page_width_is_a_design_choice_not_a_schema_restriction(self):
        theme = parse_theme_package(package("#set page(width: 400pt)\n{{CONTENT}}"))
        data, _ = service._compile_image("正文", "v", "png", 85, theme=theme)
        with Image.open(io.BytesIO(data)) as image:
            self.assertEqual(image.width, 800)

    def test_theme_can_import_its_own_local_assets(self):
        theme = parse_theme_package(package('#import "assets/header.typ": title\n#title\n{{CONTENT}}', files={"assets/header.typ": base64.b64encode('#let title = [本地主题模块]'.encode()).decode()}))
        data, _ = service._compile_image("正文", "v", "png", 85, theme=theme)
        self.assertTrue(data.startswith(b"\x89PNG"))

    def test_theme_cannot_read_outside_its_project(self):
        theme = parse_theme_package(package('#read("/etc/passwd")\n{{CONTENT}}'))
        with self.assertRaisesRegex(service.RenderError, "排版失败"):
            service._compile_image("正文", "v", "png", 85, theme=theme)

    def test_six_published_reference_folders_render(self):
        root = Path("/reference-themes")
        if not root.is_dir():
            self.skipTest("Reference theme mount is unavailable")
        for folder in root.iterdir():
            if not (folder / "theme.typ").is_file():
                continue
            with self.subTest(theme=folder.name):
                value = {"id": folder.name, "source": (folder / "theme.typ").read_text(), "meta": json.loads((folder / "theme.json").read_text()), "files": {"avatar.webp": base64.b64encode((folder / "avatar.webp").read_bytes()).decode()}}
                theme = parse_theme_package(value)
                data, _ = service._compile_image("     旁白 **强调**\n\n# 标题\n\n正文", "v", "png", 85, model_name="actual-model", legacy_reply_prefix=True, theme=theme)
                with Image.open(io.BytesIO(data)) as image:
                    self.assertEqual(image.width, 720)


if __name__ == "__main__":
    unittest.main()

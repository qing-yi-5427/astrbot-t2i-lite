"""Integration contract for formal themes, bounded avatars and clean footers."""

import base64
import io
import json
import shutil
import subprocess
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from PIL.PngImagePlugin import PngInfo

import service
from themes import TEMPLATE_CATALOG, normalize_style


IDS = ("codex", "miku", "genshin", "starrail", "zzz", "rio")


def image_bytes(fmt="PNG", size=(40, 40), color="#2177bb", **kwargs):
    output = io.BytesIO()
    Image.new("RGB", size, color).save(output, format=fmt, **kwargs)
    return output.getvalue()


def payload(style=None, *, text="中文正文", template='<div class="brand-name">Amadeus</div>'):
    data = {"text": text, "version": "v4.28.2", "model_name": "test-model"}
    if style is not None:
        data["t2i_style"] = style
    return {"tmpl": template, "tmpldata": data, "options": {"type": "png"}}


class AvatarValidationTests(unittest.TestCase):
    def test_png_jpeg_webp_become_clean_webp(self):
        for fmt in ("PNG", "JPEG", "WEBP"):
            with self.subTest(fmt=fmt):
                result = service._style_avatar(base64.b64encode(image_bytes(fmt)).decode())
                with Image.open(io.BytesIO(result)) as image:
                    self.assertEqual(image.format, "WEBP")
                    self.assertEqual(image.size, (40, 40))
                    image.verify()

    def test_empty_means_default_and_data_urls_are_supported(self):
        self.assertIsNone(service._style_avatar(None))
        self.assertIsNone(service._style_avatar(""))
        encoded = base64.b64encode(image_bytes()).decode()
        self.assertIsNotNone(service._style_avatar("data:image/png;base64," + encoded))

    def test_bad_avatars_are_rejected_without_network_or_path_reads(self):
        invalid = [0, True, [], {}, "not base64!", "https://example.com/avatar.png", "/etc/passwd", "data:image/svg+xml;base64,PHN2Zy8+", "data:image/png;base64,", "A" * (4 * ((512000 + 2) // 3) + 4)]
        invalid += [base64.b64encode(raw).decode() for raw in (b"<svg/>", image_bytes("GIF"), image_bytes(size=(1025, 2)), b"x" * 512001)]
        for value in invalid:
            with self.subTest(value=str(value)[:80]), self.assertRaises(service.RenderError):
                service._style_avatar(value)

    def test_raster_metadata_is_dropped_and_dimensions_bounded(self):
        info = PngInfo()
        info.add_text("secret", "private metadata")
        encoded = base64.b64encode(image_bytes(size=(1000, 600), pnginfo=info)).decode()
        clean = service._style_avatar(encoded)
        self.assertNotIn(b"private metadata", clean)
        with Image.open(io.BytesIO(clean)) as image:
            self.assertEqual(image.size, (512, 307))
            self.assertNotIn("exif", image.info)


class SeriesRoutingTests(unittest.TestCase):
    def test_series_defaults_ignore_legacy_html_avatar(self):
        for template in IDS[1:]:
            for avatar_field in ({}, {"avatar_base64": ""}):
                with self.subTest(template=template, avatar_field=avatar_field), patch.object(service, "_template_avatar", side_effect=AssertionError("Must not parse old HTML avatar")), patch.object(service, "_compile_image", return_value=(b"image", "image/png")) as compile_image, patch.object(service, "_proxy_unsupported", side_effect=AssertionError("Style must stay local")):
                    service._render(payload({"template": template, **avatar_field}))
                    self.assertIsNone(compile_image.call_args.args[4])
                    self.assertEqual(compile_image.call_args.kwargs["style"], normalize_style({"template": template}))

    def test_custom_avatar_has_highest_priority_for_every_theme(self):
        encoded = base64.b64encode(image_bytes()).decode()
        for template in IDS:
            with self.subTest(template=template), patch.object(service, "_template_avatar", side_effect=AssertionError("Custom beats HTML")), patch.object(service, "_compile_image", return_value=(b"image", "image/png")) as compile_image:
                service._render(payload({"template": template, "avatar_base64": encoded}))
                self.assertIsInstance(compile_image.call_args.args[4], bytes)
                self.assertNotIn("avatar_base64", compile_image.call_args.kwargs["style"])

    def test_codex_legacy_and_explicit_styles_keep_html_avatar(self):
        for style in (None, {}, {"template": "codex"}, {"template": "codex", "avatar_base64": ""}):
            with self.subTest(style=style), patch.object(service, "_template_avatar", return_value=b"old-avatar"), patch.object(service, "_compile_image", return_value=(b"image", "image/png")) as compile_image:
                service._render(payload(style))
                self.assertEqual(compile_image.call_args.args[4], b"old-avatar")

    def test_defaults_resolve_only_fixed_repo_asset_paths(self):
        root = Path(service.__file__).resolve().parent
        self.assertEqual(service._default_avatar_path("codex"), root / "assets" / "avatar.webp")
        for template in IDS[1:]:
            self.assertEqual(service._default_avatar_path(template), root / "assets" / "themes" / (template + ".webp"))
        for template in ("../avatar", "/etc/passwd", "midnight", ""):
            with self.assertRaises(service.RenderError):
                service._default_avatar_path(template)

    def test_invalid_styles_fail_before_compile_or_proxy(self):
        styles = [{"template": "../rio"}, {"template": "midnight"}, {"brand_name": "x" * 65}, {"subtitle": "x" * 97}, {"show_footer": 0}, {"show_avatar": "false"}, {"avatar_path": "/etc/passwd"}, {"avatar_base64": None}, {"avatar_base64": "bad!"}]
        for style in styles:
            with self.subTest(style=style), patch.object(service, "_compile_image", side_effect=AssertionError("Invalid style must not compile")), patch.object(service, "_proxy_unsupported", side_effect=AssertionError("Invalid style must not proxy")), self.assertRaises(service.RenderError):
                service._render(payload(style))

    def test_explicit_style_is_local_even_for_unrelated_html(self):
        with patch.object(service, "_proxy_unsupported", side_effect=AssertionError("No proxy")), patch.object(service, "_compile_image", return_value=(b"image", "image/png")) as compile_image:
            service._render(payload({"template": "rio"}, template="<div>other template</div>"))
            self.assertFalse(compile_image.call_args.kwargs["legacy_reply_prefix"])
        with self.assertRaises(service.RenderError):
            service._render(payload({"template": "rio"}, text=None))


class HttpStyleProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = service.ThreadingHTTPServer(("127.0.0.1", 0), service.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def request(self, method, path, body=None):
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            encoded = json.dumps(body).encode() if body is not None else None
            connection.request(method, path, body=encoded, headers={"Content-Type": "application/json"} if encoded else {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_health_protocol_on_both_routes(self):
        for route in ("/health", "/text2img/health"):
            status, headers, body = self.request("GET", route)
            self.assertEqual(status, 200)
            self.assertIn("AstrBotT2ILite/2.0", headers["Server"])
            self.assertEqual(json.loads(body), {"status": "ok", "engine": "typst", "style_protocol": 1, "theme_protocol": 1, "service_version": "2.1.0-themes"})

    def test_catalog_routes_have_six_safe_named_defaults(self):
        for route in ("/templates", "/text2img/templates"):
            status, headers, body = self.request("GET", route)
            self.assertEqual(status, 200)
            self.assertIn("application/json", headers["Content-Type"])
            result = json.loads(body)
            self.assertEqual(result, {"templates": TEMPLATE_CATALOG, "default": "codex", "style_protocol": 1, "theme_protocol": 1, "service_version": "2.1.0-themes"})
            self.assertEqual(tuple(item["id"] for item in result["templates"]), IDS)
            for item in result["templates"]:
                self.assertTrue(item["name"])
                self.assertTrue(item["default_brand_name"])
                self.assertTrue(item["default_subtitle"])
                self.assertIs(item["has_default_avatar"], True)
            for private in (b"/Users/", b"/app/", b"avatar_base64", b"avatar_path", b"assets/"):
                self.assertNotIn(private, body)

    def test_post_accepts_every_theme_and_can_retrieve_cached_image(self):
        for template in IDS:
            request = payload({"template": template})
            with patch.object(service, "_compile_image", return_value=(b"fake-png", "image/png")):
                status, headers, body = self.request("POST", "/text2img/generate", request)
                self.assertEqual((status, body), (200, b"fake-png"))
                self.assertEqual(headers["Content-Type"], "image/png")
        request["json"] = True
        with patch.object(service, "_compile_image", return_value=(b"cached-png", "image/png")):
            status, _, body = self.request("POST", "/text2img/generate", request)
        self.assertEqual(status, 200)
        key = json.loads(body)["data"]["id"]
        self.assertTrue(key.startswith("data/"))
        status, _, body = self.request("GET", "/text2img/" + key)
        self.assertEqual((status, body), (200, b"cached-png"))

    @unittest.skipUnless(shutil.which("typst"), "Typst CLI is not available")
    def test_real_http_generation_for_all_six_themes(self):
        for template in IDS:
            with self.subTest(template=template):
                status, headers, body = self.request("POST", "/text2img/generate", payload({"template": template}))
                self.assertEqual(status, 200, body[:500])
                self.assertEqual(headers["Content-Type"], "image/png")
                with Image.open(io.BytesIO(body)) as image:
                    self.assertEqual(image.width, 720)
                    image.verify()

    def test_bad_requests_report_422_not_500_and_never_proxy(self):
        for style in ({"template": "unknown"}, {"template": "../miku"}, {"show_avatar": 1}, {"unknown": "x"}, {"avatar_base64": "/etc/passwd"}):
            with patch.object(service, "_proxy_unsupported", side_effect=AssertionError("No proxy")), patch.object(service, "_compile_image", side_effect=AssertionError("No compile")):
                status, _, body = self.request("POST", "/text2img/generate", payload(style))
                self.assertEqual(status, 422)
                self.assertIn("error", json.loads(body))
        for value in (None, "rio", [], False):
            request = payload()
            request["tmpldata"]["t2i_style"] = value
            self.assertEqual(self.request("POST", "/text2img/generate", request)[0], 422)


@unittest.skipUnless(shutil.which("typst"), "Typst CLI is not available")
class RealSeriesServiceTests(unittest.TestCase):
    def test_requested_font_is_registered_with_typst(self):
        result = subprocess.run(["typst", "fonts"], capture_output=True, text=True, check=True)
        self.assertIn("Source Han Sans SC", result.stdout.splitlines())

    def render(self, template, **style):
        data, mime = service._render(payload({"template": template, **style}))
        self.assertEqual(mime, "image/png")
        with Image.open(io.BytesIO(data)) as image:
            self.assertEqual(image.width, 720)
            self.assertLessEqual(image.height, service.MAX_IMAGE_HEIGHT)
            return image.convert("RGB").copy()

    def test_all_default_assets_are_shipped_valid_and_bounded(self):
        for template in IDS:
            path = service._default_avatar_path(template)
            with self.subTest(template=template):
                self.assertTrue(path.is_file(), f"Missing shipped default avatar for {template}")
                self.assertLessEqual(path.stat().st_size, service.MAX_AVATAR_BYTES)
                with Image.open(path) as image:
                    self.assertEqual(image.format, "WEBP")
                    self.assertLessEqual(max(image.size), service.MAX_AVATAR_DIMENSION)
                    image.verify()
                self.render(template)

    def test_all_avatar_choices_keep_clean_image_height_and_model_footer_toggle(self):
        custom = base64.b64encode(image_bytes()).decode()
        for template in IDS:
            with self.subTest(template=template):
                default = self.render(template)
                replacement = self.render(template, avatar_base64=custom)
                self.assertEqual(default.height, replacement.height)
                no_footer = self.render(template, show_footer=False)
                custom_no_footer = self.render(template, show_footer=False, avatar_base64=custom)
                self.assertEqual(no_footer.height, custom_no_footer.height)
                self.assertLess(no_footer.height, default.height)
                with patch.object(service, "_default_avatar_path", side_effect=AssertionError("Hidden avatar must not read material")):
                    self.render(template, show_avatar=False)
                restored = self.render(template, avatar_base64="")
                self.assertEqual(restored.size, default.size)
                self.assertEqual(restored.tobytes(), default.tobytes())

    def test_series_ignores_html_avatar_in_real_images(self):
        encoded_html = base64.b64encode(image_bytes("WEBP", color="#ff0000")).decode()
        html = '<div class="brand-name">Amadeus</div><img class="brand-avatar" src="data:image/webp;base64,' + encoded_html + '">'
        for template in IDS[1:]:
            expected = self.render(template)
            data, _ = service._render(payload({"template": template}, template=html))
            with Image.open(io.BytesIO(data)) as image:
                self.assertEqual(image.convert("RGB").tobytes(), expected.tobytes())


if __name__ == "__main__":
    unittest.main()

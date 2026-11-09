"""AstrBot-compatible, browserless text-to-image endpoint."""

from __future__ import annotations

import io
import base64
import binascii
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from PIL import Image, ImageOps, UnidentifiedImageError

from markdown_typst import to_typst
from themes import TEMPLATE_CATALOG, THEME_AVATAR_FILES, normalize_style
from theme_package import ThemePackage, VALIDATION_MARKDOWN, parse_theme_package


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOG = logging.getLogger("t2i-lite")
MAX_REQUEST_BYTES = 4 * 1024 * 1024
MAX_TEXT_CHARS = 100_000
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_IMAGE_HEIGHT = 25_000
MAX_AVATAR_BYTES = 512_000
MAX_AVATAR_DIMENSION = 1024
COMPILE_TIMEOUT = 25
REMOTE_URL = "https://t2i.soulter.top/text2img/generate"
_SLOTS = threading.BoundedSemaphore(2)
_CACHE: dict[str, tuple[float, bytes, str]] = {}
_CACHE_LOCK = threading.Lock()
_AVATAR_PATTERN = re.compile(r'<img class="brand-avatar" src="data:image/webp;base64,([^"]+)"')


class RenderError(Exception):
    pass


def _template_avatar(template: str) -> bytes | None:
    match = _AVATAR_PATTERN.search(template)
    if not match:
        return None
    try:
        data = base64.b64decode(match.group(1), validate=True)
        if len(data) > 512_000:
            return None
        with Image.open(io.BytesIO(data)) as image:
            if image.format != "WEBP" or image.width > 1024 or image.height > 1024:
                return None
            image.verify()
    except (binascii.Error, UnidentifiedImageError, OSError):
        return None
    return data


def _style_avatar(value: object) -> bytes | None:
    """Decode bounded raster data only; never fetch URLs or read user paths."""
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise RenderError("头像必须是 PNG、JPEG 或 WebP 的 Base64 字符串")
    if value.startswith("data:"):
        match = re.fullmatch(r"data:image/(?:png|jpeg|webp);base64,(.+)", value)
        if not match:
            raise RenderError("不支持的头像数据格式")
        value = match.group(1)
    if len(value) > 4 * ((MAX_AVATAR_BYTES + 2) // 3):
        raise RenderError("头像文件超过 512000 字节")
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as error:
        raise RenderError("头像 Base64 无效") from error
    if not raw or len(raw) > MAX_AVATAR_BYTES:
        raise RenderError("头像文件为空或超过 512000 字节")
    try:
        with Image.open(io.BytesIO(raw)) as image:
            if image.format not in {"PNG", "JPEG", "WEBP"}:
                raise RenderError("头像仅支持 PNG、JPEG 或 WebP")
            if not (0 < image.width <= MAX_AVATAR_DIMENSION and 0 < image.height <= MAX_AVATAR_DIMENSION):
                raise RenderError("头像尺寸不能超过 1024 × 1024")
            image.verify()
        with Image.open(io.BytesIO(raw)) as image:
            # Flatten animation and drop EXIF/ICC metadata before Typst sees it.
            image.seek(0)
            clean = ImageOps.exif_transpose(image).convert("RGBA")
            clean.thumbnail((512, 512))
            buffer = io.BytesIO()
            clean.save(buffer, format="WEBP", quality=90, method=4)
            return buffer.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as error:
        raise RenderError("头像图片损坏或格式无效") from error


def _default_avatar_path(template_id: str) -> Path:
    """Resolve only shipped allowlisted assets, never a user-supplied path."""
    assets = Path(__file__).resolve().parent / "assets"
    if template_id == "codex":
        return assets / "avatar.webp"
    filename = THEME_AVATAR_FILES.get(template_id)
    if filename is None:
        raise RenderError("未知头像主题")
    return assets / "themes" / filename


def _compile_image(text: str, version: str, output_type: str, quality: int, avatar: bytes | None = None, model_name: str = "", *, legacy_reply_prefix: bool = False, style: dict | None = None, theme: ThemePackage | None = None) -> tuple[bytes, str]:
    selected = normalize_style(style, theme)
    kwargs = {"legacy_reply_prefix": legacy_reply_prefix}
    if style is not None:
        kwargs["style"] = style
    if theme is not None:
        if avatar is None and theme.avatar is not None:
            avatar = _style_avatar(base64.b64encode(theme.files[theme.avatar]).decode())
        if avatar is None:
            selected["show_avatar"] = False
        kwargs.update(style=selected, theme=theme)
    source = to_typst(text, version, model_name, **kwargs)
    with tempfile.TemporaryDirectory(prefix="t2i-") as temp_dir:
        input_path = Path(temp_dir) / "render.typ"
        output_path = Path(temp_dir) / "render.png"
        avatar_path = Path(temp_dir) / "avatar.webp"
        if theme is not None:
            for name, raw in theme.files.items():
                asset = Path(temp_dir) / name
                asset.parent.mkdir(parents=True, exist_ok=True)
                asset.write_bytes(raw)
        if selected["show_avatar"]:
            if avatar is None:
                shutil.copyfile(_default_avatar_path(selected["template"]), avatar_path)
            else:
                avatar_path.write_bytes(avatar)
        input_path.write_text(source, encoding="utf-8")
        completed = subprocess.run(
            ["typst", "compile", "--root", temp_dir, "--format", "png", "--ppi", "144", str(input_path), str(output_path)],
            capture_output=True,
            text=True,
            timeout=COMPILE_TIMEOUT,
            check=False,
        )
        if completed.returncode != 0:
            LOG.warning("Typst compile failed: %s", completed.stderr[:1500])
            detail = ": " + completed.stderr[:1200] if theme is not None else ""
            raise RenderError("排版失败" + detail)
        with Image.open(output_path) as image:
            if image.height > MAX_IMAGE_HEIGHT:
                raise RenderError("内容过长，单张图片会影响 QQ 阅读")
            image = image.convert("RGB")
            buffer = io.BytesIO()
            if output_type == "png":
                image.save(buffer, format="PNG", optimize=True)
                mime = "image/png"
            else:
                image.save(buffer, format="JPEG", quality=max(80, min(quality, 92)), optimize=True, subsampling=0)
                mime = "image/jpeg"
        data = buffer.getvalue()
    if len(data) > MAX_IMAGE_BYTES:
        raise RenderError("图片文件过大")
    return data, mime


def _proxy_unsupported(payload: dict) -> tuple[bytes, str]:
    """Keep non-Codex plugin templates working through the prior official service."""
    upstream = dict(payload)
    upstream["json"] = False
    request = Request(
        REMOTE_URL,
        data=json.dumps(upstream, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            content_type = response.headers.get("Content-Type", "").split(";", 1)[0]
            data = response.read(MAX_IMAGE_BYTES + 1)
    except (HTTPError, URLError, TimeoutError) as error:
        raise RenderError("原模板远端渲染失败") from error
    if content_type not in {"image/jpeg", "image/png", "image/webp"} or len(data) > MAX_IMAGE_BYTES:
        raise RenderError("原模板远端未返回有效图片")
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
    except (UnidentifiedImageError, OSError) as error:
        raise RenderError("原模板远端未返回有效图片") from error
    return data, content_type


def _render(payload: dict) -> tuple[bytes, str]:
    data = payload.get("tmpldata")
    if not isinstance(data, dict):
        raise RenderError("缺少 tmpldata")
    text = data.get("text")
    template = payload.get("tmpl", "")
    if not isinstance(template, str):
        raise RenderError("模板格式无效")
    # Explicit style requests stay local: custom avatars and text must not be
    # forwarded to the legacy remote HTML renderer.
    raw_style = data.get("t2i_style")
    explicit_style = "t2i_style" in data
    theme = None
    if "t2i_theme" in data:
        try:
            theme = parse_theme_package(data["t2i_theme"])
        except ValueError as error:
            raise RenderError(str(error)) from error
        if not explicit_style:
            raw_style = {"template": theme.id}
        explicit_style = True
    if explicit_style and not isinstance(raw_style, dict):
        raise RenderError("t2i_style 必须是对象")
    style = None
    avatar = None
    if explicit_style:
        try:
            style = normalize_style(raw_style, theme)
        except (ValueError, TypeError) as error:
            raise RenderError(str(error)) from error
        avatar = _style_avatar(raw_style.get("avatar_base64"))
        if avatar is None and style["template"] == "codex" and theme is None:
            # Codex alone retains old embedded HTML avatar compatibility.
            avatar = _template_avatar(template)
    else:
        avatar = _template_avatar(template)
    # Each series theme resolves its own generated avatar during compilation;
    # legacy HTML avatars must not override those defaults.
    # AstrBot's active Codex template carries this stable brand marker.
    legacy = '<div class="brand-name">Amadeus</div>' in template
    local = isinstance(text, str) and (legacy or explicit_style)
    if explicit_style and not isinstance(text, str):
        raise RenderError("样式渲染需要字符串正文 text")
    if not local:
        try:
            return _proxy_unsupported(payload)
        except RenderError:
            # The former endpoint can reject NAS-originated requests (HTTP 403).
            # Keep text-bearing plugin templates usable, even though their
            # custom HTML/CSS cannot be reproduced by the browserless engine.
            if not isinstance(text, str):
                raise
            LOG.warning("remote template unavailable; rendering its text with the local style")
    if len(text) > MAX_TEXT_CHARS:
        raise RenderError("文本过长")
    options = payload.get("options") or {}
    if not isinstance(options, dict):
        options = {}
    output_type = "png" if str(options.get("type", "jpeg")).lower() == "png" else "jpeg"
    try:
        quality = int(options.get("quality", 85))
    except (TypeError, ValueError):
        quality = 85
    version = str(data.get("version", ""))
    model_name = data.get("model_name", "")
    if not isinstance(model_name, str):
        model_name = ""
    kwargs = {"legacy_reply_prefix": legacy and local}
    if style is not None:
        kwargs["style"] = style
    if theme is not None:
        kwargs["theme"] = theme
    return _compile_image(text, version, output_type, quality, avatar, model_name, **kwargs)


def _cache_put(data: bytes, mime: str) -> str:
    key = uuid.uuid4().hex
    now = time.monotonic()
    with _CACHE_LOCK:
        for old_key, (expires, _, _) in list(_CACHE.items()):
            if expires < now:
                del _CACHE[old_key]
        if len(_CACHE) >= 32:
            del _CACHE[next(iter(_CACHE))]
        _CACHE[key] = (now + 300, data, mime)
    return key


class Handler(BaseHTTPRequestHandler):
    server_version = "AstrBotT2ILite/2.0"

    def _send(self, status: int, body: bytes, mime: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, data: dict) -> None:
        self._send(status, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json")

    def do_GET(self) -> None:
        if self.path in {"/health", "/text2img/health"}:
            self._json(200, {"status": "ok", "engine": "typst", "style_protocol": 1, "theme_protocol": 1, "service_version": "2.1.0-themes"})
            return
        if self.path in {"/templates", "/text2img/templates"}:
            self._json(200, {"templates": TEMPLATE_CATALOG, "default": "codex", "style_protocol": 1, "theme_protocol": 1, "service_version": "2.1.0-themes"})
            return
        prefix = "/text2img/data/"
        if self.path.startswith(prefix):
            key = self.path[len(prefix) :]
            with _CACHE_LOCK:
                cached = _CACHE.get(key)
            if cached and cached[0] >= time.monotonic():
                self._send(200, cached[1], cached[2])
            else:
                self._json(404, {"error": "image expired"})
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        validation = self.path == "/text2img/themes/validate"
        if self.path != "/text2img/generate" and not validation:
            self._json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length < 1 or length > MAX_REQUEST_BYTES:
            self._json(413, {"error": "request too large or empty"})
            return
        try:
            payload = json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._json(400, {"error": "invalid JSON"})
            return
        if not isinstance(payload, dict):
            self._json(400, {"error": "JSON object expected"})
            return
        if not _SLOTS.acquire(timeout=30):
            self._json(503, {"error": "render queue full"})
            return
        start = time.monotonic()
        try:
            if validation:
                try:
                    theme = parse_theme_package(payload.get("theme", payload))
                except ValueError as error:
                    raise RenderError(str(error)) from error
                _compile_image(VALIDATION_MARKDOWN, "validation", "png", 85, model_name="validation-model", legacy_reply_prefix=True, style={"template": theme.id}, theme=theme)
                self._json(200, {"status": "ok", "theme": theme.catalog})
                return
            data, mime = _render(payload)
        except (RenderError, subprocess.TimeoutExpired, OSError) as error:
            LOG.warning("render failed: %s", error)
            self._json(422, {"error": str(error)})
            return
        except Exception:
            LOG.exception("unexpected render failure")
            self._json(500, {"error": "排版服务内部错误"})
            return
        finally:
            _SLOTS.release()
        LOG.info("rendered %d bytes in %.2fs", len(data), time.monotonic() - start)
        if payload.get("json"):
            key = _cache_put(data, mime)
            self._json(200, {"data": {"id": f"data/{key}"}})
        else:
            self._send(200, data, mime)


def main() -> None:
    host = os.environ.get("T2I_HOST", "0.0.0.0")
    port = int(os.environ.get("T2I_PORT", "8000"))
    server = ThreadingHTTPServer((host, port), Handler)
    LOG.info("listening on %s:%s", host, port)
    server.serve_forever()


if __name__ == "__main__":
    main()

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

from PIL import Image, UnidentifiedImageError

from markdown_typst import to_typst


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOG = logging.getLogger("t2i-lite")
MAX_REQUEST_BYTES = 4 * 1024 * 1024
MAX_TEXT_CHARS = 100_000
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_IMAGE_HEIGHT = 25_000
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


def _compile_image(text: str, version: str, output_type: str, quality: int, avatar: bytes | None = None, model_name: str = "", *, legacy_reply_prefix: bool = False) -> tuple[bytes, str]:
    source = to_typst(text, version, model_name, legacy_reply_prefix=legacy_reply_prefix)
    with tempfile.TemporaryDirectory(prefix="t2i-") as temp_dir:
        input_path = Path(temp_dir) / "render.typ"
        output_path = Path(temp_dir) / "render.png"
        avatar_path = Path(temp_dir) / "avatar.webp"
        if avatar is None:
            shutil.copyfile(Path(__file__).resolve().parent / "assets" / "avatar.webp", avatar_path)
        else:
            avatar_path.write_bytes(avatar)
        input_path.write_text(source, encoding="utf-8")
        completed = subprocess.run(
            ["typst", "compile", "--format", "png", "--ppi", "144", str(input_path), str(output_path)],
            capture_output=True,
            text=True,
            timeout=COMPILE_TIMEOUT,
            check=False,
        )
        if completed.returncode != 0:
            LOG.warning("Typst compile failed: %s", completed.stderr[:1500])
            raise RenderError("排版失败")
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
    # AstrBot's active Codex template carries this stable brand marker.
    local = isinstance(text, str) and '<div class="brand-name">Amadeus</div>' in template
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
    return _compile_image(text, version, output_type, quality, _template_avatar(template), model_name, legacy_reply_prefix=local)


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
    server_version = "AstrBotT2ILite/1.0"

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
            self._json(200, {"status": "ok", "engine": "typst"})
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
        if self.path != "/text2img/generate":
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

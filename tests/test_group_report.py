"""Report extraction, actual local images and compatibility with the byte API."""

import io
import json
import shutil
import threading
import unittest
from http.client import HTTPConnection
from unittest.mock import patch

from PIL import Image

import service
from group_report import adapt_group_report


def html(title="群聊日报", detail='话题正文 **原样文字** #read("/etc/passwd")'):
    chart = "".join(
        f'<div class="chart-column"><div class="chart-value-top">{hour * 7}</div><div class="chart-label-xaxis">{hour:02d}</div></div>'
        for hour in range(24)
    )
    return (
        '<!doctype html><html><head><style>.hidden{color:red}</style><script>throw Error("do not run")</script></head><body>'
        f'<div class="header"><h1>{title}</h1><div class="date-badge">2026年11月17日</div></div>'
        '<div class="stats-grid"><div><span>2000</span><span>消息总数</span></div><div><span>80</span><span>参与人数</span></div></div>'
        '<div class="chart-section-horizontal">' + chart + "</div>"
        '<div class="section-title">今日话题</div><div class="topic-title">测试话题</div><div>'
        + detail
        + "</div>"
        '<div class="section-title">群友画像</div><div class="u-name">群友甲</div><div>INTJ 建筑师</div>'
        '<div class="section-title">金句</div><div class="q-content">金句完整保留</div>'
        '<div class="section-title">质量锐评</div><div>有用信息 35.5%：说明</div>'
        '<img src="http://never-fetch.invalid/private.png"><div hidden>隐私隐藏字段</div>'
        "<footer>SXP-Simon/astrbot_plugin_qq_group_daily_analysis</footer></body></html>"
    )


class ReportExtractionTests(unittest.TestCase):
    def test_content_sections_and_exact_hourly_values_are_preserved(self):
        report = adapt_group_report(html())
        for text in (
            "测试话题",
            "群友甲",
            "INTJ 建筑师",
            "金句完整保留",
            "质量锐评",
            "35.5%",
        ):
            self.assertIn(text, report.text)
        self.assertEqual(report.hourly_counts, [(hour, hour * 7) for hour in range(24)])
        self.assertNotIn("隐私隐藏字段", report.text)
        self.assertNotIn("throw Error", report.text)
        self.assertNotIn("never-fetch", report.text)
        self.assertIn('"2000"', report.theme.source)
        self.assertEqual(set(report.theme.files), {"assets/activity.svg"})

    def test_known_name_alone_does_not_capture_unrelated_html(self):
        self.assertIsNone(
            adapt_group_report(
                "<body><h1>插件安装说明</h1>astrbot_plugin_qq_group_daily_analysis</body>"
            )
        )
        self.assertIsNone(
            adapt_group_report("<body><h1>普通网页</h1>消息总数 10 参与人数 5</body>")
        )

    def test_empty_or_disabled_sections_and_absent_chart_still_work(self):
        report = adapt_group_report(
            "<body><h1>空闲日报</h1><p>消息总数：0</p><p>参与人数：0</p><footer>astrbot_plugin_qq_group_daily_analysis</footer></body>"
        )
        self.assertEqual(report.hourly_counts, [])
        self.assertIn("消息总数", report.text)
        self.assertEqual(report.theme.files, {})

    def test_malformed_or_oversized_html_is_bounded(self):
        for source in (
            html() + "<div>" * 150,
            html().replace(">161<", ">99999999999<"),
        ):
            with self.subTest(source=source[-80:]), self.assertRaises(ValueError):
                adapt_group_report(source)

    def test_bad_hour_labels_do_not_silently_claim_a_complete_chart(self):
        with self.assertRaisesRegex(ValueError, "24 小时"):
            adapt_group_report(html().replace(">23</div>", ">22</div>"))

    def test_miku_separate_ticks_keep_sparse_counts_and_chinese_hour_suffix(self):
        bars = "".join(
            "<div>" + ("<span>77</span>" if hour == 13 else "") + "<div></div></div>"
            for hour in range(24)
        )
        ticks = "".join(
            f"<div><span>{hour:02d}"
            + (" 时" if hour % 4 == 0 else "")
            + "</span></div>"
            for hour in range(24)
        )
        source = (
            '<body><h1>日报</h1><p>消息总数 77 参与人数 1</p><div class="miku-activity-chart"><div>'
            + bars
            + "</div><div>"
            + ticks
            + "</div></div><footer>astrbot_plugin_qq_group_daily_analysis</footer></body>"
        )
        report = adapt_group_report(source)
        self.assertEqual(
            report.hourly_counts,
            [(hour, 77 if hour == 13 else 0) for hour in range(24)],
        )

    def test_report_data_cannot_insert_typst_or_html_resource_paths(self):
        report = adapt_group_report(
            html('标题 #read("/etc/passwd")', '#read("/etc/shadow") {{CONTENT}}')
        )
        from markdown_typst import to_typst

        source = to_typst(
            report.text, style={"template": report.theme.id}, theme=report.theme
        )
        self.assertIn('\\"/etc/passwd\\"', source)
        self.assertIn('text("#read(\\"/etc/shadow\\") {{CONTENT}}")', source)
        self.assertNotIn('src="http', source)

    def test_report_does_not_use_upstream_even_when_it_is_down(self):
        with (
            patch.object(
                service,
                "_proxy_unsupported",
                side_effect=AssertionError("No remote HTML"),
            ),
            patch.object(
                service, "_compile_image", return_value=(b"PNG", "image/png")
            ) as compile_image,
        ):
            service._render(
                {"tmpl": html(), "tmpldata": {}, "options": {"type": "png"}}
            )
            self.assertEqual(
                compile_image.call_args.kwargs["theme"].id, "group-analysis-report"
            )
            self.assertFalse(compile_image.call_args.kwargs["style"]["show_avatar"])
            self.assertFalse(compile_image.call_args.kwargs["style"]["show_footer"])

    def test_unrelated_plugin_template_keeps_its_original_route(self):
        with patch.object(
            service, "_proxy_unsupported", return_value=(b"old", "image/png")
        ) as proxy:
            payload = {"tmpl": "<div>Other plugin</div>", "tmpldata": {}}
            self.assertEqual(service._render(payload), (b"old", "image/png"))
            proxy.assert_called_once_with(payload)


@unittest.skipUnless(shutil.which("typst"), "Typst required")
class LocalReportRenderingTests(unittest.TestCase):
    def test_png_and_jpeg_are_actual_images_with_the_existing_dimensions_limit(self):
        with patch.object(
            service, "_proxy_unsupported", side_effect=AssertionError("No remote")
        ):
            for fmt in ("png", "jpeg"):
                raw, mime = service._render(
                    {"tmpl": html(), "tmpldata": {}, "options": {"type": fmt}}
                )
                self.assertEqual(mime, "image/" + fmt)
                with Image.open(io.BytesIO(raw)) as image:
                    self.assertEqual(image.width, 880)
                    self.assertGreater(image.height, 600)
                    self.assertLess(image.height, 25000)
                    image.verify()

    def test_astrbot_bytes_and_cached_url_response_both_contain_real_images(self):
        server = service.ThreadingHTTPServer(("127.0.0.1", 0), service.Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            for cached in (False, True):
                connection = HTTPConnection(*server.server_address, timeout=30)
                connection.request(
                    "POST",
                    "/text2img/generate",
                    json.dumps(
                        {
                            "tmpl": html(),
                            "tmpldata": {},
                            "json": cached,
                            "options": {"type": "png"},
                        }
                    ),
                    {"Content-Type": "application/json"},
                )
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                raw = response.read()
                if cached:
                    path = json.loads(raw)["data"]["id"]
                    connection.request("GET", "/text2img/" + path)
                    response = connection.getresponse()
                    self.assertEqual(response.status, 200)
                    raw = response.read()
                self.assertTrue(raw.startswith(b"\x89PNG"))
                connection.close()
        finally:
            server.shutdown()
            server.server_close()
            worker.join()

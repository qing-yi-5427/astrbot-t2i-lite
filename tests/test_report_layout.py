"""Readable report structure and actual render output for the selected themes."""

import copy
import io
import shutil
import unittest
from unittest.mock import patch

from PIL import Image

import service
from markdown_typst import to_typst
from report_layout import StructuredReport, render_report, content_text, mention_pattern


def dataset():
    return {
        "schema": 1,
        "summary": {
            "current_date": "2026年11月17日",
            "current_datetime": "2026-11-17 20:00:00",
            "message_count": 1970,
            "participant_count": 38,
            "emoji_count": 209,
            "total_characters": 16345,
            "most_active_period": "14:00–15:00",
            "total_tokens": 93254,
        },
        "hours": [{"hour": hour, "count": hour * 17} for hour in range(24)],
        "topics": [
            {
                "title": "游戏体验与创作",
                "contributors": "群友甲、群友乙",
                "detail": '<p>这里是完整的话题内容，<strong>重点需要保留</strong>。<img src="http://never-fetch.invalid/a.png"></p>',
            }
        ],
        "people": [
            {
                "name": "群友甲",
                "title": "灵感收集者",
                "profile_display": "INTJ 建筑师",
                "reason": "这里是实际分析给出的原因。",
            },
            {
                "name": "群友乙",
                "title": "游戏观察员",
                "mbti": "INTP",
                "reason": "保持不同群友和观察结果的对应关系。",
            },
        ],
        "quotes": [
            {
                "sender": "群友甲",
                "content": '原话 #read("/etc/passwd") <literal>',
                "reason": "<p>点评仍然是数据。</p>",
            }
        ],
        "quality": {
            "title": "今天的群聊很热闹",
            "subtitle": "基于本次分析结果",
            "summary": "总体评价保留。",
            "dimensions": [
                {"name": "游戏交流", "percentage": 65, "comment": "这里是具体点评。"},
                {
                    "name": "生活讨论",
                    "percentage": 35,
                    "comment": "保持解释和百分比对应。",
                },
            ],
        },
    }


class ReportDataTests(unittest.TestCase):
    def test_nicknames_have_a_distinct_theme_badge_in_metadata_and_body(self):
        d = dataset()
        d["topics"][0]["contributors"] = "海胆脑袋已治好、群友甲"
        d["topics"][0]["detail"] = (
            '<p><span class="user-capsule">海胆脑袋已治好</span>提出了建议。</p>'
        )
        report = StructuredReport.parse(d)
        source = render_report(report)
        assert "海胆脑袋已治好" in report.names
        self.assertIn("#highlight(fill: accentsoft", source)
        self.assertIn('text("海胆脑袋已治好",', source)
        self.assertGreaterEqual(source.count('text("海胆脑袋已治好",'), 2)

    def test_short_ascii_nicknames_do_not_style_substrings_of_other_words(self):
        pattern = mention_pattern(("UI", "XXD"))
        source = content_text("UI 与 GUID、XXD、XXDmodel", mentions=pattern)
        self.assertEqual(source.count("#highlight("), 2)

    def test_hidden_person_fields_do_not_invent_name_badges(self):
        d = dataset()
        d["people"][0]["name"] = ""
        d["people"][1]["name"] = ""
        d["quotes"][0]["sender"] = ""
        d["topics"][0]["contributors"] = ""
        report = StructuredReport.parse(d)
        self.assertEqual(report.names, ())

    def test_prepared_html_becomes_text_without_external_resources(self):
        report = StructuredReport.parse(dataset())
        self.assertIn("重点需要保留", report.topics[0]["detail"])
        self.assertNotIn("never-fetch", str(report))
        self.assertIn("<literal>", report.quotes[0]["content"])
        self.assertEqual(report.hours[14], (14, 238))

    def test_all_sections_are_separate_cards_with_the_theme_palette(self):
        source = render_report(StructuredReport.parse(dataset()))
        for label in (
            "话题手记",
            "群友观察",
            "群聊摘录",
            "今日锐评",
            "24 小时活跃轨迹",
        ):
            self.assertIn(label, source)
        for color in ("accentdeep", "soft", "quotebg", "quoteink", "linecolor"):
            self.assertIn(color, source)
        self.assertIn("columns: (1fr,1fr)", source)
        self.assertNotIn("#1d3e55", source)

    def test_invalid_statistics_lists_and_percentages_are_rejected(self):
        cases = []
        for key, value in [
            ("message_count", True),
            ("message_count", -1),
            ("total_tokens", "100"),
        ]:
            d = dataset()
            d["summary"][key] = value
            cases.append(d)
        for value in (float("nan"), float("inf"), -1, 101, True):
            d = dataset()
            d["quality"]["dimensions"][0]["percentage"] = value
            cases.append(d)
        d = dataset()
        d["hours"][23]["hour"] = 22
        cases.append(d)
        d = dataset()
        d["topics"] = [{}] * 65
        cases.append(d)
        for d in cases:
            with self.subTest(value=str(d)[:80]), self.assertRaises(ValueError):
                StructuredReport.parse(d)

    def test_empty_optional_sections_are_not_invented(self):
        d = dataset()
        for key in ("hours", "topics", "people", "quotes"):
            d[key] = []
        d["quality"] = {}
        source = render_report(StructuredReport.parse(d))
        for label in ("话题手记", "群友观察", "群聊摘录", "今日锐评"):
            self.assertNotIn(label, source)

    def test_data_is_literal_and_report_footer_does_not_claim_a_reply_model(self):
        report = StructuredReport.parse(dataset())
        source = to_typst(
            "",
            style={"template": "genshin"},
            rendered_body=render_report(report),
            footer_text=report.footer,
        )
        self.assertIn("派蒙", source)
        self.assertIn("群聊分析报告", source)
        self.assertIn('\\"/etc/passwd\\"', source)
        self.assertNotIn("回复模型：", source)

    def test_structured_report_bypasses_the_flat_html_adapter(self):
        data = {"t2i_report": dataset(), "t2i_style": {"template": "starrail"}}
        with (
            patch.object(
                service,
                "adapt_group_report",
                side_effect=AssertionError("No flattening"),
            ),
            patch.object(
                service,
                "_proxy_unsupported",
                side_effect=AssertionError("No external HTML"),
            ),
            patch.object(
                service, "_compile_image", return_value=(b"png", "image/png")
            ) as compiler,
        ):
            service._render({"tmpl": "<html>plugin html</html>", "tmpldata": data})
            self.assertEqual(compiler.call_args.kwargs["style"]["template"], "starrail")
            self.assertIsInstance(compiler.call_args.kwargs["report"], StructuredReport)


@unittest.skipUnless(shutil.which("typst"), "Typst required")
class ThemedReportImageTests(unittest.TestCase):
    def test_every_builtin_theme_renders_the_report_at_its_chat_width(self):
        for identity in ("codex", "genshin", "starrail", "miku", "zzz", "rio"):
            with self.subTest(theme=identity):
                raw, mime = service._render(
                    {
                        "tmpl": "",
                        "tmpldata": {
                            "t2i_report": dataset(),
                            "t2i_style": {"template": identity},
                        },
                        "options": {"type": "png"},
                    }
                )
                self.assertEqual(mime, "image/png")
                with Image.open(io.BytesIO(raw)) as image:
                    self.assertEqual(image.width, 720)
                    self.assertGreater(image.height, 1200)
                    self.assertLess(image.height, 25000)
                    image.verify()

    def test_open_git_theme_source_and_custom_brand_are_used(self):
        theme = {
            "id": "custom-report",
            "source": "#set page(width: 400pt)\n#text(brand)\n{{CONTENT}}",
            "meta": {"brand_name": "自定义主题"},
        }
        raw, _ = service._render(
            {
                "tmpl": "",
                "tmpldata": {"t2i_report": dataset(), "t2i_theme": theme},
                "options": {"type": "png"},
            }
        )
        with Image.open(io.BytesIO(raw)) as image:
            self.assertEqual(image.width, 800)

    def test_long_names_all_zero_chart_and_disabled_avatars_render(self):
        d = dataset()
        d["people"][0]["name"] = (
            "名字比较长但仍然需要完整展示并且能够在标签内自然换行的群友"
        )
        for item in d["hours"]:
            item["count"] = 0
        raw, _ = service._render(
            {
                "tmpl": "",
                "tmpldata": {
                    "t2i_report": d,
                    "t2i_style": {
                        "template": "genshin",
                        "brand_name": "一个较长的自定义机器人名字",
                        "show_avatar": False,
                        "show_footer": False,
                    },
                },
                "options": {"type": "jpeg"},
            }
        )
        self.assertTrue(raw.startswith(b"\xff\xd8"))

    def test_concurrent_themes_do_not_share_a_palette_or_header(self):
        from concurrent.futures import ThreadPoolExecutor

        def render(identity):
            return service._render(
                {
                    "tmpl": "",
                    "tmpldata": {
                        "t2i_report": copy.deepcopy(dataset()),
                        "t2i_style": {"template": identity},
                    },
                    "options": {"type": "png"},
                }
            )[0]

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(render, ["genshin", "starrail"]))
        self.assertNotEqual(results[0], results[1])


if __name__ == "__main__":
    unittest.main()

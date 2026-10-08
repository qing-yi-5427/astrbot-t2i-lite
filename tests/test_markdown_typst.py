import unittest

from markdown_typst import to_typst, _parse_markdown, _wrap_code_line
import json
from unittest.mock import patch


class CodeFenceTests(unittest.TestCase):
    def test_unlabeled_code_fence(self):
        result = to_typst("正文\n\n```\nprint(1)\n```", "v4.28.1")
        self.assertIn("print(1)", result)

    def test_whitespace_only_code_fence(self):
        result = to_typst("```   \nprint(2)\n```", "v4.28.1")
        self.assertIn("print(2)", result)

    def test_labeled_code_fence(self):
        result = to_typst("```python\nprint(3)\n```", "v4.28.1")
        self.assertIn("PYTHON", result)


class StatusSymbolTests(unittest.TestCase):
    def test_table_statuses_have_distinct_supported_symbols(self):
        markdown = "| 项目 | 状态 |\n|---|---|\n| 成功 | ✅ 正常 |\n| 失败 | ❌ 失败 |\n| 警告 | ⚠️ 不稳定 |"
        result = to_typst(markdown, "v4.28.1")
        self.assertIn('text("✓", fill: rgb("#238a5a")', result)
        self.assertIn('text("×", fill: rgb("#b84040")', result)
        self.assertIn('text("⚠", fill: rgb("#a16b00")', result)
        self.assertNotIn('text("✅")', result)
        self.assertNotIn('text("❌")', result)


class FooterTests(unittest.TestCase):
    def test_default_footer_is_backward_compatible(self):
        result = to_typst("正文", "v4.28.2")
        self.assertIn("AMADEUS  ·  POWERED BY ASTRBOT", result)
        self.assertNotIn("{{FOOTER}}", result)

    def test_model_footer_replaces_old_credit(self):
        result = to_typst("正文", "v4.28.2", "gpt-6.1-sol")
        self.assertIn("回复模型：gpt-6.1-sol", result)
        self.assertNotIn("POWERED BY ASTRBOT", result)

    def test_model_is_escaped_and_length_bounded(self):
        model = '#read("/etc/passwd") [*] \\ {{CONTENT}}'
        result = to_typst("原始正文", "v4.28.2", model)
        self.assertIn(json.dumps("回复模型：" + model, ensure_ascii=False), result)
        self.assertIn("原始正文", result)
        self.assertIn("回复模型：" + 'x'*160, to_typst("正文", model_name='x'*1000))

    def test_placeholder_like_markdown_is_preserved(self):
        result = to_typst("{{FOOTER}} {{VERSION}}", model_name="model")
        self.assertIn('text("{{FOOTER}} {{VERSION}}")', result)


class CheckboxAndEmojiTests(unittest.TestCase):
    def test_task_list_uses_drawn_checkboxes_not_font_characters(self):
        result = to_typst('- [x] 已完成\n- [ ] 未完成')
        self.assertEqual(result.count('viewBox=\\"0 0 20 20\\"'), 2)
        self.assertEqual(result.count('<polyline'), 1)
        self.assertIn('alt: "已完成"', result)
        self.assertIn('alt: "未完成"', result)
        self.assertNotIn('text("☑")', result)
        self.assertNotIn('text("☐")', result)

    def test_literal_checkbox_variants_are_drawn_consistently(self):
        result = to_typst('☑ ☑️ ☑︎ ☐ ☐️ ☐︎')
        self.assertEqual(result.count('viewBox=\\"0 0 20 20\\"'), 6)
        self.assertEqual(result.count('<polyline'), 3)

    def test_quote_and_bot_aside_checkboxes_have_correct_contrast(self):
        result = to_typst('> - [x] 已完成\n> - [ ] 未完成')
        self.assertIn('fill=\\"#28658e\\"', result)
        self.assertIn('stroke=\\"#ffffff\\"', result)
        aside = to_typst('     ☑ 旁白已完成 ☐ 旁白待完成', legacy_reply_prefix=True)
        self.assertIn('fill=\\"#6dc8ff\\"', aside)
        self.assertIn('stroke=\\"#142e46\\"', aside)
        self.assertIn('stroke=\\"#a5bdc9\\"', aside)

    def test_emoji_font_fallback_is_used_in_headings_quotes_and_code(self):
        result = to_typst('# 📡 未来道具研究所\n\n正文 🧪 🍮\n\n> 引用 📡\n\n`📡`\n\n```\n📡\n```')
        self.assertIn('("Noto Sans SC", "Noto Sans CJK SC", "Noto Color Emoji")', result)
        self.assertIn('size: 20pt', result)
        self.assertIn('("DejaVu Sans Mono", "Noto Sans SC", "Noto Color Emoji")', result)
        self.assertIn('text("📡 未来道具研究所")', result)
        self.assertIn('回复模型：model', to_typst('☑ 状态 📡', model_name='model'))

    def test_normal_list_and_code_semantics_are_preserved(self):
        result = to_typst('- 普通项目\n\n1. 有序项目\n\n`☑`\n\n```\n- [x] literal code\n```')
        self.assertIn('text("•"', result)
        self.assertIn('text("1."', result)
        self.assertIn('text("☑", font:', result)
        self.assertIn('raw("- [x] literal code"', result)
        self.assertNotIn('<polyline', result)


class DarkQuoteTests(unittest.TestCase):
    BANK_TEXT = "你们这里说的是银行的云服务和数据中心架构吧，不是彭博那类行情数据。我查几个美国大行的公开案例，看看哪些用公有云、哪些保留自建基础设施。"

    def test_legacy_intro_is_a_quote_not_a_code_block(self):
        nodes = _parse_markdown("\n\n     " + self.BANK_TEXT + "\n\n正常正文", True)
        first = next(node for node in nodes if node['type'] != 'blank_line')
        self.assertEqual(first['type'], 'dark_quote')
        self.assertEqual(first['children'][0]['type'], 'paragraph')
        result = to_typst("\n\n     " + self.BANK_TEXT + "\n\n正常正文", legacy_reply_prefix=True)
        self.assertIn(self.BANK_TEXT, result)
        self.assertNotIn('#raw(', result)
        self.assertNotIn('哪\\n  些', result)
        self.assertIn('fill: asidebg', result)
        self.assertIn('text("正常正文")', result)

    def test_quotes_do_not_use_the_code_line_wrapper(self):
        with patch('markdown_typst._wrap_code_line', side_effect=AssertionError('Prose must not be sliced')):
            to_typst('> ' + self.BANK_TEXT)
            to_typst('     ' + self.BANK_TEXT, legacy_reply_prefix=True)

    def test_explicit_quote_has_natural_line_layout_and_legible_emphasis(self):
        result = to_typst('> 普通文字 **重点内容** 和 [链接](https://example.com)')
        self.assertIn('fill: quotebg', result)
        self.assertIn('size: 11pt, fill: quoteink', result)
        self.assertIn('linebreaks: "simple"', result)
        self.assertIn('fill: accentdeep)[#text("重点内容")]', result)
        self.assertIn('fill: accentdeep)[#text("链接")]', result)
        self.assertNotIn('#raw(', result)

    def test_only_legacy_intro_is_wrapped(self):
        result = to_typst('     引用开头\n\n正常正文\n\n    real_code()', legacy_reply_prefix=True)
        self.assertEqual(result.count('fill: asidebg,'), 1)
        self.assertIn('raw("real_code()"', result)

    def test_quote_spacing_is_local_and_code_spacing_is_unchanged(self):
        result = to_typst('> 注意：忙碌感不等于进度。  \n> 尤其当你的“准备工作”比实际工作还长的时候。\n>\n> 下一段\n\n正常正文\n\n```python\nprint(1)\n```')
        self.assertIn('inset: (x: 11pt, y: 10pt)', result)
        self.assertIn('first-line-indent: 0pt, leading: 0.85em', result)
        self.assertIn('#block(width: 100%, above: 6pt, below: 6pt)', result)
        self.assertIn('#block(width: 100%, above: 8pt, below: 8pt)[#text("正常正文")]', result)
        self.assertIn('#set par(leading: 0.65em, spacing: 0pt)', result)
        self.assertIn('inset: (x: 11pt, y: 11pt)', result)
        self.assertIn('size: 9.5pt', result)

    def test_other_clients_do_not_reinterpret_indented_code(self):
        nodes = _parse_markdown('     real_code()')
        self.assertEqual(nodes[0]['type'], 'block_code')
        self.assertEqual(nodes[0]['raw'], ' real_code()')

    def test_real_code_keeps_indentation_and_fences(self):
        samples = ['     ```python\nprint(1)\n```', '         real_code()', '     # 标题\n\n正文', '     - 列表\n- 下一项']
        for text in samples:
            with self.subTest(text=text):
                result = to_typst(text, legacy_reply_prefix=True)
                self.assertNotIn('fill: asidebg,', result)
        self.assertIn('PYTHON', to_typst(samples[0], legacy_reply_prefix=True))

    def test_multiline_quote_retains_explicit_breaks_not_artificial_indent(self):
        result = to_typst('> 第一行  \n> 第二行\n>\n> 下一段')
        self.assertIn('#linebreak()', result)
        self.assertNotIn('#raw(', result)
        self.assertIn('text("下一段")', result)

    def test_nested_quote_lists_and_tables_are_not_lost(self):
        result = to_typst('> 第一段\n>\n> - 一项\n> - **重点**\n>\n> | 项目 | 状态 |\n> |---|---|\n> | 引用 | 正常 |')
        self.assertIn('text("第一段")', result)
        self.assertIn('text("重点")', result)
        self.assertIn('#table(', result)
        self.assertIn('#text(fill: ink)[#table(', result)

    def test_source_is_safe_and_model_footer_is_preserved(self):
        result = to_typst('     引用 #read("/etc/passwd") {{FOOTER}}', model_name='actual-model', legacy_reply_prefix=True)
        self.assertIn('回复模型：actual-model', result)
        self.assertIn(json.dumps('引用 #read("/etc/passwd") {{FOOTER}}', ensure_ascii=False), result)

    def test_exact_prefix_not_arbitrary_whitespace(self):
        for count in (0, 1, 2, 3, 4, 6, 9):
            result = to_typst(' '*count + '文本', legacy_reply_prefix=True)
            self.assertNotIn('fill: asidebg,', result)


class LabMarkdownCoverageTests(unittest.TestCase):
    def test_aside_label_color_is_distinct_from_blue_emphasis(self):
        result = to_typst('     普通文字 **正文重点**', legacy_reply_prefix=True)
        self.assertIn('#let asidelabel = rgb("#e6c58d")', result)
        self.assertIn('#let asideaccent = rgb("#80cfff")', result)
        self.assertIn('text("AMADEUS / 个人旁白", size: 8pt, fill: asidelabel', result)
        self.assertIn('#let accent = asideaccent', result)
        self.assertIn('fill: accent)[#text("正文重点")]', result)

    def test_bot_aside_quote_and_code_are_separate_components(self):
        result = to_typst('     Bot 吐槽\n\n> 引用内容\n\n```python\nprint(1)\n```', legacy_reply_prefix=True)
        for marker in ('fill: asidebg', 'fill: quotebg', 'fill: codebg', 'fill: codehead', '个人旁白', '研究记录', 'PYTHON'):
            if marker != '研究记录':
                self.assertIn(marker, result)
        self.assertEqual(result.count('fill: asidebg,'), 1)
        self.assertEqual(result.count('fill: quotebg,'), 1)

    def test_six_heading_levels_and_inline_formats(self):
        result = to_typst('\n\n'.join('#'*level + ' H' + str(level) for level in range(1, 7)) + '\n\n**加粗** *斜体* ~~删除~~ [链接](https://example.com) `行内代码`')
        for level in range(1, 7):
            self.assertIn('text("H' + str(level) + '")', result)
        for marker in ('weight: "bold"', '#emph[', '#strike[', 'text("链接")', 'text("行内代码", font:'):
            self.assertIn(marker, result)

    def test_ordered_list_start_nested_blocks_and_loose_paragraphs(self):
        result = to_typst('3. 第一项\n\n   另一个段落\n\n   > 列表内引用\n\n   ```python\n   print("列表内代码")\n   ```\n\n   - 子项\n     - 更深子项\n\n4. 第二项')
        for marker in ('text("3."', 'text("4."', '另一个段落', '列表内引用', '列表内代码', '更深子项', 'fill: quotebg', 'fill: codebg'):
            self.assertIn(marker, result)

    def test_deep_lists_do_not_drop_content(self):
        markdown = '\n'.join('  '*depth + '- 层级' + str(depth) for depth in range(12))
        result = to_typst(markdown)
        for depth in range(12):
            self.assertIn('text("层级' + str(depth) + '")', result)

    def test_table_alignment_and_wide_table_content(self):
        result = to_typst('| 左 | 中 | 右 |\n| :--- | :---: | ---: |\n| A | B | C |')
        for alignment in ('left', 'center', 'right'):
            self.assertIn('#align(' + alignment + ')', result)
        wide = to_typst('| A | B | C | D | E | F |\n|---|---|---|---|---|---|\n| 1 | 2 | 3 | 4 | 5 | 最后一列 |')
        self.assertIn('text("最后一列")', wide)

    def test_breaks_rules_escape_images_and_unsafe_html(self):
        result = to_typst('第一行  \n第二行<br>第三行\n\n---\n\n\\*普通星号\\*\n\n![图片说明](https://example.invalid/image.png)\n\n<script>alert(1)</script>')
        self.assertGreaterEqual(result.count('#linebreak()'), 2)
        self.assertIn('height: 0.6pt', result)
        self.assertIn('普通星号', result)
        self.assertIn('图片说明', result)
        self.assertIn('外链未加载', result)
        self.assertNotIn('alert(1)', result)

    def test_code_language_labels_and_source_are_safe(self):
        result = to_typst('```diff\n-old\n+new\n```\n\n```unknown_lang\n#read("/etc/passwd")\n```\n\n```\n[☑] {{CONTENT}}\n```')
        for marker in ('DIFF', 'UNKNOWN_LANG', 'CODE', 'raw("-old\\n+new"', '#read(\\"/etc/passwd\\")', '{{CONTENT}}'):
            self.assertIn(marker, result)

    def test_code_wrap_accounts_for_cjk_and_preserves_characters(self):
        source = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' * 4 + '中文字符' * 12
        lines = _wrap_code_line(source).splitlines()
        recovered = lines[0] + ''.join(line[2:] for line in lines[1:])
        self.assertEqual(recovered, source)
        import unicodedata
        for line in lines:
            columns = sum(2 if unicodedata.east_asian_width(char) in {'W', 'F'} else 1 for char in line)
            self.assertLessEqual(columns, 46)


if __name__ == "__main__":
    unittest.main()

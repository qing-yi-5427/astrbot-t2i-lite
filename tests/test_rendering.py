import io
import unittest

from PIL import Image
from service import _compile_image


class QuoteCompileTests(unittest.TestCase):
    def test_aside_label_is_gold_while_emphasis_stays_blue(self):
        data, _ = _compile_image('     **正文重点保持蓝色**，其他正文保持白色。', 'v4.28.2', 'png', 85, legacy_reply_prefix=True)
        with Image.open(io.BytesIO(data)) as image:
            pixels = image.convert('RGB').load()
            gold = sum(
                1 for x in range(90, 400) for y in range(206, 235)
                if pixels[x, y][0] > pixels[x, y][1] + 15
                and pixels[x, y][1] > pixels[x, y][2] + 25
            )
            blue = sum(
                1 for x in range(90, 640) for y in range(235, 290)
                if pixels[x, y][1] > pixels[x, y][0] + 30
                and pixels[x, y][2] > pixels[x, y][0] + 30
            )
            self.assertGreater(gold, 100)
            self.assertGreater(blue, 100)

    def assert_rendered(self, text):
        data, mime = _compile_image(text, 'v4.28.2', 'png', 85, model_name='排版测试', legacy_reply_prefix=True)
        self.assertEqual(mime, 'image/png')
        with Image.open(io.BytesIO(data)) as image:
            self.assertEqual(image.width, 720)
            self.assertGreater(image.height, 250)
            image.verify()

    def test_legacy_intro_compiles_as_real_prose(self):
        self.assert_rendered('     你们这里说的是银行的云服务和数据中心架构吧，不是彭博那类行情数据。我查几个美国大行的公开案例，看看哪些用公有云、哪些保留自建基础设施。\n\n正常正文。')

    def test_quote_table_and_emphasis_compile(self):
        self.assert_rendered('> 引用段落 **重点** 和 [链接](https://example.com)\n>\n> | 项目 | 状态 |\n> |---|---|\n> | 引用 | ✅ 正常 |\n> | 表格 | ❌ 失败 |')

    def test_nested_quote_list_and_code_compile(self):
        self.assert_rendered('> 引用开头\n>\n> - 普通列表\n> - **重点列表**\n>\n> > 嵌套引用\n>\n> ```python\n> print("代码保持原样")\n> ```\n\n普通正文')

    def test_quote_spacing_with_hard_break_and_multiple_paragraphs(self):
        self.assert_rendered('## 今日研究课题\n\n普通正文。\n\n> 注意：忙碌感不等于进度。  \n> 尤其当你的“准备工作”比实际工作还长的时候。\n>\n> 单独的下一段也保留适当间距。')

    def test_emoji_heading_and_task_list_compile(self):
        self.assert_rendered('# 📡 未来道具研究所：零食失踪事件\n\n## 三、调查进度\n\n- [x] 确认布丁失踪\n- [x] 排除“布丁长腿逃跑”的假设\n- [ ] 找到真正的食用者\n- [ ] 获得一份赔偿布丁\n- [ ] 阻止嫌疑人把赔偿款用于买香蕉')

    def test_checkboxes_compile_in_nested_lists_quotes_and_tables(self):
        self.assert_rendered('- [x] 第一项\n  - [ ] 子项\n\n> - [x] 引用已完成\n> - [ ] 引用待完成\n\n| 状态 | 含义 |\n|---|---|\n| ☑️ | 已完成 |\n| ☐ | 未完成 |')

    def test_satellite_emoji_is_visible_not_a_missing_glyph_box(self):
        data, _ = _compile_image('# 📡 未来道具研究所：零食失踪事件\n\n正常正文', 'v4.28.2', 'png', 85)
        with Image.open(io.BytesIO(data)) as image:
            pixels = image.convert('RGB').load()
            # This heading region excludes the avatar and research label.
            # The satellite dish is cyan; a missing-glyph box is monochrome.
            colored = sum(
                1 for x in range(70, 130) for y in range(215, 285)
                if pixels[x, y][1] > pixels[x, y][0] + 20
                and pixels[x, y][2] > pixels[x, y][0] + 20
            )
            self.assertGreater(colored, 100)

    def test_all_common_markdown_formats_compile_together(self):
        self.assert_rendered('     吐槽里 **强调** 与 ☑ 也能显示。\n\n# 📡 一级标题\n\n## 二级标题\n\n### 三级标题\n\n#### 四级标题\n\n##### 五级标题\n\n###### 六级标题\n\n**加粗**、*斜体*、~~删除线~~、[链接](https://example.com)、`行内代码`、\\*转义\\*。\n\n第一行  \n第二行<br>第三行\n\n---\n\n> 引用正文\n>\n> > 嵌套引用\n>\n> - [x] 引用中的任务\n> - [ ] 引用中的待办\n\n3. 有序列表\n\n   另一段正文\n\n   > 列表内引用\n\n   ```json\n   {"list": true}\n   ```\n\n   - 嵌套列表\n     - 更深一层\n\n4. 下一项\n\n| 左 | 中 | 右 |\n| :--- | :---: | ---: |\n| A | ✅ | C |\n| B | ☑ | D |\n\n```diff\n-old\n+new\n```\n\n```\n没有语言标签的代码\n```\n\n![外链图片说明](https://example.invalid/image.png)')

    def test_long_code_lines_and_quote_nested_code_compile(self):
        line = '变量名称与中文字符串' * 20 + 'x'*150
        self.assert_rendered('```python\n' + line + '\n```\n\n> ```python\n> ' + line + '\n> ```\n\n- 项目\n\n  ```python\n  ' + line + '\n  ```')

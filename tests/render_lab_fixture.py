"""Save the compile-test fixtures for visual inspection, without model requests."""

import sys
from pathlib import Path

from service import _compile_image
from test_rendering import QuoteCompileTests


class FixturePreview(QuoteCompileTests):
    output: Path

    def assert_rendered(self, text):
        data, mime = _compile_image(
            text, "v4.28.2", "png", 85,
            model_name="排版测试（非实际模型调用）", legacy_reply_prefix=True,
        )
        assert mime == "image/png"
        self.output.write_bytes(data)
        print(self.output.name, len(data), "bytes")


if __name__ == "__main__":
    preview = FixturePreview()
    directory = Path(sys.argv[1])
    preview.output = directory / "common-markdown.png"
    preview.test_all_common_markdown_formats_compile_together()
    preview.output = directory / "long-code.png"
    preview.test_long_code_lines_and_quote_nested_code_compile()

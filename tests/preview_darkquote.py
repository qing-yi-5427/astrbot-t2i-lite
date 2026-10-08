"""Render the screenshot's reply through AstrBot without model/QQ requests."""
import asyncio
import copy
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import aiohttp
from PIL import Image as PILImage
from astrbot.api.provider import LLMResponse
from astrbot.core.message.components import Image
from astrbot.core.message.message_event_result import MessageEventResult, ResultContentType
from astrbot.core.pipeline.result_decorate import stage as pipeline
from astrbot.core.utils.t2i.network_strategy import NetworkRenderStrategy
from astrbot_plugin_model_footer.bridge import _RENDER_EVENT
from astrbot_plugin_model_footer.main import ModelFooterPlugin


class PreviewEvent:
    plugins_name = None
    unified_msg_origin = 'isolated-darkquote-render-test'

    def __init__(self, text):
        self.extra = {}
        self.result = MessageEventResult().message(text).set_result_content_type(ResultContentType.LLM_RESULT)

    def set_extra(self, key, value):
        self.extra[key] = value

    def get_extra(self, key, default=None):
        return self.extra.get(key, default)

    def get_result(self):
        return self.result

    def get_platform_name(self):
        return 'isolated-preview'

    def is_stopped(self):
        return False


async def main():
    cfg = copy.deepcopy(json.loads(Path('/AstrBot/data/cmd_config.json').read_text(encoding='utf-8-sig')))
    assert cfg['platform_settings']['reply_prefix'] == '     ', 'Live reply prefix changed; revisit compatibility handling'
    cfg.update(t2i=True, t2i_strategy='remote', t2i_active_template='codex', t2i_word_threshold=50)
    cfg['platform_settings']['segmented_reply']['enable'] = False
    cfg['platform_settings'].update(reply_with_mention=False, reply_with_quote=False)
    cfg['provider_tts_settings']['enable'] = False
    cfg['provider_settings']['display_reasoning_text'] = False
    cfg['content_safety']['also_use_in_response'] = False
    context = SimpleNamespace(astrbot_config=cfg, plugin_manager=SimpleNamespace(context=SimpleNamespace(get_using_tts_provider_async=AsyncMock(return_value=None))))
    plugin = ModelFooterPlugin(MagicMock())
    pipeline.html_renderer.network_strategy = NetworkRenderStrategy(sys.argv[1])
    stage = pipeline.ResultDecorateStage()
    await stage.initialize(context)
    await plugin.initialize()
    text = '你们这里说的是银行的云服务和数据中心架构吧，不是彭博那类行情数据。我查几个美国大行的公开案例，看看哪些用公有云、哪些保留自建基础设施。\n\n## 排版测试\n\n深色开头使用独立引用样式，中文按实际宽度自然换行。**模型页脚、正文和代码样式仍保留。**\n\n> 显式 Markdown 引用也采用深色框，支持 **重点文字** 和 [链接](https://example.com)。这是排版测试，没有调用模型，也没有发送 QQ 消息。\n\n```python\nprint("代码块仍按代码排版")\n```'
    if len(sys.argv) > 3 and sys.argv[3] == 'quote-spacing':
        text = '# 一、今日研究课题\n\n**为什么人打开电脑以后，会忘记自己原本要做什么？**\n\n初步推测：你本来只想查一个单词，结果打开了十二个网页、看了 **三个视频**，最后开始研究如何提高效率机械键盘。\n\n> 注意：忙碌感不等于进度。  \n> 尤其当你的“准备工作”比实际工作还长的时候。'
    elif len(sys.argv) > 3 and sys.argv[3] == 'symbols':
        text = '# 📡 未来道具研究所：零食失踪事件\n\n清衣，又来？你这已经不是“随便输出”，而是在给 Markdown 做耐久测试了。好吧，这次换个主题——**一场极其严肃、但研究对象是布丁的调查**。\n\n## 三、调查进度\n\n- [x] 确认布丁失踪\n- [x] 排除“布丁长腿逃跑”的假设\n- [ ] 找到真正的食用者\n- [ ] 获得一份赔偿布丁\n- [ ] 阻止嫌疑人把赔偿款用于买香蕉'
    elif len(sys.argv) > 3 and sys.argv[3] == 'lab-style':
        from lab_sample import SAMPLE
        text = SAMPLE[5:]
    elif len(sys.argv) > 3 and sys.argv[3] == 'aside-label':
        text = '**能，这次引用里的两张图片都能看清，不只是收到两个 `[Image]` 占位符。** 引用者是试剂，里面显示“宁宁起爆器”发了两张图。'
    event = PreviewEvent(text)
    try:
        await plugin.remember_response_model(event, LLMResponse(role='assistant', completion_text=text, raw_completion={'model': '排版测试（非实际模型调用）'}))
        async for _ in stage.process(event):
            pass
        assert _RENDER_EVENT.get() is None
        assert len(event.result.chain) == 1 and isinstance(event.result.chain[0], Image)
        url = event.result.chain[0].url or event.result.chain[0].file
        assert url.startswith('http'), 'Unexpected local-render fallback'
        async with aiohttp.ClientSession(trust_env=False) as session:
            async with session.get(url) as response:
                response.raise_for_status()
                data = await response.read()
        with PILImage.open(io.BytesIO(data)) as image:
            assert image.width == 720
            image.save(sys.argv[2], format='PNG')
            print('Real AstrBot pipeline image:', image.size, 'bytes:', len(data), 'file:', sys.argv[2])
    finally:
        await plugin.terminate()


asyncio.run(main())

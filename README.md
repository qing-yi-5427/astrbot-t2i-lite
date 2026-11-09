# AstrBot 轻量文转图服务

独立 Docker 项目，使用 Typst 排版、Pillow 编码，不启动浏览器。兼容 AstrBot 文转图请求，支持 Markdown、中文、Emoji、代码、表格、任务列表和模型页脚。

## 2.1.0-themes：Git 主题包

配合 [主题与模型页脚插件](https://github.com/qing-yi-5427/astrbot-plugins/tree/main/plugins/astrbot_plugin_t2i_style) v1.2.0，支持由插件从 Git 仓库下载、缓存和试渲染主题，再随当前文转图请求传入。服务继续使用只读 Docker，不需要把 Git 挂进容器、不需要为每次主题修改重建镜像。

主题可以只有一个 `theme.typ`，含 `{{CONTENT}}` 正文入口即可；元数据、头像和相对资源可选。页面布局、配色、字号、宽度与头部高度不受现有六套格式限制。未定义的 Markdown 配色变量由默认前导代码补齐。给其他 agent 的文档：[T2I_THEME_AUTHORING.md](https://github.com/qing-yi-5427/astrbot-plugins/blob/main/docs/T2I_THEME_AUTHORING.md)。

新增接口：

- `GET /text2img/health` 返回整数 `theme_protocol: 1`，服务版本为 `2.1.0-themes`，原 `style_protocol: 1` 保留。
- `POST /text2img/themes/validate`，请求 `{"theme": {"schema": 1, "id": "my-theme", "source": "{{CONTENT}}", "meta": {}, "files": {}}}`。真实编译公共 Markdown 样例，通过后返回主题信息；失败返回 422 和有限的编译诊断。
- `POST /text2img/generate` 可在 `tmpldata.t2i_theme` 携带同一主题包，`t2i_style.template` 选择对应 ID。`files` 为主题内相对路径到 Base64 数据的映射，支持 `assets/` 下的局部模块和素材。

服务不维护可变的 Git 全局目录；`GET /templates` 仍列出六套内置回退。Git 主题列表由插件 `/t2i list` 提供。一个请求只携带当前选用的主题，主题源码不会加入聊天模型上下文。

主题是你所选仓库提供的 Typst 代码。编译仍限制在独立临时项目根目录，资源路径不允许逃逸或覆盖编译输出；保持 25 秒编译超时、并发 2、原请求/输出上限及 Docker 资源限制。服务未增加持久写入目录或主题管理凭据。

当前部署镜像标签：`astrbot-t2i-lite:2.1.0-themes`。下面的 2.0.3 说明是内置回退主题的设计基线。

## 内置六主题与紧凑页头（2.0.3 设计基线）

本版逐一优化六套页头，高度为上一版的约 64%–73%；派蒙名称上下使用明确的 8pt 堆叠间距，其他主题也分开处理眉题、名称和副标题，缩小头像、状态条与装饰。星铁、初音和莉音的背景装饰限制在头部范围，避免越界到正文。

继承上一版：全部主题取消图片外追加的素材署名条，五套新主题头像使用 GPT 生图服务生成的角色同人插画。六套正式主题以及保留的历史草稿统一使用 Adobe 思源黑体 Source Han Sans SC，代码保留等宽字体与同字库中文回退。此前旁白品牌名修复和伊埃斯身份保持不变。

保留 `codex` 正文与页脚布局，本次同步收紧其页头，加入五套经本地真实 Typst 编译验证的非官方作品／角色启发主题。此前实验性 `midnight/sakura/forest/paper` 不属于正式协议白名单，不能通过请求选择。

| ID | 名称 | 默认品牌 | 默认副标题 | 视觉方向 |
|---|---|---|---|---|
| `codex` | Codex 经典 | Amadeus | powered by Astrbot | 蓝白研究卡片，紧凑头像与标题 |
| `miku` | 初音未来 | 初音未来 | HATSUNE MIKU · VIRTUAL SINGER | 青绿电子舞台、五线谱、耳机式头像框 |
| `genshin` | 原神 | 派蒙 | AD ASTRA ABYSSOSQUE | 羊皮纸冒险手册、星纹罗盘、思源黑体正文 |
| `starrail` | 星穹铁道 | 帕姆 | TRAILBLAZER · ASTRAL EXPRESS | 星轨、列车、车票结构与旅行档案 |
| `zzz` | 绝区零 | 伊埃斯 | NEW ERIDU · RANDOM PLAY | 黑黄撞色、录像带、街头贴纸 |
| `rio` | 蔚蓝档案 · 调月莉音 | 调月莉音 | TSUKATSUKI RIO · MILLENNIUM | 黑白红科技档案、几何光环、工程网格 |

每个主题都有自己的默认头像。名称、副标题、头像均可替换，也可关闭头像或模型／品牌页脚。PLAY、REC、条码、状态栏等均为视觉装饰，不执行播放、录音或认证功能。

### 页头高度验收

用同一正文，通过 Typst 的实际排版位置测量；不包含外部页面边距和正文内边距。正文仍为 12pt 思源黑体，宽度保持 720px。自定义长名称/副标题允许自然增高，优先完整显示。

| 主题 | 2.0.2 页头 | 本版页头 | 保留比例 |
|---|---:|---:|---:|
| `codex` | 60.50pt | 42.50pt | 70.2% |
| `miku` | 190.60pt | 122.13pt | 64.1% |
| `genshin` | 170.35pt | 121.35pt | 71.2% |
| `starrail` | 169.53pt | 119.13pt | 70.3% |
| `zzz` | 151.99pt | 111.13pt | 73.1% |
| `rio` | 187.27pt | 127.13pt | 67.9% |

### 与旧版本的关系

本项目最初从 NAS 的 `astrbot-t2i-lite:1.4.1-aside-label` 补齐源码、依赖、字体许可、默认头像和离线 wheel；此次版本在其上增量接入正式主题。`codex` 不传个性化字段时仍使用原版 [Codex 样式](<codex_style.typ>)；旧整页源码指纹已随用户明确要求的页头重排撤下，改用真实 Typst 测量保护 60%–75% 的头部高度目标；默认与显式 Codex 渲染保持像素一致，不改原有 Markdown 语义及模型页脚优先级。新的固定镜像标签为 `astrbot-t2i-lite:2.1.0-themes`；本地构建成功不等于已经部署，应以实际运行容器标签和健康检查为准。

原有二进制资源校验记录在 [资源校验清单](<assets.sha256.json>)。离线 wheel 对应 Linux x86_64 / Python 3.12；当前 Compose 应在该架构运行。首次构建仍需拉取基础镜像，或提前在本机缓存这些镜像。本仓库不包含聊天数据、密钥或部署备份。

## 部署接口

[Compose 配置](<compose.yaml>) 使用外部网络 `astrbot-napcat_astrbot_network`，容器别名为 `t2i-lite`，不发布宿主机端口，保留只读根文件系统、临时目录、非特权用户、能力限制及内存／进程上限。部署前根据自己的 AstrBot 网络调整；不要把示例网络误用于其他服务。

```sh
docker compose build
docker compose up -d
```

AstrBot 文转图地址：`http://t2i-lite:8000/text2img`。

- `POST /text2img/generate`：兼容 AstrBot 请求；返回图片，或通过 `json: true` 返回短期缓存地址。
- `GET /health`、`GET /text2img/health`：返回 `status: "ok"`、`engine: "typst"`、`style_protocol: 1`、`service_version: "2.1.0-themes"`。
- `GET /templates`、`GET /text2img/templates`：返回 `templates` 数组、`default: "codex"`、`style_protocol: 1`、`service_version: "2.1.0-themes"`。每项有 `id/name/description/default_brand_name/default_subtitle/has_default_avatar`，不公开服务器路径、用户头像或配置。
- `GET /text2img/data/<id>`：读取短期图片缓存。

[主题与模型页脚插件](https://github.com/qing-yi-5427/astrbot-plugins/tree/main/plugins/astrbot_plugin_t2i_style) 通过 `tmpldata.model_name` 传入本次回复模型名，并提供管理员控制、会话／全局默认、自定义头像与 Git 主题同步。它已合并旧独立页脚插件的功能，请只启用合并版。插件在合集仓库维护，不是本 Docker 项目的一部分。

## 样式协议 v1

请求中的 `tmpldata.t2i_style` 是可选对象；不传则保持旧版路由。示例：

```json
{
  "tmpl": "<div class=\"brand-name\">Amadeus</div>",
  "tmpldata": {
    "text": "# 今日记录\n\n中文正文 **重点**",
    "version": "v4.28.2",
    "model_name": "实际回复模型",
    "t2i_style": {
      "template": "miku",
      "show_avatar": true,
      "show_footer": true
    }
  },
  "options": {"type": "png"}
}
```

只传 `template` 时继承对应主题的默认品牌和副标题。字段规则：

| 字段 | 规则 |
|---|---|
| `template` | 可选，默认为 `codex`；内置主题使用表中六个 ID，外部主题必须同时携带对应的有效 `t2i_theme` 包 |
| `brand_name` | 可选字符串，最多 64 字符；明确传入时覆盖主题默认，空字符串也有效 |
| `subtitle` | 可选字符串，最多 96 字符；明确传入时覆盖主题默认，空字符串也有效 |
| `show_avatar` | 严格布尔值，默认 `true`；关闭后不读头像文件、不保留头像占位 |
| `show_footer` | 严格布尔值，默认 `true`；关闭模型／品牌页脚；所有内置主题均不再追加独立署名条 |
| `avatar_base64` | 可选 PNG/JPEG/WebP 的 Base64 字符串；也支持相应的 `data:image/...;base64,` 前缀；空串或省略回到主题默认头像 |

未知字段、非法模板、错误类型、过长名称、损坏或超限头像返回 HTTP 422。头像解码原始数据最多 512000 字节，尺寸最多 1024×1024；服务验证后取首帧、去除元数据并转换为最多 512×512 的 WebP。不会根据请求读取本地头像路径、下载 URL 或处理 SVG 头像。

头像优先级：有效 `avatar_base64` > 当前主题默认头像。五套新主题忽略旧 HTML 模板里的 Amadeus 头像，清除自定义头像后回到各自的默认头像；`codex` 单独保留旧 HTML 内嵌 WebP 头像兼容，自定义 Base64 仍优先。所有 Typst 图片引用均为临时目录内的固定 `avatar.webp`，不从用户字段拼接路径。

品牌、副标题、版本、模型名都是转义后的字符串数据；占位符仅作单遍替换，用户文本中的 `{{CONTENT}}` 等不会再次替换。Typst 编译根目录限制在本次临时目录内。显式样式请求始终本地处理，不会把自定义头像或样式转发给旧远端渲染服务。

## 头像生成记录与字体

五套新主题头像（初音未来、派蒙、帕姆、伊埃斯、调月莉音）均通过 Codex 内置 GPT 生图服务重新绘制；未将此前下载的官方表情、立绘或其他插画作为输入。完整提示词与原始 PNG/WebP 哈希见 [生成记录](<assets/themes/GENERATION.json>)，当前素材说明见 [SOURCES.md](<assets/themes/SOURCES.md>)。角色身份与主题配色保留，Codex 继续使用原有头像。

所有主题的输出直接结束在模板画布边界，不再附加 46 像素的浅灰署名条；本次真实回复模型页脚仍由 `show_footer` 独立控制。

默认字体为 [Adobe 思源黑体](https://github.com/adobe-fonts/source-han-sans) 简体中文静态字库 `SourceHanSansSC-Regular.otf` 和 `SourceHanSansSC-Bold.otf`，Typst family 为 `Source Han Sans SC`。字库与原始 [OFL 许可](<fonts/OFL-SourceHanSansSC.txt>) 随镜像保留。字体下载的 Git blob SHA-1 分别为 `8113ad53da18b6a08b133c6c460ae1d818a0f865`（Regular）和 `3b33e77fce75424e20c90eb2feaa489e38ebe9d7`（Bold），完整文件 SHA256 见资源清单。代码的拉丁字符使用 DejaVu Sans Mono，中文回退到思源黑体，Emoji 使用 Noto Color Emoji。

## 支持范围与限制

支持常用 Markdown 排版，不是通用浏览器，不完整渲染 HTML/CSS、脚本、LaTeX 或 Mermaid。Markdown 外链图片仅显示说明，不自动加载。

没有显式样式字段的非 Codex HTML 模板仍先尝试原 AstrBot 远端服务；失败且模板数据包含 `text` 时使用本地 Codex 样式。正文上限 100000 字符、图片高度上限 25000 像素、并发 2 张。

## 测试

[Markdown 测试](<tests/test_markdown_typst.py>) 检查转换语义，[服务测试](<tests/test_service.py>) 检查旧协议，[主题测试](<tests/test_themes.py>) 检查原布局／当前默认与显式 Codex 的像素一致性、六主题真实编译、安全转义和开关，[正式主题服务测试](<tests/test_series_service.py>) 检查元数据默认继承、HTTP 路由与 catalog、头像格式／大小限制、头像优先级、无外加署名栏和真实字体注册。[原有渲染测试](<tests/test_rendering.py>) 继续检查 Emoji、旁白颜色与常见 Markdown 的实际渲染。

下面的命令对构建后的镜像运行全部测试；关闭外部网络，不访问模型或聊天平台，HTTP 测试只使用容器内环回地址：

```sh
docker run --rm --network none --read-only --tmpfs /tmp:size=128m,mode=1777 \
  -e PYTHONPATH=/app -v "$PWD/tests:/app/tests:ro" --entrypoint python \
  astrbot-t2i-lite:2.1.0-themes -m unittest discover -s /app/tests -p 'test_*.py'
```

在 macOS bundled Python 环境应使用其自带 Pillow，并通过 `PYTHONPATH` 指向仓库中的 Mistune wheel，不要用 pip 安装的不同 Pillow 覆盖带签名扩展。真实渲染测试需要 Typst CLI；本地可通过 `TYPST_FONT_PATHS` 指向仓库字体目录。

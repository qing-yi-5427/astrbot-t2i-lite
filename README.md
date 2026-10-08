# AstrBot 轻量文转图服务

独立 Docker 项目，使用 Typst 排版、Pillow 编码，不启动浏览器。兼容 AstrBot 文转图请求，支持 Markdown、中文、Emoji、代码、表格、任务列表和模型页脚。

## 同步状态（2026-10-08）

本仓库是本地开发文件的源码快照，对应本地记录的 `1.4.1-aside-label`。尚未连接 NAS 核对当前运行版本，当前快照不能直接完整构建：原 Dockerfile 引用的以下资源不在本地，需从实际部署目录补齐后验证。

- `requirements.txt`
- `wheels/` 中的离线 Python 依赖
- `fonts/NotoSansSC-wght.ttf`、`fonts/NotoSerifSC-wght.ttf`
- `fonts/OFL-NotoSansSC.txt`、`fonts/OFL-NotoSerifSC.txt`
- `assets/avatar.webp`

已包含 Noto Color Emoji 字体及其 OFL 许可。没有上传运行配置、聊天数据或部署备份。仓库保持私有；不要把本次源码上传理解为已重新部署或已通过 Docker 构建。

## 部署接口

原 Compose 使用外部网络 `astrbot-napcat_astrbot_network`，容器别名为 `t2i-lite`，未发布宿主机端口。使用前根据自己的 AstrBot 网络调整 Compose。补齐以上文件后，可在本目录运行：

```sh
docker compose build
docker compose up -d
```

AstrBot 文转图地址：`http://t2i-lite:8000/text2img`；健康检查：`http://t2i-lite:8000/health`。

[回复模型页脚插件](https://github.com/qing-yi-5427/astrbot_plugin_model_footer) 在独立仓库维护，通过 `tmpldata.model_name` 传入本次回复的模型名。该插件不是本 Docker 项目的一部分。

## 支持范围与限制

支持常用 Markdown 排版和本地实验报告样式。不是通用浏览器，不完整渲染 HTML/CSS、脚本、LaTeX 或 Mermaid。Markdown 外链图片仅显示说明，不自动加载。

非 Codex 自定义 HTML 模板会先尝试原 AstrBot 远端渲染服务；失败且模板数据包含 `text` 时使用本地样式。上限为正文 100,000 字符、图片高度 25,000 像素、并发 2 张。

## 测试

`tests/test_markdown_typst.py` 检查转换，`tests/test_service.py` 检查服务逻辑，`tests/test_rendering.py` 需要实际 Typst、中文字体及头像资源。完整渲染测试须在补齐构建资源后执行。本次上传尚未验证容器构建及完整渲染。

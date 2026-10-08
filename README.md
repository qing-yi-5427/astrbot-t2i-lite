# AstrBot 轻量文转图服务

独立 Docker 项目，使用 Typst 排版、Pillow 编码，不启动浏览器。兼容 AstrBot 文转图请求，支持 Markdown、中文、Emoji、代码、表格、任务列表和模型页脚。

## 同步状态（2026-10-08）

已从 NAS 当前运行的 `astrbot-t2i-lite:1.4.1-aside-label` 部署目录补齐源码、依赖、字体及许可、默认头像和离线 wheel。服务入口、Markdown 转换器和 Typst 样式与运行容器逐文件 SHA-256 一致。

完整 Dockerfile 已在 NAS 构建成功，验证镜像与生产容器分开；新镜像中 46 项转换、服务及实际渲染测试全部通过（包括 Emoji 和样式像素检查）。二进制资源校验值记录在 `assets.sha256.json`。离线 wheel 对应 Linux x86_64 / Python 3.12；目前 Compose 应在该架构运行。首次构建仍需拉取 Dockerfile 的基础镜像，或提前在本机缓存这些镜像。

仓库保持私有，不包含聊天数据、密钥或部署备份。

## 部署接口

原 Compose 使用外部网络 `astrbot-napcat_astrbot_network`，容器别名为 `t2i-lite`，未发布宿主机端口。使用前根据自己的 AstrBot 网络调整 Compose。可在本目录运行：

```sh
docker compose build
docker compose up -d
```

AstrBot 文转图地址：`http://t2i-lite:8000/text2img`；健康检查：`http://t2i-lite:8000/health`。

[回复模型页脚插件](https://github.com/qing-yi-5427/astrbot-plugins/tree/main/plugins/astrbot_plugin_model_footer) 在插件合集仓库维护，通过 `tmpldata.model_name` 传入本次回复的模型名。该插件不是本 Docker 项目的一部分。

## 支持范围与限制

支持常用 Markdown 排版和本地实验报告样式。不是通用浏览器，不完整渲染 HTML/CSS、脚本、LaTeX 或 Mermaid。Markdown 外链图片仅显示说明，不自动加载。

非 Codex 自定义 HTML 模板会先尝试原 AstrBot 远端渲染服务；失败且模板数据包含 `text` 时使用本地样式。上限为正文 100,000 字符、图片高度 25,000 像素、并发 2 张。

## 测试

`tests/test_markdown_typst.py` 检查转换，`tests/test_service.py` 检查服务逻辑，`tests/test_rendering.py` 需要实际 Typst、中文字体及头像资源。使用下面的命令对构建后的镜像运行测试（网络关闭，不会访问模型或聊天平台）：

```sh
docker run --rm --network none --read-only --tmpfs /tmp:size=128m,mode=1777 \
  -e PYTHONPATH=/app -v "$PWD/tests:/tests:ro" --entrypoint python \
  astrbot-t2i-lite:1.4.1-aside-label -m unittest discover -s /tests -p 'test_*.py'
```

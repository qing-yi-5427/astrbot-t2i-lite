FROM ghcr.io/typst/typst:0.15.1 AS typst
FROM soulter/astrbot:latest AS astrbot-fonts

FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    XDG_CACHE_HOME=/tmp/typst-cache

COPY --from=typst /bin/typst /usr/local/bin/typst
COPY --from=astrbot-fonts /usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc /usr/share/fonts/opentype/noto/
COPY --from=astrbot-fonts /usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf /usr/share/fonts/truetype/dejavu/
COPY fonts/NotoSansSC-wght.ttf fonts/NotoSerifSC-wght.ttf /usr/share/fonts/truetype/
COPY --chmod=644 fonts/SourceHanSansSC-Regular.otf fonts/SourceHanSansSC-Bold.otf /usr/share/fonts/truetype/
COPY --chmod=644 fonts/NotoColorEmoji.ttf /usr/share/fonts/truetype/
COPY fonts/OFL-NotoSansSC.txt fonts/OFL-NotoSerifSC.txt /app/
COPY --chmod=644 fonts/OFL-SourceHanSansSC.txt /app/
COPY --chmod=644 fonts/OFL-NotoColorEmoji.txt /app/
RUN chmod 755 /app \
    && chmod 644 /usr/share/fonts/truetype/NotoSansSC-wght.ttf \
    /usr/share/fonts/truetype/NotoSerifSC-wght.ttf \
    /app/OFL-NotoSansSC.txt /app/OFL-NotoSerifSC.txt
WORKDIR /app
COPY requirements.txt ./
COPY wheels/ /wheels/
RUN pip install --no-index --find-links=/wheels --no-cache-dir -r requirements.txt
COPY --chmod=644 service.py markdown_typst.py codex_style.typ themes.py theme_package.py ./
COPY templates/ /app/templates/
COPY --chmod=644 assets/avatar.webp /app/assets/avatar.webp
COPY --chmod=644 assets/themes/miku.webp assets/themes/genshin.webp assets/themes/starrail.webp assets/themes/zzz.webp assets/themes/rio.webp assets/themes/SOURCES.md /app/assets/themes/
COPY --chmod=644 assets/themes/GENERATION.json /app/assets/themes/
RUN chmod 755 /app/assets /app/assets/themes

RUN groupadd -g 10001 renderer && useradd -u 10001 -g renderer -M renderer
USER renderer
EXPOSE 8000
CMD ["python", "service.py"]

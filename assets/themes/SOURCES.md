# Theme avatars — generated illustrations

On 2026-11-09 the user requested removing the external attribution strip from every theme and replacing the five externally sourced avatars with newly generated illustrations. Current `miku.webp`, `genshin.webp`, `starrail.webp`, `zzz.webp`, and `rio.webp` were generated through Codex's built-in `image_gen` service. No previous official sticker, game portrait, KEI illustration, or external fan artwork was supplied as an image input.

| Asset | Character | Visual identity |
|---|---|---|
| `miku.webp` | Hatsune Miku / 初音未来 | Turquoise twin-tails and eyes, headset, gray top and teal necktie |
| `genshin.webp` | Paimon / 派蒙 | White hair, star accessory, floating crown, cream and peach outfit |
| `starrail.webp` | Pom-Pom / 帕姆 | Rabbit ears, blue eyes, red conductor hat and jacket |
| `zzz.webp` | Eous / 伊埃斯 | White rabbit-ear hood, black face panel, green eyes, orange scarf |
| `rio.webp` | Tsukatsuki Rio / 调月莉音 | Black hair, red eyes, geometric halo, regular school appearance |

The images are new, non-official fan illustrations of the named characters; character names and designs remain associated with their original owners. This provenance record does not claim ownership of the underlying characters or a new license to them.

Processing only resizes the generated square PNGs to 512×512 and encodes them as WebP. Generation prompts and source/output hashes are retained in `GENERATION.json`; full generated PNGs are saved in the fnos workspace at `output/imagegen/theme-avatars-20261109/`. The original downloaded assets and their old source records remain in private deployment rollback backups, not in the active avatar files.

All theme renderings now end at the template's own canvas. The service does not append an artwork/source strip. The actual reply model footer is a separate feature and remains available. Codex keeps its existing user-selected avatar and layout.

Assets have fixed local paths, are below 512000 bytes, and are at most 1024 pixels per dimension. Rendering never downloads character images. Custom administrative avatar overrides continue to work.

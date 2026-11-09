#let canvas = rgb("#e8e2d8")
#let paper = rgb("#fffcf4")
#let soft = rgb("#f4efe2")
#let ink = rgb("#332d27")
#let inksoft = rgb("#82776a")
#let muted = rgb("#82776a")
#let linecolor = rgb("#cec3af")
#let accent = rgb("#ae8c5f")
#let accentsoft = rgb("#f2e8d6")
#let accentdeep = rgb("#80572f")
#let asidebg = rgb("#42382e")
#let asideink = rgb("#fbf3e4")
#let asideaccent = rgb("#e7c497")
#let asidelabel = rgb("#edd7a8")
#let quotebg = rgb("#f2ecdd")
#let quoteink = rgb("#65503b")
#let quoteline = rgb("#b39a75")
#let codebg = rgb("#302c27")
#let codehead = rgb("#494237")
#let codeink = rgb("#faf1df")
#let tableheadbg = rgb("#eae0cc")
#set page(width: 360pt, height: auto, margin: (x: 14pt, y: 17pt), fill: canvas)
#set text(font: ("Source Han Sans SC", "Noto Sans CJK SC", "Noto Color Emoji"), size: 12pt, fill: ink)
#set par(leading: 0.65em, spacing: 0pt)
#block(width: 100%, fill: paper, inset: (x: 21pt, top: 16pt, bottom: 17pt))[
  #grid(columns: (1fr, auto), column-gutter: 8pt,
    [#text("THE DAILY / 每日纪事", size: 8pt, weight: "bold", fill: accentdeep)],
    [#text({{VERSION}}, size: 8pt, fill: muted)])
  #v(8pt)
  #line(length: 100%, stroke: 1.4pt + ink)
  #v(11pt)
  #align(center)[
    #if {{SHOW_AVATAR}} [
      #box(width: 27pt, height: 27pt, radius: 50%, clip: true, stroke: 0.7pt + accent)[#image("avatar.webp", width: 27pt, height: 27pt, fit: "cover")]
      #v(5pt)
    ]
    #text({{BRAND}}, size: 25pt, weight: "bold")
    #linebreak()
    #text({{SUBTITLE}}, size: 9pt, fill: inksoft)
  ]
  #v(12pt)
  #line(length: 100%, stroke: 1.4pt + ink)
  #v(2pt)
  #line(length: 100%, stroke: 0.4pt + ink)
  #v(12pt)
{{CONTENT}}
  #if {{SHOW_FOOTER}} [
    #v(14pt)
    #line(length: 100%, stroke: 0.5pt + linecolor)
    #v(7pt)
    #align(center)[#text({{FOOTER}}, size: 8pt, fill: muted)]
  ]
]

#let canvas = rgb("#090f1b")
#let paper = rgb("#121d2b")
#let soft = rgb("#18283a")
#let ink = rgb("#e4edf6")
#let inksoft = rgb("#9fb6c7")
#let muted = rgb("#9fb6c7")
#let linecolor = rgb("#30485a")
#let accent = rgb("#75e2c1")
#let accentsoft = rgb("#203c43")
#let accentdeep = rgb("#88efd0")
#let asidebg = rgb("#20313f")
#let asideink = rgb("#ecf8fc")
#let asideaccent = rgb("#8be4cb")
#let asidelabel = rgb("#e8cd89")
#let quotebg = rgb("#1c3437")
#let quoteink = rgb("#c0e9dc")
#let quoteline = rgb("#65ba9e")
#let codebg = rgb("#080f19")
#let codehead = rgb("#213443")
#let codeink = rgb("#d0f6e5")
#let tableheadbg = rgb("#233f48")
#set page(width: 360pt, height: auto, margin: (x: 14pt, y: 17pt), fill: canvas)
#set text(font: ("Source Han Sans SC", "Noto Sans CJK SC", "Noto Color Emoji"), size: 12pt, fill: ink)
#set par(leading: 0.65em, spacing: 0pt)
#block(width: 100%, fill: paper, radius: 4pt, stroke: 0.7pt + linecolor)[
  #block(width: 100%, fill: soft, inset: (x: 13pt, y: 9pt))[
    #grid(columns: (5pt, 5pt, 5pt, 1fr), column-gutter: 5pt,
      [#circle(radius: 2.5pt, fill: rgb("#ee8e8e"))],
      [#circle(radius: 2.5pt, fill: rgb("#e7c27e"))],
      [#circle(radius: 2.5pt, fill: accent)],
      [#align(right)[#text("SESSION / " + {{VERSION}}, size: 8pt, fill: muted)]])
  ]
  #block(width: 100%, inset: (x: 19pt, y: 18pt))[
    #let identity = [#text("> ", fill: accent, weight: "bold")#text({{BRAND}}, size: 17pt, weight: "bold", fill: accent)#linebreak()#text({{SUBTITLE}}, size: 9pt, fill: inksoft)]
    #if {{SHOW_AVATAR}} {
      grid(columns: (1fr, 32pt), column-gutter: 10pt, identity,
        [#box(width: 32pt, height: 32pt, radius: 4pt, clip: true, stroke: 1pt + accent)[#image("avatar.webp", width: 32pt, height: 32pt, fit: "cover")]])
    } else { identity }
  ]
  #block(width: 100%, height: 0.5pt, fill: linecolor)
  #block(width: 100%, inset: (x: 21pt, top: 14pt, bottom: 19pt))[
{{CONTENT}}
  ]
  #if {{SHOW_FOOTER}} [
    #block(width: 100%, fill: soft, inset: (x: 15pt, y: 10pt))[
      #text("● ", fill: accent, size: 8pt)#text({{FOOTER}}, size: 8pt, fill: muted)
    ]
  ]
]

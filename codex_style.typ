#let canvas = rgb("#eef2f8")
#let paper = rgb("#fafdff")
#let soft = rgb("#f2f6fc")
#let ink = rgb("#203045")
#let inksoft = rgb("#70829b")
#let muted = rgb("#70829b")
#let linecolor = rgb("#d9e3ef")
#let accent = rgb("#6dc8ff")
#let accentsoft = rgb("#e9f3ff")
#let accentdeep = rgb("#28658e")
#let asidebg = rgb("#142e46")
#let asideink = rgb("#eef6ff")
#let asideaccent = rgb("#80cfff")
#let asidelabel = rgb("#e6c58d")
#let quotebg = rgb("#edf8f2")
#let quoteink = rgb("#2c5140")
#let quoteline = rgb("#65a88a")
#let codebg = rgb("#25262e")
#let codehead = rgb("#333541")
#let codeink = rgb("#edf0fb")
#let tableheadbg = rgb("#e1edf9")

#set page(width: 360pt, height: auto, margin: (x: 14pt, y: 17pt), fill: canvas)
#set text(font: ("Noto Sans SC", "Noto Sans CJK SC", "Noto Color Emoji"), size: 12pt, fill: ink)
#set par(leading: 0.65em, spacing: 0pt)

#block(width: 100%, fill: paper, radius: 8pt, inset: 0pt, stroke: 0.5pt + linecolor)[
  #block(width: 100%, height: 3pt, fill: accent)
  #block(width: 100%, inset: (x: 19pt, y: 14pt))[
    #grid(columns: (1fr, auto), column-gutter: 8pt,
      [
        #grid(columns: (29pt, 1fr), column-gutter: 8.5pt,
          [#box(width: 29pt, height: 29pt, radius: 50%, clip: true, stroke: 1.5pt + accent, inset: 0pt)[
            #image("avatar.webp", width: 29pt, height: 29pt, fit: "cover")
          ]],
          [
            #text(size: 14pt, weight: "bold", fill: ink)[Amadeus]
            #linebreak()
            #text(size: 9pt, fill: inksoft)[powered by Astrbot]
          ]
        )
      ],
      [#box(fill: accentsoft, radius: 6pt, inset: (x: 7pt, y: 4pt))[
        #text({{VERSION}}, size: 8pt, weight: "bold", fill: accentdeep)
      ]]
    )
  ]
  #block(width: 100%, height: 0.5pt, fill: linecolor)
  #block(width: 100%, inset: (x: 21pt, top: 19pt, bottom: 22pt))[
{{CONTENT}}
  ]
  #block(width: 100%, height: 0.5pt, fill: linecolor)
  #block(width: 100%, fill: soft, inset: (x: 17pt, y: 12pt))[
    #align(center)[#text({{FOOTER}}, size: 8.5pt, fill: muted)]
  ]
]

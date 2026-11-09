#let canvas = rgb("#e8eee3")
#let paper = rgb("#fcfcf2")
#let soft = rgb("#edf2e3")
#let ink = rgb("#314737")
#let inksoft = rgb("#72816a")
#let muted = rgb("#72816a")
#let linecolor = rgb("#d3ddc5")
#let accent = rgb("#8fa966")
#let accentsoft = rgb("#e6eed8")
#let accentdeep = rgb("#4e7139")
#let asidebg = rgb("#2c4437")
#let asideink = rgb("#f0f7e9")
#let asideaccent = rgb("#bddc9b")
#let asidelabel = rgb("#e7ce9b")
#let quotebg = rgb("#edf3df")
#let quoteink = rgb("#456037")
#let quoteline = rgb("#97b674")
#let codebg = rgb("#27362c")
#let codehead = rgb("#3b4f3c")
#let codeink = rgb("#eef5e4")
#let tableheadbg = rgb("#e1eacb")
#set page(width: 360pt, height: auto, margin: (x: 14pt, y: 17pt), fill: canvas)
#set text(font: ("Source Han Sans SC", "Noto Sans CJK SC", "Noto Color Emoji"), size: 12pt, fill: ink)
#set par(leading: 0.65em, spacing: 0pt)
#block(width: 100%, fill: paper, radius: 2pt, stroke: (left: 5pt + accent, rest: 0.5pt + linecolor))[
  #block(width: 100%, inset: (x: 18pt, top: 17pt, bottom: 12pt))[
    #grid(columns: (1fr, auto), column-gutter: 8pt,
      [#text("FIELD NOTES / 森林手记", size: 8pt, weight: "bold", fill: accentdeep)],
      [#text({{VERSION}}, size: 8pt, fill: muted)])
    #v(13pt)
    #let identity = [#text({{BRAND}}, size: 19pt, weight: "bold")#linebreak()#text({{SUBTITLE}}, size: 9pt, fill: inksoft)]
    #if {{SHOW_AVATAR}} {
      grid(columns: (35pt, 1fr), column-gutter: 11pt,
        [#box(width: 35pt, height: 35pt, radius: 7pt, clip: true, stroke: 1pt + accent)[#image("avatar.webp", width: 35pt, height: 35pt, fit: "cover")]], identity)
    } else { identity }
  ]
  #block(width: 100%, inset: (x: 18pt, y: 0pt))[#line(length: 100%, stroke: 0.6pt + linecolor)]
  #block(width: 100%, inset: (x: 21pt, top: 12pt, bottom: 18pt))[
{{CONTENT}}
  ]
  #if {{SHOW_FOOTER}} [
    #block(width: 100%, fill: soft, inset: (x: 17pt, y: 12pt))[
      #text("—  " + {{FOOTER}}, size: 8pt, fill: muted)
    ]
  ]
]

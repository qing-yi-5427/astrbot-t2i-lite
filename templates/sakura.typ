#let canvas = rgb("#faeaf0")
#let paper = rgb("#fffafd")
#let soft = rgb("#fcf0f5")
#let ink = rgb("#543346")
#let inksoft = rgb("#956d82")
#let muted = rgb("#956d82")
#let linecolor = rgb("#ebcddc")
#let accent = rgb("#df8daf")
#let accentsoft = rgb("#f9e1ec")
#let accentdeep = rgb("#a74870")
#let asidebg = rgb("#533548")
#let asideink = rgb("#fff2f9")
#let asideaccent = rgb("#ffb5d5")
#let asidelabel = rgb("#efcf9d")
#let quotebg = rgb("#f9eaf2")
#let quoteink = rgb("#79465e")
#let quoteline = rgb("#d69ab6")
#let codebg = rgb("#342b39")
#let codehead = rgb("#514054")
#let codeink = rgb("#f7ecf8")
#let tableheadbg = rgb("#f5dce8")
#set page(width: 360pt, height: auto, margin: (x: 14pt, y: 17pt), fill: canvas)
#set text(font: ("Source Han Sans SC", "Noto Sans CJK SC", "Noto Color Emoji"), size: 12pt, fill: ink)
#set par(leading: 0.65em, spacing: 0pt)
#block(width: 100%, fill: paper, radius: 15pt, stroke: 0.6pt + linecolor)[
  #block(width: 100%, fill: soft, radius: (top: 15pt), inset: (x: 20pt, top: 19pt, bottom: 14pt))[
    #align(center)[
      #if {{SHOW_AVATAR}} [
        #box(width: 42pt, height: 42pt, radius: 50%, clip: true, stroke: 2pt + accent)[#image("avatar.webp", width: 42pt, height: 42pt, fit: "cover")]
        #v(7pt)
      ]
      #text({{BRAND}}, size: 18pt, weight: "bold", fill: accentdeep)
      #linebreak()
      #text({{SUBTITLE}}, size: 9pt, fill: inksoft)
      #v(9pt)
      #box(fill: paper, radius: 20pt, inset: (x: 11pt, y: 3pt), stroke: 0.5pt + linecolor)[#text("✿  " + {{VERSION}} + "  ✿", size: 8pt, fill: accentdeep)]
    ]
  ]
  #block(width: 100%, inset: (x: 21pt, top: 14pt, bottom: 20pt))[
{{CONTENT}}
  ]
  #if {{SHOW_FOOTER}} [
    #block(width: 100%, inset: (x: 18pt, top: 0pt, bottom: 16pt))[
      #align(center)[#text("· · ·", fill: accent)#v(5pt)#text({{FOOTER}}, size: 8pt, fill: muted)]
    ]
  ]
]

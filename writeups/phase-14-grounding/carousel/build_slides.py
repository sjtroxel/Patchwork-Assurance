#!/usr/bin/env python3
"""Phase 14 write-up carousel. Nine self-contained 1080x1350 portrait slides.

Chrome matches the launch carousel (~/job-search-headquarters/portfolio/patchwork-launch/carousel):
navy gradient, quilt seamstrip, gold kicker, cream text, patchworkassurance.com footer, system fonts.
Bodies are inline HTML/CSS infographics (no external assets). Data series: grounded = teal #199e70,
raw = terracotta #d95926 (both validated CVD-safe; both live in the seamstrip). All numbers are
audited from eval/results/judged-20260721T*.json (see ../README.md). render.sh rasterizes to 1620x2025.
"""

import pathlib

DIR = pathlib.Path(__file__).parent

CSS = """
*{margin:0;padding:0;box-sizing:border-box;}
html,body{background:#0f1626;}
.slide{width:1080px;height:1350px;position:relative;overflow:hidden;
 background:linear-gradient(150deg,#1b2942,#26384f);color:#f3ece1;
 font-family:"Segoe UI",system-ui,-apple-system,Roboto,"Helvetica Neue",Arial,sans-serif;
 padding:78px 76px 52px;display:flex;flex-direction:column;}
.seamstrip{position:absolute;top:0;left:0;right:0;height:14px;display:flex;}
.seamstrip i{flex:1;}
.seamstrip i:nth-child(6n+1){background:#21304c;}
.seamstrip i:nth-child(6n+2){background:#7c2f3b;}
.seamstrip i:nth-child(6n+3){background:#2f6f5f;}
.seamstrip i:nth-child(6n+4){background:#d6a43e;}
.seamstrip i:nth-child(6n+5){background:#2f4b5e;}
.seamstrip i:nth-child(6n+6){background:#e9e0d2;}
.kicker{flex:none;font-size:22px;font-weight:700;letter-spacing:.2em;text-transform:uppercase;color:#d6a43e;}
h1{flex:none;font-size:60px;line-height:1.03;font-weight:800;letter-spacing:-1.4px;margin:16px 0 6px;text-wrap:balance;}
h1.sm{font-size:52px;}
.body{flex:1 1 auto;min-height:0;display:flex;flex-direction:column;justify-content:center;gap:22px;margin:24px 0 18px;}
.cap{flex:none;font-size:26px;line-height:1.42;color:#cdc6b8;max-width:960px;}
.foot{flex:none;margin-top:20px;display:flex;align-items:center;gap:15px;font-size:20px;color:#bcb6aa;}
.foot .url{color:#f3ece1;font-weight:700;}
.foot .dot{width:5px;height:5px;border-radius:50%;background:#d6a43e;}
.teal{color:#3fb98f;} .terra{color:#e0692e;} .gold{color:#e0b659;}

/* legend chips */
.legend{display:flex;gap:26px;font-size:23px;color:#cdc6b8;align-items:center;}
.legend b{font-weight:600;color:#f3ece1;}
.chip{display:inline-block;width:20px;height:20px;border-radius:5px;vertical-align:-3px;margin-right:10px;}
.chip.g{background:#199e70;} .chip.r{background:#d95926;}

/* bar chart */
.bars{display:flex;flex-direction:column;gap:18px;}
.row{display:flex;align-items:center;gap:20px;}
.row .lab{flex:0 0 320px;font-size:24px;color:#e9e0d2;text-align:right;}
.row .lab small{display:block;font-size:17px;color:#9fb0c0;letter-spacing:.03em;text-transform:uppercase;}
.track{flex:1 1 auto;height:44px;background:rgba(243,236,225,.08);border-radius:8px;position:relative;}
.fill{height:100%;border-radius:8px;display:flex;align-items:center;justify-content:flex-end;
 padding-right:16px;font-weight:800;font-size:25px;color:#10161c;min-width:64px;}
.fill.g{background:#199e70;} .fill.r{background:#d95926;}

/* two flow columns */
.cols{display:flex;gap:26px;align-items:stretch;}
.col{flex:1;background:rgba(15,22,38,.5);border:1px solid rgba(243,236,225,.12);border-radius:16px;padding:30px 28px;}
.col.win{border-color:rgba(224,182,89,.6);box-shadow:0 0 0 2px rgba(224,182,89,.18),0 22px 50px rgba(0,0,0,.4);}
.col h3{font-size:24px;letter-spacing:.14em;text-transform:uppercase;margin-bottom:20px;}
.step{font-size:25px;line-height:1.32;color:#e9e0d2;padding:12px 0;border-bottom:1px solid rgba(243,236,225,.08);}
.step:last-child{border-bottom:none;}
.step .n{display:inline-block;color:#9fb0c0;font-weight:700;margin-right:10px;}

/* big stat cards */
.statcard{flex:1;border-radius:18px;padding:34px 32px;background:rgba(15,22,38,.55);border:1px solid rgba(243,236,225,.12);}
.statcard.win{border-color:rgba(224,182,89,.65);box-shadow:0 0 0 2px rgba(224,182,89,.2),0 22px 50px rgba(0,0,0,.42);}
.statcard .who{font-size:27px;font-weight:800;}
.statcard .mode{font-size:20px;letter-spacing:.12em;text-transform:uppercase;margin:4px 0 22px;}
.statcard .cost{font-size:70px;font-weight:800;line-height:1;letter-spacing:-2px;}
.statcard .cost small{font-size:26px;font-weight:600;color:#bcb6aa;letter-spacing:0;}
.statcard .m{font-size:25px;line-height:1.55;color:#e9e0d2;margin-top:18px;}
.statcard .m b{font-weight:800;}

/* 454 split */
.split{display:flex;gap:16px;align-items:stretch;height:150px;}
.split .seg{border-radius:12px;padding:24px 26px;display:flex;flex-direction:column;justify-content:center;}
.split .big{flex:449;background:rgba(25,158,112,.16);border:1px solid rgba(63,185,143,.5);}
.split .small{flex:60;background:rgba(217,89,38,.18);border:1px solid rgba(224,105,46,.6);align-items:center;text-align:center;}
.split .num{font-size:46px;font-weight:800;line-height:1;}
.split .small .num{font-size:40px;}
.split .desc{font-size:23px;color:#e9e0d2;margin-top:8px;line-height:1.3;}
.split .small .desc{font-size:18px;}

/* plain statement + bullets */
.big-statement{font-size:44px;line-height:1.28;font-weight:600;color:#f3ece1;text-wrap:balance;}
.bullets{display:flex;flex-direction:column;gap:20px;}
.bullets .b{font-size:29px;line-height:1.34;color:#e9e0d2;padding-left:34px;position:relative;}
.bullets .b::before{content:"";position:absolute;left:0;top:14px;width:14px;height:14px;border-radius:4px;background:#d6a43e;}
.twobox{display:flex;gap:26px;}
.twobox .bx{flex:1;border-radius:16px;padding:30px 30px;background:rgba(15,22,38,.5);border:1px solid rgba(243,236,225,.12);}
.twobox .bx h4{font-size:24px;letter-spacing:.1em;text-transform:uppercase;margin-bottom:16px;}
.twobox .bx p{font-size:26px;line-height:1.42;color:#e9e0d2;}
.hero-url{font-size:58px;font-weight:800;letter-spacing:-1px;color:#f3ece1;}
.hero-sub{font-size:29px;color:#cdc6b8;margin-top:16px;line-height:1.45;}
"""

FOOT = (
    '<div class="foot"><span class="url">patchworkassurance.com</span>'
    '<span class="dot"></span><span>Educational tool, not legal advice</span></div>'
)
SEAM = '<div class="seamstrip">' + "<i></i>" * 15 + "</div>"


def page(stem, kicker, headline, body, caption, h1cls=""):
    h1c = f" {h1cls}" if h1cls else ""
    return (
        f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{stem}</title>'
        f'<style>{CSS}</style></head><body><div class="slide">{SEAM}'
        f'<div class="kicker">{kicker}</div>'
        f'<h1 class="{h1c.strip()}">{headline}</h1>'
        f'<div class="body">{body}</div>'
        f'<div class="cap">{caption}</div>{FOOT}</div></body></html>'
    )


# ---- bar chart data (audited; resolve % descending -> the staircase) ----
BAR_ROWS = [
    ("Fable 5", "with the system", 100, "g"),
    ("DeepSeek V4", "with the system", 100, "g"),
    ("Sonnet 5", "with the system", 100, "g"),
    ("GPT-5.6 Sol", "with the system", 98, "g"),
    ("Fable 5", "model alone", 43, "r"),
    ("Gemini 3.5", "model alone", 30, "r"),
    ("GPT-5.6 Sol", "model alone", 20, "r"),
]


def bars_html():
    rows = ""
    for model, mode, pct, cls in BAR_ROWS:
        # min visual width so the 20% bar still shows its label legibly
        w = max(pct, 7)
        rows += (
            f'<div class="row"><div class="lab">{model}<small>{mode}</small></div>'
            f'<div class="track"><div class="fill {cls}" style="width:{w}%">{pct}%</div></div></div>'
        )
    legend = (
        '<div class="legend"><span><span class="chip g"></span><b>With the system</b> (grounded)</span>'
        '<span><span class="chip r"></span><b>Model alone</b> (raw)</span></div>'
    )
    return f'<div class="bars">{rows}</div>{legend}'


SLIDES = [
    (
        "01-cover",
        "Patchwork Assurance · a field test",
        "Isn&rsquo;t this just<br>asking ChatGPT?",
        '<div class="big-statement">I built an AI tool for US state AI-regulation law. '
        "So I put it up against the same frontier models it is built on.</div>"
        '<div class="legend" style="margin-top:10px">'
        '<span><span class="chip g"></span><b>The model, with my system</b></span>'
        '<span><span class="chip r"></span><b>The same model, alone</b></span></div>',
        "Same models. Same questions. The only difference is the system around them.",
    ),
    (
        "02-setup",
        "The experiment",
        "Same models,<br>measured two ways.",
        '<div class="cols">'
        '<div class="col"><h3 class="terra">Raw &mdash; model alone</h3>'
        '<div class="step"><span class="n">1</span>Ask the question</div>'
        '<div class="step"><span class="n">2</span>Model answers from memory</div>'
        '<div class="step"><span class="n">3</span>Hope it is the right law, and current</div></div>'
        '<div class="col win"><h3 class="teal">Grounded &mdash; with the system</h3>'
        '<div class="step"><span class="n">1</span>Ask the question</div>'
        '<div class="step"><span class="n">2</span>Retrieve the governing statutes</div>'
        '<div class="step"><span class="n">3</span>Model answers from the text</div>'
        '<div class="step"><span class="n">4</span>Every citation checked before it ships</div></div>'
        "</div>",
        "7 configurations. 12 real US state AI laws. About $20 of real API calls.",
    ),
    (
        "03-centerpiece",
        "The result that surprised me",
        "A penny model beat<br>a $5.83 model.",
        '<div class="cols">'
        '<div class="statcard win"><div class="who teal">DeepSeek V4</div>'
        '<div class="mode teal">with the system</div>'
        '<div class="cost">$0.11<small> total</small></div>'
        '<div class="m"><b>100%</b> valid citations<br><b>21 / 24</b> points covered</div></div>'
        '<div class="statcard"><div class="who terra">Fable 5</div>'
        '<div class="mode terra">model alone</div>'
        '<div class="cost">$5.83<small> total</small></div>'
        '<div class="m"><b>43%</b> valid citations<br><b>14 / 24</b> points covered</div></div>'
        "</div>",
        "The cheapest model in the test, wrapped in the system, beat the most expensive model asked on its own.",
    ),
    (
        "04-chart",
        "The number that matters",
        "How much cited law<br>actually governs.",
        bars_html(),
        "Raw, only 1 in 3 to 1 in 5 of the laws they cite governs the question. With the corpus, nearly all of it does.",
        "sm",
    ),
    (
        "05-honesty",
        "But are they hallucinating?",
        "No. I checked<br>all 454 by hand.",
        '<div class="split">'
        '<div class="seg big"><div class="num teal">449</div>'
        '<div class="desc">real, current laws &mdash; just not the one the question was about</div></div>'
        '<div class="seg small"><div class="num terra">5</div>'
        '<div class="desc">actual errors</div></div>'
        "</div>"
        '<div class="cap" style="margin-top:6px;color:#9fb0c0;font-size:22px">'
        "Of every raw citation that did not resolve to the governing corpus.</div>",
        "The raw models cite real law: federal statutes, state civil-rights codes, local ordinances. Breadth, not invention.",
    ),
    (
        "06-eli5",
        "The idea in one picture",
        "Closed book<br>vs. open book.",
        '<div class="twobox">'
        '<div class="bx"><h4 class="terra">Closed book</h4>'
        "<p>Answer from memory. Hope the memory is right, and hope the law did not change since training.</p></div>"
        '<div class="bx"><h4 class="teal">Open book</h4>'
        "<p>The right statute, open to the right page, as it reads today. Every citation checked before the answer ships.</p></div>"
        "</div>",
        "The model was always smart. Grounding just hands it the book.",
    ),
    (
        "07-boundary",
        "What this is not",
        "Frontier models<br>aren&rsquo;t the problem.",
        '<div class="bullets">'
        '<div class="b">Raw, they are remarkable. This is not &ldquo;models are bad.&rdquo;</div>'
        '<div class="b">But 50 states are writing their own AI law, with no federal floor.</div>'
        '<div class="b">A model alone cannot know which statute governs, or that it changed last month.</div>'
        '<div class="b">Small sample (12&ndash;13 cases), automated checks, not human legal review.</div>'
        "</div>",
        "Educational tool, not legal advice. A grounded starting point for a conversation with counsel.",
    ),
    (
        "08-moat",
        "The takeaway",
        "The moat was never<br>the model.",
        '<div class="big-statement">Everyone can call the same API I call. The value is the corpus, the '
        'retrieval, and the scope gate &mdash; <span class="gold">the boring engineering around the model.</span></div>',
        "That is the part that is actually mine.",
    ),
    (
        "09-close",
        "See it · read it",
        "Try it yourself.",
        '<div class="hero-url">patchworkassurance.com</div>'
        '<div class="hero-sub">The live tool, plus the full benchmark and every number, in the repo.<br>'
        "Built in Python.</div>",
        "Educational tool, not legal advice.",
    ),
]


def main():
    for slide in SLIDES:
        stem, kicker, headline, body, caption = slide[0], slide[1], slide[2], slide[3], slide[4]
        h1cls = slide[5] if len(slide) > 5 else ""
        html = page(stem, kicker, headline, body, caption, h1cls)
        (DIR / f"_slide_{stem}.html").write_text(html, encoding="utf-8")
        print("wrote", stem)


if __name__ == "__main__":
    main()

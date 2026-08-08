/**
 * Demo deck for Autopilot Asia 2026 Round 2 finals.
 *
 * Palette and logomark come from the app itself, so the slides and the live
 * product read as one thing when the presenter switches between them.
 *
 * Type is Calibri rather than the app's Funnel Display / Geologica. Those are
 * Google web fonts: they render in a browser but are not installed on a venue
 * laptop, so a deck using them would silently fall back to something arbitrary
 * on the machine that actually matters. Calibri ships with Office everywhere.
 */

const fs = require('fs')
const pptx = require('pptxgenjs')
const pres = new pptx()

// Must be set before any slide is added, or coordinates past 10" are written
// but land off-canvas.
pres.layout = 'LAYOUT_WIDE' // 13.33 x 7.5
pres.author = 'Service Desk Command Center'
pres.title = 'Service Desk Command Center — Autopilot Asia 2026'

const NAVY = '141A42'
const CORN = '8AA2DF'
const PURPLE = '5A64A3'
const MUTED_BG = 'F4F5F9'
const BORDER = 'E8EBF2'
const MUTED_FG = '6B7391'
const WHITE = 'FFFFFF'
const DARK_CARD = '1E2551'
const DARK_LINE = '2E3768'

const F = 'Calibri'
const M = 0.85

const img = f => 'image/png;base64,' + fs.readFileSync(f).toString('base64')
const LOGO_LIGHT = img('logo-light.png')   // light artwork, for dark slides
const LOGO_DARK = img('logo-dark.png')     // dark artwork, for light slides
const MARK_LIGHT = img('mark-light.png')
const MARK_DARK = img('mark-dark.png')

/* -------------------------------------------------------------- helpers -- */

function slide(dark) {
  const s = pres.addSlide()
  s.background = { color: dark ? NAVY : WHITE }
  // The app watermarks its cards with the logomark bleeding off the corner.
  // Same device here, so every slide carries the brand without a banner.
  s.addImage({
    data: dark ? MARK_LIGHT : MARK_DARK,
    x: 10.9, y: 4.7, w: 3.6, h: 3.6,
    transparency: dark ? 92 : 95,
  })
  return s
}

function eyebrow(s, text, dark) {
  s.addText(text.toUpperCase(), {
    x: M, y: 0.62, w: 11.6, h: 0.32,
    fontFace: F, fontSize: 12, bold: true, charSpacing: 2,
    color: dark ? CORN : MUTED_FG, margin: 0,
  })
}

function title(s, runs, y = 1.15, w = 11.4) {
  s.addText(runs, {
    x: M, y, w, h: 1.9,
    fontFace: F, fontSize: 40, bold: true, lineSpacing: 46,
    color: NAVY, margin: 0, valign: 'top',
  })
}

function body(s, text, y, o = {}) {
  s.addText(text, {
    x: o.x ?? M, y, w: o.w || 8.6, h: o.h || 0.9,
    fontFace: F, fontSize: o.size || 17, color: o.color || MUTED_FG,
    lineSpacing: o.lineSpacing || 26, margin: 0, valign: 'top',
    ...(o.bold ? { bold: true } : {}),
  })
}

function stats(s, items, y, dark) {
  const gap = 3.45
  items.forEach((it, i) => {
    const x = M + i * gap
    s.addText(it.n, {
      x, y, w: gap - 0.3, h: 1.0,
      fontFace: F, fontSize: 52, bold: true, margin: 0,
      color: it.accent ? CORN : (dark ? WHITE : NAVY),
    })
    s.addText(it.l.toUpperCase(), {
      x, y: y + 0.95, w: gap - 0.3, h: 0.62,
      fontFace: F, fontSize: 10.5, bold: true, charSpacing: 1, margin: 0,
      color: dark ? 'A8AECB' : MUTED_FG,
    })
  })
}

function numberedCard(s, x, y, w, num, heading, text, dark) {
  s.addShape(pres.ShapeType.roundRect, {
    x, y, w, h: 2.5, rectRadius: 0.12,
    fill: { color: dark ? DARK_CARD : MUTED_BG },
    line: { color: dark ? DARK_LINE : BORDER, width: 1 },
  })
  s.addShape(pres.ShapeType.ellipse, {
    x: x + 0.32, y: y + 0.3, w: 0.52, h: 0.52,
    fill: { color: CORN }, line: { color: CORN, width: 0 },
  })
  s.addText(num, {
    x: x + 0.32, y: y + 0.3, w: 0.52, h: 0.52,
    fontFace: F, fontSize: 15, bold: true, color: NAVY,
    align: 'center', valign: 'middle', margin: 0,
  })
  s.addText(heading, {
    x: x + 0.32, y: y + 1.0, w: w - 0.64, h: 0.62,
    fontFace: F, fontSize: 18, bold: true, margin: 0,
    color: dark ? WHITE : NAVY, valign: 'top',
  })
  s.addText(text, {
    x: x + 0.32, y: y + 1.62, w: w - 0.64, h: 0.72,
    fontFace: F, fontSize: 13, margin: 0, lineSpacing: 18,
    color: dark ? 'A8AECB' : MUTED_FG, valign: 'top',
  })
}

function quote(s, text, attr, y) {
  s.addShape(pres.ShapeType.roundRect, {
    x: M, y, w: 10.2, h: 1.55, rectRadius: 0.1,
    fill: { color: MUTED_BG }, line: { color: BORDER, width: 1 },
  })
  // A quote glyph reads as a mark rather than the forbidden accent stripe.
  s.addText('“', {
    x: M + 0.18, y: y + 0.02, w: 0.6, h: 0.7,
    fontFace: 'Cambria', fontSize: 44, bold: true, color: CORN, margin: 0,
  })
  s.addText(text, {
    x: M + 0.72, y: y + 0.24, w: 9.2, h: 0.78,
    fontFace: F, fontSize: 15, italic: true, color: NAVY,
    lineSpacing: 21, margin: 0, valign: 'top',
  })
  s.addText(attr.toUpperCase(), {
    x: M + 0.72, y: y + 1.06, w: 9.2, h: 0.3,
    fontFace: F, fontSize: 9.5, bold: true, charSpacing: 1,
    color: MUTED_FG, margin: 0,
  })
}

function pageNum(s, n, dark) {
  s.addText(String(n), {
    x: 12.3, y: 6.85, w: 0.5, h: 0.3,
    fontFace: F, fontSize: 10, align: 'right', margin: 0,
    color: dark ? '5A6497' : 'B4B9CC',
  })
}

/* ------------------------------------------------------------- 1 title --- */
let s = slide(true)
s.addImage({ data: LOGO_LIGHT, x: M, y: 0.55, w: 2.5, h: 0.66 })
s.addText('AUTOPILOT ASIA 2026 · ROUND 2 · TRACK 3', {
  x: M, y: 1.45, w: 11.6, h: 0.3,
  fontFace: F, fontSize: 12, bold: true, charSpacing: 2, color: CORN, margin: 0,
})
s.addText('Service Desk\nCommand Center.', {
  x: M, y: 1.95, w: 11.4, h: 2.3,
  fontFace: F, fontSize: 54, bold: true, color: WHITE,
  lineSpacing: 62, margin: 0, valign: 'top',
})
s.addText('An AI Employee that eliminates problems instead of processing tickets.', {
  x: M, y: 4.35, w: 8.8, h: 0.5,
  fontFace: F, fontSize: 19, color: 'C9CFE6', margin: 0,
})
stats(s, [{ n: '380', l: 'tickets that need never happen', accent: true }], 5.2, true)
s.addNotes('Open on the Elimination page already loaded. Lead with the idea, not the architecture.')
pageNum(s, 1, true)

/* ------------------------------------------------------------ 2 premise -- */
s = slide()
eyebrow(s, 'The premise')
title(s, [
  { text: 'Closing tickets faster is\n', options: { color: NAVY } },
  { text: 'the wrong goal.', options: { color: PURPLE } },
])
body(s, 'If 44 people request shared drive access every month, resolving those tickets quickly is being efficient at something that should not be happening.', 3.35, { w: 6.4 })
body(s, 'Everyone else optimises the queue. We went after what keeps filling it.', 4.85, { color: NAVY, bold: true, size: 19, w: 6.4 })

// Visual: the queue as repeating tickets, and the one thing underneath them.
const tx = 8.0
for (let i = 0; i < 5; i++) {
  s.addShape(pres.ShapeType.roundRect, {
    x: tx + i * 0.16, y: 2.55 + i * 0.14, w: 4.0, h: 0.62, rectRadius: 0.08,
    fill: { color: MUTED_BG }, line: { color: BORDER, width: 1 },
  })
}
s.addText('44 tickets', {
  x: tx + 0.9, y: 3.13, w: 3.0, h: 0.5,
  fontFace: F, fontSize: 17, bold: true, color: MUTED_FG, margin: 0, valign: 'middle',
})
s.addShape(pres.ShapeType.downArrow, {
  x: tx + 2.1, y: 4.12, w: 0.36, h: 0.62,
  fill: { color: CORN }, line: { color: CORN, width: 0 },
})
s.addShape(pres.ShapeType.roundRect, {
  x: tx, y: 5.0, w: 4.0, h: 0.86, rectRadius: 0.1,
  fill: { color: NAVY }, line: { color: NAVY, width: 0 },
})
s.addText('1 root cause', {
  x: tx, y: 5.0, w: 4.0, h: 0.86,
  fontFace: F, fontSize: 18, bold: true, color: WHITE,
  align: 'center', valign: 'middle', margin: 0,
})
s.addNotes('Everyone else closes tickets faster. We think that is the wrong goal.')
pageNum(s, 2)

/* -------------------------------------------------------- 3 three ideas -- */
s = slide(true)
eyebrow(s, 'What makes this different', true)
s.addText('Three choices. One idea.', {
  x: M, y: 1.15, w: 11.4, h: 0.9,
  fontFace: F, fontSize: 40, bold: true, color: WHITE, margin: 0,
})
const cw = 3.5
numberedCard(s, M, 2.5, cw, '1', 'Stop the tickets\nhappening', 'Find the root cause, propose the permanent fix, name the owner.', true)
numberedCard(s, M + cw + 0.35, 2.5, cw, '2', 'Know when\nto stop', 'Four refusal reasons, none overridable by urgency.', true)
numberedCard(s, M + (cw + 0.35) * 2, 2.5, cw, '3', 'Never invent\na number', 'A dash is honest. A zero is a claim.', true)
s.addText('All three are the same instinct: knowing where its own judgement runs out.', {
  x: M, y: 5.5, w: 11.0, h: 0.5,
  fontFace: F, fontSize: 16, color: 'A8AECB', margin: 0,
})
s.addNotes('These three are really one idea: knowing where its own judgement runs out.')
pageNum(s, 3, true)

/* ------------------------------------------------------ 4 worked example -- */
s = slide()
eyebrow(s, '01 · Stop the tickets happening')
title(s, [
  { text: '37 password resets\n', options: { color: NAVY } },
  { text: 'are one problem.', options: { color: PURPLE } },
])
body(s, 'A normal service desk resolves 37 tickets. Our agent noticed they were the same problem, checked the knowledge base, found no self-service route, and proposed building one.', 3.25, { w: 10.2, h: 0.8 })
quote(s,
  'Implement a Self-Service Password Reset portal integrated with MFA, so users verify their own identity and reset credentials without help desk intervention.',
  'Proposed by the Correlator · owner: IAM Team', 4.2)
s.addText([
  { text: 'Those 37 tickets stop arriving.  ', options: { color: NAVY } },
  { text: 'Not resolved faster. Gone.', options: { color: CORN } },
], { x: M, y: 6.05, w: 10.2, h: 0.5, fontFace: F, fontSize: 21, bold: true, margin: 0 })
s.addNotes('This is the whole differentiator in one example. Say "gone", not "prevented".')
pageNum(s, 4)

/* -------------------------------------------------------- 5 at scale ----- */
s = slide()
eyebrow(s, '01 · At scale')
title(s, [{ text: '460 tickets.\n15 actual problems.', options: { color: NAVY } }])
body(s, 'Two numbers, never blended. One is work already avoided. The other is conditional on a human approving each fix.', 3.3, { w: 5.7, h: 1.2 })
// Drawn directly rather than via stats(): this pair sits in a narrow column
// beside the chart and needs its own spacing.
;[
  { n: '40',  l: 'COLLAPSED TODAY\nWORK AVOIDED', c: NAVY },
  { n: '380', l: 'PREVENTABLE\nA FORECAST',       c: CORN },
].forEach((it, k) => {
  const x = M + k * 2.75
  s.addText(it.n, { x, y: 4.7, w: 2.55, h: 1.0,
    fontFace: F, fontSize: 50, bold: true, color: it.c, margin: 0 })
  s.addText(it.l, { x, y: 5.68, w: 2.55, h: 0.66,
    fontFace: F, fontSize: 10.5, bold: true, charSpacing: 1,
    color: MUTED_FG, margin: 0, lineSpacing: 13 })
})

// Native chart: the top classes, so the ranking is a picture not a claim.
s.addChart(pres.ChartType.bar, [{
  name: 'Tickets',
  labels: ['Shared drive', 'Printers offline', 'Mailbox quota', 'Guest wifi', 'Password resets'],
  values: [44, 43, 43, 40, 37],
}], {
  x: 7.0, y: 1.5, w: 5.6, h: 4.6,
  barDir: 'bar',
  chartColors: [NAVY, PURPLE, CORN, CORN, CORN],
  varyColors: true,
  showValue: true, dataLabelPosition: 'outEnd',
  dataLabelColor: MUTED_FG, dataLabelFontSize: 11, dataLabelFontFace: F,
  showLegend: false, showTitle: true,
  title: 'The five heaviest classes', titleColor: NAVY,
  titleFontSize: 13, titleFontFace: F,
  catAxisLabelColor: NAVY, catAxisLabelFontSize: 11, catAxisLabelFontFace: F,
  valAxisHidden: true,
  valGridLine: { style: 'none' },
  catGridLine: { style: 'none' },
  barGapWidthPct: 45,
})
s.addNotes('The "never blended" line is the one that shows you expected to be challenged.')
pageNum(s, 5)

/* -------------------------------------------------------- 6 the refusal -- */
s = slide()
eyebrow(s, '02 · Know when to stop')
title(s, [{ text: 'It refused the most\nurgent ticket in the queue.', options: { color: NAVY } }], 1.15, 6.7)
body(s, 'Highest priority. Already past SLA. A known fix available. Every incentive said act.', 3.3, { w: 6.6, h: 0.6 })
body(s, 'It stopped because two employees share a display name and it could not tell which of them had raised it. Applying a fix to the wrong person’s account to hit a deadline is not a win.', 4.0, { w: 6.6, h: 1.3, color: NAVY })
stats(s, [{ n: '32', l: 'tickets held back for that reason', accent: true }], 5.45)

// Visual: the precedence ladder, which is the actual mechanism.
const ladder = [
  ['Change control', 'an open approval outranks everything'],
  ['Access change', 'never automated, whatever the confidence'],
  ['Identity', 'exactly one match, or stop'],
  ['Confidence', 'below the gate, escalate'],
]
s.addText('PRECEDENCE, TOP DOWN', {
  x: 7.9, y: 1.5, w: 4.6, h: 0.3,
  fontFace: F, fontSize: 10, bold: true, charSpacing: 1.5, color: MUTED_FG, margin: 0,
})
ladder.forEach(([h, d], i) => {
  const y = 1.95 + i * 1.12
  s.addShape(pres.ShapeType.roundRect, {
    x: 7.9, y, w: 4.6, h: 0.92, rectRadius: 0.1,
    fill: { color: i === 0 ? NAVY : MUTED_BG },
    line: { color: i === 0 ? NAVY : BORDER, width: 1 },
  })
  s.addText(h, {
    x: 8.15, y: y + 0.14, w: 4.1, h: 0.34,
    fontFace: F, fontSize: 14, bold: true, margin: 0,
    color: i === 0 ? WHITE : NAVY,
  })
  s.addText(d, {
    x: 8.15, y: y + 0.48, w: 4.1, h: 0.34,
    fontFace: F, fontSize: 10.5, margin: 0,
    color: i === 0 ? 'A8AECB' : MUTED_FG,
  })
  if (i < 3) {
    s.addShape(pres.ShapeType.downArrow, {
      x: 10.02, y: y + 0.94, w: 0.16, h: 0.16,
      fill: { color: CORN }, line: { color: CORN, width: 0 },
    })
  }
})
s.addNotes('Slow down here. This is the moment that lands.')
pageNum(s, 6)

/* -------------------------------------------------------- 7 auditable --- */
s = slide()
eyebrow(s, '02 · And it is auditable')
title(s, [
  { text: 'Every refusal has\n', options: { color: NAVY } },
  { text: 'a reason on the record.', options: { color: PURPLE } },
])
body(s, 'ITSM-2212 had a fix ready and an open change request awaiting board approval. Change control outranks confidence, so the agent opened the approval in GitHub rather than shipping. A human reviewed it and upheld the block.', 3.25, { w: 10.4, h: 1.0 })
stats(s, [
  { n: '15,294', l: 'policy evaluations logged' },
  { n: '4', l: 'policies, editable without code' },
  { n: '176', l: 'waiting on a human', accent: true },
], 4.5)
body(s, 'Each evaluation names the rule, the threshold in force at that moment, and what it was compared against. A later edit never rewrites history.', 6.15, { w: 10.4, size: 14, h: 0.6 })
s.addNotes('Offer to change a threshold live if they want to see it take effect.')
pageNum(s, 7)

/* ------------------------------------------------------ 8 blank metric --- */
s = slide()
eyebrow(s, '03 · Never invent a number')
title(s, [
  { text: 'One of our metrics\n', options: { color: NAVY } },
  { text: 'is deliberately blank.', options: { color: PURPLE } },
], 1.15, 6.9)
body(s, 'No Operator reports resolution timestamps, so MTTR would have to be inferred. The dashboard shows a dash and prints the reason underneath.', 3.25, { w: 6.5, h: 0.9 })
quote(s,
  'Ask it something outside what the agents actually observed and it says: I can’t answer that from agent data, so I won’t guess.',
  'The AI Manager holds no language model', 4.35)
body(s, 'A dash is honest. A zero is a claim.', 6.2, { w: 6.5, size: 17, bold: true, color: NAVY, h: 0.5 })

// Visual: the dashboard tile as it actually renders.
s.addShape(pres.ShapeType.roundRect, {
  x: 8.1, y: 1.55, w: 4.4, h: 2.3, rectRadius: 0.12,
  fill: { color: MUTED_BG }, line: { color: BORDER, width: 1 },
})
s.addText('MTTR', {
  x: 8.45, y: 1.85, w: 3.7, h: 0.3,
  fontFace: F, fontSize: 10.5, bold: true, charSpacing: 1.5, color: MUTED_FG, margin: 0,
})
s.addText('—', {
  x: 8.45, y: 2.15, w: 3.7, h: 0.9,
  fontFace: F, fontSize: 54, bold: true, color: 'B4B9CC', margin: 0,
})
s.addText('no Operator reports resolution timestamps', {
  x: 8.45, y: 3.1, w: 3.7, h: 0.5,
  fontFace: F, fontSize: 11, color: MUTED_FG, margin: 0,
})
s.addNotes('Type "tell me a joke" into the AI Manager live. The refusal is the proof.')
pageNum(s, 8)

/* ----------------------------------------------------- 9 architecture ---- */
s = slide(true)
eyebrow(s, 'How it runs', true)
s.addText('One Orchestrator. Seven Operators.', {
  x: M, y: 1.1, w: 11.4, h: 0.8,
  fontFace: F, fontSize: 34, bold: true, color: WHITE, margin: 0,
})

// Orchestrator
s.addShape(pres.ShapeType.roundRect, {
  x: 4.55, y: 2.15, w: 4.2, h: 0.85, rectRadius: 0.12,
  fill: { color: CORN }, line: { color: CORN, width: 0 },
})
s.addText('Service Desk Orchestrator', {
  x: 4.55, y: 2.15, w: 4.2, h: 0.85,
  fontFace: F, fontSize: 15, bold: true, color: NAVY,
  align: 'center', valign: 'middle', margin: 0,
})

// Seven Operators, two rows
const ops = [
  'Triage', 'Correlator', 'Evidence\n& Policy', 'Change\nApproval',
  'Safe\nResolution', 'Human\nEscalation', 'CSAT &\nKnowledge',
]
const ow = 1.62, og = 0.18
const row1 = ops.slice(0, 4), row2 = ops.slice(4)
function drawRow(list, y) {
  const total = list.length * ow + (list.length - 1) * og
  const x0 = (13.33 - total) / 2
  list.forEach((label, i) => {
    const x = x0 + i * (ow + og)
    s.addShape(pres.ShapeType.roundRect, {
      x, y, w: ow, h: 0.98, rectRadius: 0.1,
      fill: { color: DARK_CARD }, line: { color: DARK_LINE, width: 1 },
    })
    s.addText(label, {
      x, y, w: ow, h: 0.98,
      fontFace: F, fontSize: 11.5, color: WHITE,
      align: 'center', valign: 'middle', margin: 0, lineSpacing: 14,
    })
  })
  return { x0, total }
}
// Connector from the orchestrator down to the operator rows
s.addShape(pres.ShapeType.line, {
  x: 6.65, y: 3.0, w: 0, h: 0.42,
  line: { color: '3E4780', width: 1.5 },
})
const r1 = drawRow(row1, 3.42)
const r2 = drawRow(row2, 4.62)
s.addShape(pres.ShapeType.line, {
  x: r1.x0, y: 3.42 - 0.18, w: r1.total, h: 0,
  line: { color: '3E4780', width: 1.5 },
})

stats(s, [
  { n: '288', l: 'agent runs · 99.3% success' },
  { n: '8', l: 'live integrations' },
  { n: '0', l: 'agent logic in our codebase', accent: true },
], 5.85, true)
s.addNotes('The zero is the point: the hard rule is that Auto decides and this repo displays.')
pageNum(s, 9, true)

/* ------------------------------------------------------------ 10 demo ---- */
s = slide()
eyebrow(s, 'The demo')
title(s, [{ text: 'Let’s look at\nthe real thing.', options: { color: NAVY } }])
const items = [
  ['Elimination Backlog', 'the ranked classes and their proposed fixes'],
  ['Agent timeline', 'one full cycle, step by step, with the raw output'],
  ['Policies', 'change a threshold, watch it take effect'],
  ['Workbench', 'four different reasons the agent stopped'],
  ['Insights & Data Manager', 'what it noticed, and honest health'],
]
items.forEach(([h, d], i) => {
  const y = 3.25 + i * 0.72
  s.addShape(pres.ShapeType.ellipse, {
    x: M, y: y + 0.04, w: 0.34, h: 0.34,
    fill: { color: CORN }, line: { color: CORN, width: 0 },
  })
  s.addText(String(i + 1), {
    x: M, y: y + 0.04, w: 0.34, h: 0.34,
    fontFace: F, fontSize: 11, bold: true, color: NAVY,
    align: 'center', valign: 'middle', margin: 0,
  })
  s.addText([
    { text: h + '   ', options: { bold: true, color: NAVY } },
    { text: d, options: { color: MUTED_FG } },
  ], { x: M + 0.58, y: y + 0.02, w: 10.2, h: 0.4, fontFace: F, fontSize: 16, margin: 0 })
})
s.addNotes('Switch to the live app here. Localhost, not the hosted link.')
pageNum(s, 10)

/* ----------------------------------------------------------- 11 close ---- */
s = slide(true)
s.addImage({ data: LOGO_LIGHT, x: M, y: 0.55, w: 2.5, h: 0.66 })
s.addText('AN AGENT THAT ACTS FAST IS EASY TO BUILD', {
  x: M, y: 1.6, w: 11.4, h: 0.3,
  fontFace: F, fontSize: 12, bold: true, charSpacing: 2, color: CORN, margin: 0,
})
s.addText('One that stops is\nthe one you would\nactually deploy.', {
  x: M, y: 2.1, w: 8.6, h: 2.6,
  fontFace: F, fontSize: 44, bold: true, color: WHITE, lineSpacing: 52,
  margin: 0, valign: 'top',
})
stats(s, [{ n: '380', l: 'tickets that need never happen', accent: true }], 5.3, true)
s.addNotes('End on 380. Do not add anything after this.')
pageNum(s, 11, true)

pres.writeFile({ fileName: 'Service-Desk-Command-Center.pptx' })
  .then(f => console.log('written:', f))

/**
 * Demo deck for Autopilot Asia 2026 Round 2 finals.
 *
 * Palette is lifted from the app's own tokens so the slides and the live
 * product read as one thing when the presenter switches between them.
 *
 * Type is Calibri rather than the app's Funnel Display / Geologica. Those are
 * Google web fonts: they render in a browser but are not installed on a venue
 * laptop, so a deck using them would silently fall back to something arbitrary
 * on the machine that matters. Calibri ships with Office everywhere.
 */

const pptx = require('pptxgenjs')
const pres = new pptx()

// Must be set before any slide is added, or coordinates past 10" are written
// but land off-canvas.
pres.layout = 'LAYOUT_WIDE' // 13.3 x 7.5
pres.author = 'Service Desk Command Center'
pres.title = 'Service Desk Command Center — Autopilot Asia 2026'

const NAVY = '141A42'
const CORN = '8AA2DF'
const PURPLE = '5A64A3'
const MUTED_BG = 'F4F5F9'
const BORDER = 'E8EBF2'
const MUTED_FG = '6B7391'
const WHITE = 'FFFFFF'

const F = 'Calibri'
const M = 0.85 // left margin

/** Eyebrow label. Fresh object each call: pptxgenjs mutates options in place. */
function eyebrow(s, text, dark) {
  s.addText(text.toUpperCase(), {
    x: M, y: 0.62, w: 11.6, h: 0.32,
    fontFace: F, fontSize: 12, bold: true, charSpacing: 2,
    color: dark ? CORN : MUTED_FG, margin: 0,
  })
}

function title(s, runs, y = 1.15) {
  s.addText(runs, {
    x: M, y, w: 11.6, h: 1.9,
    fontFace: F, fontSize: 40, bold: true, lineSpacing: 46,
    color: NAVY, margin: 0, valign: 'top',
  })
}

function body(s, text, y, opts = {}) {
  s.addText(text, {
    x: M, y, w: opts.w || 8.6, h: opts.h || 0.9,
    fontFace: F, fontSize: opts.size || 17, color: opts.color || MUTED_FG,
    lineSpacing: opts.lineSpacing || 26, margin: 0, valign: 'top',
    ...(opts.bold ? { bold: true } : {}),
  })
}

/** Big number plus caption. The deck's main visual device. */
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

/** The repeated motif: a numbered cornflower disc beside a heading. */
function numberedCard(s, x, y, w, num, heading, text, dark) {
  s.addShape(pres.ShapeType.roundRect, {
    x, y, w, h: 2.5, rectRadius: 0.12,
    fill: { color: dark ? '1E2551' : MUTED_BG },
    line: { color: dark ? '2E3768' : BORDER, width: 1 },
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

/** Pull-quote for the Operator's own words. */
function quote(s, text, attr, y) {
  s.addShape(pres.ShapeType.roundRect, {
    x: M, y, w: 10.4, h: 1.55, rectRadius: 0.1,
    fill: { color: MUTED_BG }, line: { color: BORDER, width: 1 },
  })
  s.addText(text, {
    x: M + 0.4, y: y + 0.22, w: 9.6, h: 0.8,
    fontFace: F, fontSize: 15, italic: true, color: NAVY,
    lineSpacing: 21, margin: 0, valign: 'top',
  })
  s.addText(attr.toUpperCase(), {
    x: M + 0.4, y: y + 1.06, w: 9.6, h: 0.3,
    fontFace: F, fontSize: 9.5, bold: true, charSpacing: 1,
    color: MUTED_FG, margin: 0,
  })
}

function pageNum(s, n, dark) {
  s.addText(String(n), {
    x: 12.2, y: 6.75, w: 0.5, h: 0.3,
    fontFace: F, fontSize: 10, align: 'right', margin: 0,
    color: dark ? '5A6497' : 'B4B9CC',
  })
}

function slide(dark) {
  const s = pres.addSlide()
  s.background = { color: dark ? NAVY : WHITE }
  return s
}

// ---------------------------------------------------------------- 1 -------
let s = slide(true)
eyebrow(s, 'Autopilot Asia 2026 · Round 2 · Track 3', true)
s.addText('Service Desk\nCommand Center.', {
  x: M, y: 1.5, w: 11.6, h: 2.4,
  fontFace: F, fontSize: 54, bold: true, color: WHITE,
  lineSpacing: 62, margin: 0, valign: 'top',
})
s.addText('An AI Employee that eliminates problems instead of processing tickets.', {
  x: M, y: 4.05, w: 8.8, h: 0.5,
  fontFace: F, fontSize: 19, color: 'C9CFE6', margin: 0,
})
stats(s, [{ n: '380', l: 'tickets that need never happen', accent: true }], 4.9, true)
s.addNotes('Open on the Elimination page already loaded. Lead with the idea, not the architecture.')
pageNum(s, 1, true)

// ---------------------------------------------------------------- 2 -------
s = slide()
eyebrow(s, 'The premise')
title(s, [
  { text: 'Closing tickets faster is\n', options: { color: NAVY } },
  { text: 'the wrong goal.', options: { color: PURPLE } },
])
body(s, 'If 44 people request shared drive access every month, resolving those tickets quickly is being efficient at something that should not be happening.', 3.35, { w: 9.4 })
body(s, 'Everyone else optimises the queue. We went after what keeps filling it.', 4.55, { color: NAVY, bold: true, size: 19, w: 9.4 })
s.addNotes('Everyone else closes tickets faster. We think that is the wrong goal.')
pageNum(s, 2)

// ---------------------------------------------------------------- 3 -------
s = slide(true)
eyebrow(s, 'What makes this different', true)
s.addText('Three choices. One idea.', {
  x: M, y: 1.15, w: 11.6, h: 0.9,
  fontFace: F, fontSize: 40, bold: true, color: WHITE, margin: 0,
})
const cw = 3.63
numberedCard(s, M, 2.5, cw, '1', 'Stop the tickets\nhappening', 'Find the root cause, propose the permanent fix, name the owner.', true)
numberedCard(s, M + cw + 0.35, 2.5, cw, '2', 'Know when\nto stop', 'Four refusal reasons, none overridable by urgency.', true)
numberedCard(s, M + (cw + 0.35) * 2, 2.5, cw, '3', 'Never invent\na number', 'A dash is honest. A zero is a claim.', true)
s.addNotes('These three are really one idea: knowing where its own judgement runs out.')
pageNum(s, 3, true)

// ---------------------------------------------------------------- 4 -------
s = slide()
eyebrow(s, '01 · Stop the tickets happening')
title(s, [
  { text: '37 password resets\n', options: { color: NAVY } },
  { text: 'are one problem.', options: { color: PURPLE } },
])
body(s, 'A normal service desk resolves 37 tickets. Our agent noticed they were the same problem, checked the knowledge base, found no self-service route, and proposed building one.', 3.3, { w: 10.4 })
quote(s,
  '"Implement a Self-Service Password Reset portal integrated with MFA, so users verify their own identity and reset credentials without help desk intervention."',
  'Proposed by the Correlator · owner: IAM Team', 4.35)
s.addText([
  { text: 'Those 37 tickets stop arriving. ', options: { color: NAVY } },
  { text: 'Not resolved faster. Gone.', options: { color: CORN } },
], { x: M, y: 6.15, w: 10.4, h: 0.5, fontFace: F, fontSize: 21, bold: true, margin: 0 })
s.addNotes('This is the whole differentiator in one example. Say "gone", not "prevented".')
pageNum(s, 4)

// ---------------------------------------------------------------- 5 -------
s = slide()
eyebrow(s, '01 · At scale')
title(s, [{ text: '460 tickets.\n15 actual problems.', options: { color: NAVY } }])
stats(s, [
  { n: '15', l: 'root causes found' },
  { n: '75', l: 'collapsed today · work avoided' },
  { n: '380', l: 'preventable · a forecast', accent: true },
], 3.5)
body(s, 'Two numbers, never blended. One is work already avoided. The other is conditional on a human approving each fix. Adding them together would make a better headline and a worse answer.', 5.35, { w: 10.6 })
s.addNotes('The "never blended" line is the one that shows you expected to be challenged.')
pageNum(s, 5)

// ---------------------------------------------------------------- 6 -------
s = slide()
eyebrow(s, '02 · Know when to stop')
title(s, [{ text: 'It refused the most\nurgent ticket in the queue.', options: { color: NAVY } }])
// The first line is a single sentence and needs less room than the default
// block height, which was letting the paragraph below it overlap by 0.2in.
body(s, 'Highest priority. Already past SLA. A known fix available. Every incentive said act.', 3.35, { w: 10.4, h: 0.5 })
body(s, 'It stopped because two employees share a display name and it could not tell which of them had raised it. Applying a fix to the wrong person’s account to hit a deadline is not a win.', 4.05, { w: 10.4, h: 1.0, color: NAVY })
stats(s, [
  { n: '32', l: 'tickets held back for that reason', accent: true },
  { n: '4', l: 'refusal reasons, none overridable' },
], 5.35)
s.addNotes('Slow down here. This is the moment that lands.')
pageNum(s, 6)

// ---------------------------------------------------------------- 7 -------
s = slide()
eyebrow(s, '02 · And it is auditable')
title(s, [
  { text: 'Every refusal has\n', options: { color: NAVY } },
  { text: 'a reason on the record.', options: { color: PURPLE } },
])
body(s, 'ITSM-2212 had a fix ready and an open change request awaiting board approval. Change control outranks confidence, so the agent opened the approval in GitHub rather than shipping. A human reviewed it and upheld the block.', 3.3, { w: 10.6 })
stats(s, [
  { n: '9,752', l: 'policy evaluations logged' },
  { n: '4', l: 'policies, editable without code' },
  { n: '176', l: 'waiting on a human', accent: true },
], 4.6)
body(s, 'Each evaluation names the rule, the threshold in force at that moment, and what it was compared against. A later edit never rewrites history.', 6.25, { w: 10.6, size: 14 })
s.addNotes('Offer to change a threshold live if they want to see it take effect.')
pageNum(s, 7)

// ---------------------------------------------------------------- 8 -------
s = slide()
eyebrow(s, '03 · Never invent a number')
title(s, [
  { text: 'One of our metrics\n', options: { color: NAVY } },
  { text: 'is deliberately blank.', options: { color: PURPLE } },
])
body(s, 'No Operator reports resolution timestamps, so MTTR would have to be inferred. The dashboard shows a dash and prints the reason underneath.', 3.3, { w: 10.4 })
quote(s,
  '"Ask it something outside what the agents actually observed and it says: I can’t answer that from agent data, so I won’t guess."',
  'The AI Manager holds no language model', 4.3)
body(s, 'A dash is honest. A zero is a claim. Round 1 caught the platform’s own chat summaries inventing ticket numbers while its audit log said otherwise. That is the failure this design is built against.', 6.1, { w: 10.6, size: 14 })
s.addNotes('Type "tell me a joke" into the AI Manager live. The refusal is the proof.')
pageNum(s, 8)

// ---------------------------------------------------------------- 9 -------
s = slide(true)
eyebrow(s, 'How it runs', true)
s.addText('One Orchestrator.\nSeven Operators.', {
  x: M, y: 1.15, w: 11.6, h: 1.7,
  fontFace: F, fontSize: 40, bold: true, color: WHITE, lineSpacing: 46, margin: 0,
})
s.addText('Triage and correlation start in parallel, reconcile, then branch three ways on the decision. All of it on Supervity Auto. The Command Center never decides anything: it reads what the agents did, ranks it, and shows which run produced it.', {
  x: M, y: 3.15, w: 10.6, h: 1.1,
  fontFace: F, fontSize: 17, color: 'A8AECB', lineSpacing: 26, margin: 0,
})
stats(s, [
  { n: '96', l: 'agent runs · 97.8% success' },
  { n: '8', l: 'live integrations' },
  { n: '0', l: 'agent logic in our codebase', accent: true },
], 4.55, true)
s.addNotes('The zero is the point: the hard rule is that Auto decides and this repo displays.')
pageNum(s, 9, true)

// ---------------------------------------------------------------- 10 ------
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
  const y = 3.3 + i * 0.66
  s.addShape(pres.ShapeType.ellipse, {
    x: M, y: y + 0.09, w: 0.2, h: 0.2,
    fill: { color: CORN }, line: { color: CORN, width: 0 },
  })
  s.addText([
    { text: h + '  ', options: { bold: true, color: NAVY } },
    { text: d, options: { color: MUTED_FG } },
  ], { x: M + 0.42, y, w: 10.4, h: 0.4, fontFace: F, fontSize: 16, margin: 0 })
})
s.addNotes('Switch to the live app here. Localhost, not the hosted link.')
pageNum(s, 10)

// ---------------------------------------------------------------- 11 ------
s = slide(true)
eyebrow(s, 'In closing', true)
s.addText('An agent that acts fast\nis easy to build.', {
  x: M, y: 1.35, w: 11.6, h: 1.8,
  fontFace: F, fontSize: 42, bold: true, color: WHITE, lineSpacing: 50, margin: 0,
})
s.addText('One that stops is the one you would actually let near your company.', {
  x: M, y: 3.35, w: 9.6, h: 0.6,
  fontFace: F, fontSize: 21, color: 'C9CFE6', margin: 0,
})
stats(s, [{ n: '380', l: 'tickets that need never happen', accent: true }], 4.6, true)
s.addNotes('End on 380. Do not add anything after this.')
pageNum(s, 11, true)

pres.writeFile({ fileName: 'Service-Desk-Command-Center.pptx' })
  .then(f => console.log('written:', f))

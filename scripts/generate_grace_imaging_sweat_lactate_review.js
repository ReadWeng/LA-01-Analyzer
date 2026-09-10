// Generate the Traditional Chinese Grace Imaging / Daisuke Nakashima evidence deck.
// Dependency: npm install pptxgenjs@3.12.0
// Run from repository root:
//   NODE_PATH=/path/to/node_modules node scripts/generate_grace_imaging_sweat_lactate_review.js

const pptxgen = require('pptxgenjs');
const fs = require('fs');
const path = require('path');

const pptx = new pptxgen();
pptx.layout = 'LAYOUT_WIDE';
pptx.author = 'Arena.ai Agent Mode';
pptx.company = 'LA-01 Analyzer';
pptx.subject = 'Focused evidence tracking of Daisuke Nakashima and Grace Imaging sweat-lactate studies';
pptx.title = 'Grace Imaging 總裁中島大輔：汗液乳酸研究追蹤與 LA-01 產品判讀';
pptx.lang = 'zh-TW';
pptx.theme = {
  headFontFace: 'Microsoft JhengHei',
  bodyFontFace: 'Microsoft JhengHei',
  lang: 'zh-TW'
};
pptx.defineSlideMaster({ title: 'MASTER', background: { color: '07111F' }, objects: [] });
pptx.margin = 0;
pptx.layout = 'LAYOUT_WIDE';

const W = 13.333;
const H = 7.5;
const C = {
  bg: '07111F', panel: '0E1D2E', panel2: '12263A', panel3: '173149',
  border: '1E3A52', grid: '27435A', white: 'F5F7FA', text: 'D8E2EC',
  muted: '93A4B6', cyan: '20D4C7', cyan2: '78EAE0', blue: '6BB7FF',
  blue2: '9DD0FF', orange: 'FF9B5E', orange2: 'FFC09B', lime: 'B7F06A',
  red: 'FF6577', yellow: 'FFD166', purple: 'B59CFF', dark: '07111F', ink: '102235'
};
const FONT = 'Microsoft JhengHei';
const ENFONT = 'Aptos';
let slideNo = 0;

function text(slide, str, x, y, w, h, opt = {}) {
  slide.addText(str, {
    x, y, w, h,
    fontFace: opt.fontFace || FONT,
    fontSize: opt.fontSize || 14,
    color: opt.color || C.text,
    bold: !!opt.bold,
    italic: !!opt.italic,
    align: opt.align || 'left',
    valign: opt.valign || 'top',
    margin: opt.margin !== undefined ? opt.margin : 0,
    fit: opt.fit || 'shrink',
    breakLine: false,
    charSpacing: opt.charSpacing,
    paraSpaceAfterPt: opt.paraSpaceAfterPt || 0,
    hyperlink: opt.hyperlink,
    isTextBox: true
  });
}

function rich(slide, runs, x, y, w, h, opt = {}) {
  slide.addText(runs, {
    x, y, w, h,
    fontFace: opt.fontFace || FONT,
    fontSize: opt.fontSize || 14,
    color: opt.color || C.text,
    align: opt.align || 'left',
    valign: opt.valign || 'top',
    margin: opt.margin !== undefined ? opt.margin : 0,
    fit: opt.fit || 'shrink',
    breakLine: false
  });
}

function card(slide, x, y, w, h, opt = {}) {
  slide.addShape(pptx.ShapeType.roundRect, {
    x, y, w, h,
    rectRadius: 0.06,
    fill: { color: opt.fill || C.panel, transparency: opt.transparency || 0 },
    line: { color: opt.line || C.border, width: opt.lineWidth || 1, transparency: opt.lineTransparency || 0 }
  });
}

function pill(slide, label, x, y, w, color = C.cyan, opt = {}) {
  const hh = opt.h || 0.34;
  slide.addShape(pptx.ShapeType.roundRect, {
    x, y, w, h: hh,
    fill: { color, transparency: opt.transparency || 0 },
    line: { color, transparency: 100 }
  });
  text(slide, label, x + 0.06, y + 0.075, w - 0.12, hh - 0.11, {
    fontFace: opt.fontFace || FONT,
    fontSize: opt.fontSize || 9.1,
    bold: true,
    color: opt.textColor || C.dark,
    align: 'center',
    valign: 'mid'
  });
}

function segment(slide, x1, y1, x2, y2, line = {}) {
  const x = Math.min(x1, x2);
  const y = Math.min(y1, y2);
  slide.addShape(pptx.ShapeType.line, {
    x, y, w: Math.abs(x2 - x1), h: Math.abs(y2 - y1),
    flipH: x2 < x1, flipV: y2 < y1, line
  });
}

function note(slide, str) { slide.addNotes(str); }

function addSlide(title, kicker = '', source = '') {
  const slide = pptx.addSlide('MASTER');
  slideNo += 1;
  slide.background = { color: C.bg };
  slide.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: 0.11, h: H, fill: { color: C.cyan }, line: { color: C.cyan, transparency: 100 } });
  slide.addShape(pptx.ShapeType.ellipse, { x: 11.45, y: 0.05, w: 1.65, h: 1.65, fill: { color: C.cyan, transparency: 94 }, line: { color: C.cyan, transparency: 100 } });
  segment(slide, 0.55, 0.93, 12.75, 0.93, { color: C.border, width: 1 });
  if (kicker) text(slide, kicker.toUpperCase(), 0.62, 0.24, 3.7, 0.22, { fontFace: ENFONT, fontSize: 8.3, bold: true, color: C.cyan, charSpacing: 1.2 });
  text(slide, title, 0.62, 0.48, 11.8, 0.36, { fontSize: 22, bold: true, color: C.white });
  if (source) text(slide, source, 0.62, 7.11, 10.85, 0.18, { fontSize: 7.1, color: C.muted });
  text(slide, String(slideNo).padStart(2, '0'), 12.10, 7.10, 0.62, 0.18, { fontFace: ENFONT, fontSize: 8.4, bold: true, color: C.cyan, align: 'right' });
  return slide;
}

function metric(slide, x, y, w, value, label, color = C.cyan, sub = '') {
  card(slide, x, y, w, 1.12, { fill: C.panel2, line: color, lineWidth: 1.1 });
  text(slide, value, x + 0.15, y + 0.14, w - 0.30, 0.39, { fontFace: ENFONT, fontSize: 23, bold: true, color });
  text(slide, label, x + 0.15, y + 0.60, w - 0.30, 0.20, { fontSize: 9.6, bold: true, color: C.white });
  if (sub) text(slide, sub, x + 0.15, y + 0.83, w - 0.30, 0.16, { fontSize: 7.7, color: C.muted });
}

function bullet(slide, title, body, x, y, w, opt = {}) {
  const color = opt.color || C.cyan;
  slide.addShape(pptx.ShapeType.ellipse, { x, y: y + 0.05, w: 0.13, h: 0.13, fill: { color }, line: { color, transparency: 100 } });
  text(slide, title, x + 0.22, y, w - 0.22, 0.24, { fontSize: opt.titleSize || 12.2, bold: true, color: opt.titleColor || C.white });
  text(slide, body, x + 0.22, y + 0.27, w - 0.22, opt.bodyH || 0.45, { fontSize: opt.bodySize || 10.1, color: opt.bodyColor || C.muted });
}

function link(slide, label, url, x, y, w) {
  slide.addText([{ text: label, options: { hyperlink: { url }, color: C.cyan2, bold: true, underline: { color: C.cyan2 } } }], {
    x, y, w, h: 0.20, fontFace: ENFONT, fontSize: 8.4, color: C.cyan2, margin: 0, fit: 'shrink', breakLine: false
  });
}

function sectionLabel(slide, label, x, y, w, color = C.cyan) {
  text(slide, label, x, y, w, 0.20, { fontSize: 9.2, bold: true, color, charSpacing: 0.4 });
}

function bar(slide, x, y, w, value, max, label, valueLabel, color = C.cyan) {
  text(slide, label, x, y, 2.35, 0.20, { fontSize: 9.4, color: C.text, bold: true });
  card(slide, x + 2.40, y + 0.02, w - 3.05, 0.18, { fill: C.grid, line: C.grid, lineTransparency: 100 });
  const bw = Math.max(0.04, (w - 3.05) * value / max);
  slide.addShape(pptx.ShapeType.roundRect, { x: x + 2.40, y: y + 0.02, w: bw, h: 0.18, fill: { color }, line: { color, transparency: 100 } });
  text(slide, valueLabel, x + w - 0.58, y - 0.01, 0.58, 0.22, { fontFace: ENFONT, fontSize: 9.2, bold: true, color, align: 'right' });
}

function checkRow(slide, ok, title, body, x, y, w) {
  const color = ok ? C.lime : C.red;
  slide.addShape(ok ? pptx.ShapeType.ellipse : pptx.ShapeType.hexagon, { x, y, w: 0.28, h: 0.28, fill: { color }, line: { color, transparency: 100 } });
  text(slide, ok ? '✓' : '×', x, y + 0.047, 0.28, 0.16, { fontFace: ENFONT, fontSize: 11, bold: true, color: C.dark, align: 'center' });
  text(slide, title, x + 0.40, y - 0.01, w - 0.40, 0.23, { fontSize: 11.8, bold: true, color: C.white });
  text(slide, body, x + 0.40, y + 0.26, w - 0.40, 0.36, { fontSize: 9.5, color: C.muted });
}

function studySlide(d) {
  const slide = addSlide(`${d.id}｜${d.title}`, `${d.year} · ${d.domain}`, d.source);
  pill(slide, d.year, 0.62, 1.12, 0.74, d.color || C.cyan, { fontFace: ENFONT });
  pill(slide, d.badge, 1.49, 1.12, d.badgeW || 1.55, C.panel3, { textColor: d.color || C.cyan2, fontSize: 8.8 });
  text(slide, d.journal, 3.23, 1.18, 5.0, 0.18, { fontFace: ENFONT, fontSize: 9.4, color: C.muted, italic: true });
  link(slide, `DOI ${d.doi}`, `https://doi.org/${d.doi}`, 8.45, 1.18, 4.10);

  const mx = [0.62, 2.64, 4.66];
  d.metrics.forEach((m, i) => metric(slide, mx[i], 1.68, 1.78, m.value, m.label, m.color || d.color || C.cyan, m.sub || ''));

  card(slide, 6.68, 1.68, 6.03, 2.03, { fill: C.panel, line: d.color || C.cyan, lineWidth: 1.2 });
  sectionLabel(slide, '研究設計', 6.94, 1.93, 1.20, d.color || C.cyan);
  text(slide, d.method, 6.94, 2.25, 5.50, 1.14, { fontSize: 11.0, color: C.text });

  card(slide, 0.62, 3.98, 5.78, 2.37, { fill: C.panel2, line: C.border });
  sectionLabel(slide, '關鍵結果', 0.89, 4.25, 1.25, C.lime);
  text(slide, d.findings, 0.89, 4.59, 5.25, 1.46, { fontSize: 11.1, color: C.text });

  card(slide, 6.68, 3.98, 6.03, 2.37, { fill: C.panel2, line: C.border });
  sectionLabel(slide, '限制與風險', 6.94, 4.25, 1.55, C.orange);
  text(slide, d.limitations, 6.94, 4.59, 5.50, 1.46, { fontSize: 10.8, color: C.text });

  card(slide, 0.92, 6.60, 11.48, 0.39, { fill: d.color || C.cyan, transparency: 86, line: d.color || C.cyan, lineWidth: 1 });
  rich(slide, [
    { text: 'LA-01 判讀｜', options: { bold: true, color: d.color || C.cyan2 } },
    { text: d.implication, options: { bold: true, color: C.white } }
  ], 1.12, 6.71, 11.08, 0.17, { fontSize: 9.8, align: 'center' });
  note(slide, d.notes);
  return slide;
}

// 01 COVER
{
  const slide = pptx.addSlide('MASTER');
  slideNo += 1;
  slide.background = { color: C.bg };
  slide.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: W, h: H, fill: { color: C.bg }, line: { color: C.bg, transparency: 100 } });
  slide.addShape(pptx.ShapeType.ellipse, { x: 8.55, y: 0.35, w: 4.3, h: 4.3, fill: { color: C.cyan, transparency: 93 }, line: { color: C.cyan, transparency: 100 } });
  slide.addShape(pptx.ShapeType.ellipse, { x: 9.45, y: 2.80, w: 3.1, h: 3.1, fill: { color: C.orange, transparency: 95 }, line: { color: C.orange, transparency: 100 } });
  slide.addShape(pptx.ShapeType.teardrop, { x: 9.63, y: 1.25, w: 1.68, h: 2.15, rotate: 45, fill: { color: C.cyan, transparency: 6 }, line: { color: C.cyan2, width: 1.4 } });
  // Conceptual sLT trace.
  const pts = [];
  for (let i = 0; i <= 30; i++) {
    const t = i / 30;
    pts.push([8.25 + t * 4.15, 5.30 - 0.08 * t - 1.18 / (1 + Math.exp(-(t - 0.52) * 15))]);
  }
  for (let i = 1; i < pts.length; i++) segment(slide, pts[i-1][0], pts[i-1][1], pts[i][0], pts[i][1], { color: C.cyan2, width: 2.4 });
  segment(slide, 8.25, 5.35, 12.42, 5.35, { color: C.grid, width: 1 });
  segment(slide, 10.41, 4.12, 10.41, 5.58, { color: C.orange, width: 1.3, dash: 'dash' });
  pill(slide, 'FOCUSED EVIDENCE TRACKER', 0.72, 0.68, 2.72, C.cyan, { fontFace: ENFONT, fontSize: 8.8 });
  text(slide, 'Grace Imaging 總裁中島大輔', 0.72, 1.38, 7.25, 0.60, { fontSize: 30, bold: true, color: C.white });
  text(slide, '汗液乳酸研究追蹤', 0.72, 2.15, 7.25, 0.69, { fontSize: 35, bold: true, color: C.cyan2 });
  text(slide, '11 篇核心研究 × 2 篇支援文章\n證據版圖、疲勞判讀與 LA-01 呈現建議', 0.75, 3.22, 6.65, 0.93, { fontSize: 17.5, color: C.text });
  card(slide, 0.72, 4.66, 6.30, 1.08, { fill: C.panel2, line: C.border });
  text(slide, '2021–2026  |  查核截止 2026-09-10', 1.02, 4.94, 5.70, 0.24, { fontFace: ENFONT, fontSize: 13, bold: true, color: C.white, align: 'center' });
  text(slide, '汗乳酸 only；血乳酸僅為論文比較基準', 1.02, 5.30, 5.70, 0.19, { fontSize: 9.5, color: C.muted, align: 'center' });
  text(slide, '研究追蹤與產品規劃，不是醫療診斷', 0.75, 6.55, 4.7, 0.22, { fontSize: 9.5, color: C.muted });
  text(slide, '01', 12.10, 7.10, 0.62, 0.18, { fontFace: ENFONT, fontSize: 8.4, bold: true, color: C.cyan, align: 'right' });
  note(slide, '本簡報根據 Grace Imaging 官方論文頁、Daisuke Nakashima ORCID、PubMed/PMC 與出版社頁交叉核對。截止日 2026-09-10。');
}

// 02 EXECUTIVE SUMMARY
{
  const slide = addSlide('執行摘要：最強的是「第一轉折」，疲勞仍屬初步', 'EXECUTIVE READOUT');
  metric(slide, 0.62, 1.30, 2.15, '11', '核心汗乳酸研究', C.cyan, '2021–2026');
  metric(slide, 2.98, 1.30, 2.15, '2', '直接疲勞研究', C.orange, 'n=17 與 n=18');
  metric(slide, 5.34, 1.30, 2.15, '11/11', '揭露公司／股權關係', C.yellow, '需獨立重現');
  card(slide, 7.80, 1.30, 4.91, 1.12, { fill: C.panel2, line: C.lime });
  text(slide, '產品核心訊號', 8.05, 1.51, 1.45, 0.19, { fontSize: 9.5, color: C.lime, bold: true });
  text(slide, 'sLT 時間／功率／速度的個人內變化', 8.05, 1.84, 4.35, 0.26, { fontSize: 15.4, color: C.white, bold: true });

  const items = [
    ['可支持', '有足夠出汗時，sLT 可近似 LT1／VT1；不同場景方向一致。', C.lime],
    ['疲勞訊號', '力竭後與足球賽後，曲線／sLT 較早或在較低強度出現。', C.orange],
    ['必要條件', '先判定出汗、基線、接觸與流程一致性，再產生結果。', C.cyan],
    ['不可外推', '不能把單次 μA／mmol/L 直接換成血乳酸或全身疲勞百分比。', C.red],
    ['部署原則', '同一人、同流程、超過個人 MDC，並以第二指標複核。', C.blue]
  ];
  items.forEach((it, i) => {
    const y = 2.92 + i * 0.72;
    slide.addShape(pptx.ShapeType.ellipse, { x: 0.74, y: y + 0.02, w: 0.34, h: 0.34, fill: { color: it[2] }, line: { color: it[2], transparency: 100 } });
    text(slide, String(i + 1), 0.74, y + 0.105, 0.34, 0.14, { fontFace: ENFONT, fontSize: 8.5, bold: true, color: C.dark, align: 'center' });
    text(slide, it[0], 1.28, y, 1.25, 0.22, { fontSize: 11.5, bold: true, color: it[2] });
    text(slide, it[1], 2.55, y, 9.75, 0.39, { fontSize: 11.3, color: C.text });
  });
  note(slide, '信心總結：sLT 作為第一生理轉折的證據為中等；疲勞／恢復判讀僅初步；絕對濃度疲勞分數目前不支持。');
}

// 03 SCOPE
{
  const slide = addSlide('範圍與方法：聚焦指定作者，不冒充系統性回顧', 'METHOD', '來源：Grace Imaging、ORCID 0000-0003-1105-2669、PubMed/PMC、出版社與 J-GLOBAL；查核 2026-09-10');
  const cols = [0.62, 4.66, 8.70];
  const titles = ['納入', '分層', '排除／保留紀錄'];
  const colors = [C.cyan, C.blue, C.orange];
  const bodies = [
    '• 正式同儕審查期刊\n• Daisuke Nakashima 列名作者\n• 人體汗乳酸、sLT 或直接影響判讀的汗率\n• 截止 2026-09-10',
    '核心：汗乳酸為主要指標\n\n支援：汗乳酸應用或汗率方法\n\n相鄰：公司相關但無汗乳酸終點',
    '• 重複預印本／會議摘要不重複計數\n• EXERCISE-HF 無汗乳酸終點，列 X01\n• 血乳酸只作論文 comparator，不是 LA-01 輸入'
  ];
  cols.forEach((x, i) => {
    card(slide, x, 1.40, 3.61, 3.78, { fill: C.panel, line: colors[i], lineWidth: 1.2 });
    slide.addShape(pptx.ShapeType.rect, { x, y: 1.40, w: 3.61, h: 0.09, fill: { color: colors[i] }, line: { color: colors[i], transparency: 100 } });
    text(slide, titles[i], x + 0.25, 1.78, 3.10, 0.30, { fontSize: 16, bold: true, color: colors[i] });
    text(slide, bodies[i], x + 0.25, 2.30, 3.10, 2.35, { fontSize: 11.4, color: C.text });
  });
  card(slide, 1.38, 5.55, 10.58, 0.98, { fill: C.panel2, line: C.yellow });
  rich(slide, [
    { text: '名詞規則｜', options: { bold: true, color: C.yellow } },
    { text: '文獻雖常寫 “anaerobic threshold”，實際多比較第一上升點 LT1／VT1；本報告優先稱 sLT／第一轉折，避免和 LT2／VT2 混淆。', options: { color: C.white } }
  ], 1.70, 5.86, 9.94, 0.40, { fontSize: 11.1, align: 'center' });
  note(slide, '這是聚焦式作者/公司技術線追蹤。未做 PROSPERO 註冊、雙人獨立篩選或完整外部競品文獻系統回顧。');
}

// 04 INVENTORY
{
  const slide = addSlide('追蹤清單：11 核心＋2 支援＋1 相鄰排除', 'SCREENING RESULT');
  const rows = [
    ['核心', '11', 'sLT 效度、疲勞、EMS、MLSS、低氧、游泳、HF、女性、手搖車', C.cyan],
    ['支援', '2', '汗乳酸作分層點；局部汗率方法學', C.blue],
    ['相鄰／排除', '1', 'EXERCISE-HF：Fitbit／心率＋App，沒有汗乳酸終點', C.orange]
  ];
  rows.forEach((r, i) => {
    const y = 1.32 + i * 1.08;
    card(slide, 0.62, y, 7.36, 0.86, { fill: C.panel2, line: r[3] });
    pill(slide, r[0], 0.84, y + 0.25, 1.25, r[3], { fontSize: 9 });
    text(slide, r[1], 2.38, y + 0.18, 0.64, 0.38, { fontFace: ENFONT, fontSize: 23, bold: true, color: r[3], align: 'center' });
    text(slide, r[2], 3.30, y + 0.20, 4.35, 0.37, { fontSize: 10.4, color: C.text });
  });
  card(slide, 8.30, 1.32, 4.41, 3.02, { fill: C.panel, line: C.yellow, lineWidth: 1.2 });
  text(slide, '本次新增／修正', 8.58, 1.64, 3.85, 0.30, { fontSize: 15.5, bold: true, color: C.yellow });
  bullet(slide, '漏文補抓', '2026 健康女性論文未列於本次抓取的 Grace Paper 清單。', 8.58, 2.20, 3.55, { color: C.lime, bodyH: 0.42 });
  bullet(slide, 'DOI 校正 ×2', '手搖車應為 phy2.71002；游泳應為 10.1002。', 8.58, 3.03, 3.55, { color: C.orange, bodyH: 0.38 });

  card(slide, 0.62, 4.76, 12.09, 1.58, { fill: C.panel2, line: C.border });
  text(slide, '年份歸檔陷阱', 0.90, 5.03, 1.65, 0.26, { fontSize: 13.4, bold: true, color: C.cyan2 });
  text(slide, '足球疲勞研究', 2.76, 5.02, 1.65, 0.22, { fontSize: 11, bold: true, color: C.white });
  pill(slide, 'Online 2025-09-07', 4.30, 4.96, 2.05, C.orange, { fontFace: ENFONT, fontSize: 8.6 });
  text(slide, '≠', 6.55, 5.02, 0.40, 0.24, { fontSize: 15, bold: true, color: C.muted, align: 'center' });
  pill(slide, 'Issue 2026 · 14(1)', 7.18, 4.96, 1.95, C.blue, { fontFace: ENFONT, fontSize: 8.6 });
  text(slide, '同一篇，不重複計數；追蹤表保留兩種日期。', 9.40, 5.02, 2.85, 0.38, { fontSize: 10.2, color: C.text });
  note(slide, '核心 C01-C11；支援 S01-S02；相鄰排除 X01。詳細欄位與篩選理由見 CSV/Markdown。');
}

// 05 TIMELINE
{
  const slide = addSlide('技術路線：從閾值原型，走向情境與族群擴展', '2021 → 2026');
  const years = ['2021','2022','2023','2024','2025','2026'];
  const xs = [1.00, 3.05, 5.10, 7.15, 9.20, 11.25];
  segment(slide, 1.00, 3.47, 11.70, 3.47, { color: C.grid, width: 2.2 });
  years.forEach((yr, i) => {
    slide.addShape(pptx.ShapeType.ellipse, { x: xs[i], y: 3.27, w: 0.40, h: 0.40, fill: { color: i === 5 ? C.cyan : C.panel3 }, line: { color: C.cyan, width: 1.2 } });
    text(slide, yr, xs[i] - 0.18, 3.86, 0.76, 0.22, { fontFace: ENFONT, fontSize: 10.5, bold: true, color: C.white, align: 'center' });
  });
  const nodes = [
    [0.62,1.30,1.72,'C01','原型＋LT1/VT1','上'],
    [2.38,4.42,1.55,'C02','疲勞曲線左移','下'],
    [3.16,1.30,1.55,'C03','EMS 提前','上'],
    [4.40,4.42,1.55,'C04','出汗起始','下'],
    [5.23,1.30,1.55,'C05','MLSS','上'],
    [5.98,4.42,1.55,'C06','低氧','下'],
    [7.08,1.30,1.55,'C07','游泳','上'],
    [7.85,4.42,1.55,'C08','心衰竭試驗','下'],
    [9.10,1.30,1.63,'C09','足球疲勞 online','上'],
    [10.45,4.42,1.22,'C10','女性','下'],
    [11.48,1.30,1.22,'C11','手搖車','上']
  ];
  nodes.forEach((n, idx) => {
    const color = idx === 1 || idx === 8 ? C.orange : (idx >= 9 ? C.lime : C.cyan);
    card(slide, n[0], n[1], n[2], 0.96, { fill: C.panel2, line: color, lineWidth: 1 });
    text(slide, n[3], n[0] + 0.10, n[1] + 0.13, 0.52, 0.18, { fontFace: ENFONT, fontSize: 9.2, bold: true, color });
    text(slide, n[4], n[0] + 0.10, n[1] + 0.43, n[2] - 0.20, 0.32, { fontSize: 9.0, bold: true, color: C.white, align: 'center' });
    const center = n[0] + n[2]/2;
    if (n[5] === '上') segment(slide, center, n[1] + 0.96, center, 3.27, { color, width: 1, dash: 'dash' });
    else segment(slide, center, 3.67, center, n[1], { color, width: 1, dash: 'dash' });
  });
  text(slide, '閾值效度', 0.86, 6.18, 1.05, 0.20, { fontSize: 9.4, bold: true, color: C.cyan });
  text(slide, '→ 情境擴展', 2.05, 6.18, 1.15, 0.20, { fontSize: 9.4, bold: true, color: C.blue });
  text(slide, '→ 臨床與疲勞', 3.35, 6.18, 1.35, 0.20, { fontSize: 9.4, bold: true, color: C.orange });
  text(slide, '→ 性別／運動型態', 4.85, 6.18, 1.65, 0.20, { fontSize: 9.4, bold: true, color: C.lime });
  note(slide, 'C09 以線上日期放在 2025，但正式卷期是 2026。時間軸只顯示核心研究。');
}

// 06 MEASUREMENT MODEL
{
  const slide = addSlide('測量語意：研究成功路徑不是「濃度直譯疲勞」', 'SIGNAL → DECISION');
  const xs = [0.62, 3.02, 5.42, 7.82, 10.22];
  const labels = [
    ['1 Hz 原始電流','μA／曲線'],
    ['品質閘門','出汗・基線・接觸'],
    ['偵測 sLT','第一個持續上升點'],
    ['映射外部負荷','時間・W・速度・HR'],
    ['個人內變化','ΔsLT vs baseline']
  ];
  labels.forEach((l,i) => {
    card(slide, xs[i], 1.58, 1.96, 1.30, { fill: C.panel2, line: i===1 ? C.yellow : C.cyan, lineWidth: 1.2 });
    text(slide, l[0], xs[i]+0.15, 1.88, 1.66, 0.26, { fontSize: 12.1, bold: true, color: i===1 ? C.yellow : C.cyan2, align: 'center' });
    text(slide, l[1], xs[i]+0.15, 2.34, 1.66, 0.22, { fontSize: 8.8, color: C.muted, align: 'center' });
    if (i<4) {
      slide.addShape(pptx.ShapeType.chevron, { x: xs[i]+2.03, y: 1.99, w: 0.28, h: 0.44, fill: { color: C.grid }, line: { color: C.grid, transparency: 100 } });
    }
  });
  card(slide, 0.62, 3.38, 12.09, 2.34, { fill: C.panel, line: C.border });
  text(slide, '不建議的捷徑', 0.92, 3.72, 1.55, 0.28, { fontSize: 14.5, bold: true, color: C.red });
  card(slide, 2.70, 3.58, 2.35, 0.88, { fill: C.panel2, line: C.red });
  text(slide, '單次汗乳酸濃度', 2.88, 3.86, 1.99, 0.22, { fontSize: 12.0, bold: true, color: C.white, align: 'center' });
  text(slide, '=', 5.28, 3.83, 0.40, 0.25, { fontSize: 20, bold: true, color: C.red, align: 'center' });
  card(slide, 5.86, 3.58, 2.35, 0.88, { fill: C.panel2, line: C.red });
  text(slide, '血乳酸濃度', 6.04, 3.86, 1.99, 0.22, { fontSize: 12.0, bold: true, color: C.white, align: 'center' });
  text(slide, '=', 8.44, 3.83, 0.40, 0.25, { fontSize: 20, bold: true, color: C.red, align: 'center' });
  card(slide, 9.02, 3.58, 2.75, 0.88, { fill: C.panel2, line: C.red });
  text(slide, '通用疲勞百分比', 9.20, 3.86, 2.39, 0.22, { fontSize: 12.0, bold: true, color: C.white, align: 'center' });
  text(slide, '×', 11.97, 3.79, 0.42, 0.28, { fontSize: 22, bold: true, color: C.red, align: 'center' });
  text(slide, '汗乳酸受局部汗腺代謝、汗率、部位、溫濕度與出汗起始影響；Grace 系列研究本身主要使用轉折點。', 1.05, 4.91, 11.20, 0.41, { fontSize: 11.1, color: C.text, align: 'center' });
  card(slide, 1.55, 6.12, 10.23, 0.53, { fill: C.cyan, transparency: 86, line: C.cyan });
  text(slide, '正確產品語意：這是汗液訊號的個人化生理轉折／恢復趨勢，不是血液乳酸替身。', 1.82, 6.29, 9.69, 0.20, { fontSize: 10.7, bold: true, color: C.white, align: 'center' });
  note(slide, 'sLT = sweat lactate threshold。多數研究定義為基線後第一個顯著、持續上升點，並用外部負荷或時間與 LT1/VT1 比較。');
}

// 07 EVIDENCE MAP
{
  const slide = addSlide('證據版圖：廣度增加，但疲勞欄仍只有兩個點', 'EVIDENCE MAP');
  const headers = ['場景／族群','sLT 效度','疲勞／恢復','處方／應用'];
  const hx = [0.62, 3.36, 6.18, 9.03];
  const hw = [2.50, 2.55, 2.55, 3.68];
  headers.forEach((h,i)=>{
    card(slide,hx[i],1.25,hw[i],0.52,{fill:i===0?C.panel3:C.panel2,line:C.border});
    text(slide,h,hx[i]+0.10,1.42,hw[i]-0.20,0.18,{fontSize:10.3,bold:true,color:i===0?C.cyan2:C.white,align:'center'});
  });
  const rows = [
    ['自行車・健康/CVD','C01・C04','C02','C03 EMS'],
    ['訓練強度','C05','—','MLSS 分層'],
    ['低氧','C06','—','低氧 AeT'],
    ['游泳','C07','—','水下訓練'],
    ['心衰竭 NYHA I–II','C08','—','臨床 VT 輔助'],
    ['足球員','既有方法','C09','賽後追蹤'],
    ['健康女性／上肢','C10・C11','—','性別／型態擴展']
  ];
  rows.forEach((r,ri)=>{
    const y=1.90+ri*0.66;
    r.forEach((v,ci)=>{
      const has=v!=='—';
      card(slide,hx[ci],y,hw[ci],0.51,{fill:ri%2?C.panel:C.panel2,line:C.border});
      const color=ci===2&&has?C.orange:(ci===1&&has?C.cyan:(ci===3&&has?C.blue:C.muted));
      text(slide,v,hx[ci]+0.10,y+0.17,hw[ci]-0.20,0.17,{fontSize:9.4,bold:has&&ci>0,color:ci===0?C.text:color,align:'center'});
    });
  });
  card(slide,1.15,6.72,11.05,0.31,{fill:C.orange,transparency:86,line:C.orange});
  text(slide,'直接疲勞證據：C02（力竭後立即）＋ C09（足球賽後 48 小時）；尚無女性、臨床或多中心疲勞驗證。',1.35,6.81,10.65,0.15,{fontSize:9.0,bold:true,color:C.white,align:'center'});
  note(slide, '版圖顯示核心研究在哪些場景支援「閾值效度」與「疲勞」。廣泛的閾值研究不能自動視為疲勞效度。');
}

// 08-18 STUDIES
studySlide({
  id:'C01', year:'2021', domain:'FOUNDATION', color:C.cyan, badge:'自行車・健康＋CVD', badgeW:1.80,
  title:'初代裝置與 LT1／VT1 驗證', journal:'Scientific Reports 11:4929', doi:'10.1038/s41598-021-84381-9',
  source:'Seki et al., Scientific Reports (2021) · PMID 33654133 · PMCID PMC7925537',
  metrics:[
    {value:'65',label:'總納入',sub:'23 healthy + 42 CVD'},
    {value:'.92',label:'sLT ↔ bLT',sub:'可分析子集',color:C.lime},
    {value:'.71',label:'sLT ↔ VT1',sub:'仍有方法偏差',color:C.blue}
  ],
  method:'遞增自行車測試；汗乳酸即時連續顯示，與血液 LT1、換氣 VT1 的工作功率比較。健康者多置上臂，CVD 患者多置前額。',
  findings:'• 可出現汗訊號者可辨識第一上升點。\n• 平均功率差：sLT–bLT -4.5 W；sLT–VT1 +2.5 W。\n• 建立後續研究共同方法：看轉折，不看通用濃度。',
  limitations:'• 42 名 CVD 中僅 23 名有感測反應；血乳酸可分析者更少。\n• 單中心、無汗率、無 LOx-free 控制。\n• sLT–VT1 另見固定／比例偏差；低汗與較嚴重 HF 不適用。',
  implication:'效度必須同時報告「可分析率＋偏差」，不能只報高相關。',
  notes:'完整來源：https://pmc.ncbi.nlm.nih.gov/articles/PMC7925537/。COI：Nakashima 為 Grace Imaging 創辦人/股東，另有作者為公司員工。'
});

studySlide({
  id:'C02', year:'2022', domain:'DIRECT FATIGUE', color:C.orange, badge:'力竭後立即重測', badgeW:1.63,
  title:'疲勞後固定負荷汗乳酸曲線左移', journal:'Physiological Reports 10(2):e15169', doi:'10.14814/phy2.15169',
  source:'Okawara et al., Physiological Reports (2022) · PMID 35043587 · PMCID PMC8767313',
  metrics:[
    {value:'17',label:'年輕男性',sub:'20.6 ± 0.8 歲'},
    {value:'25%',label:'peak power',sub:'固定負荷',color:C.blue},
    {value:'p<.01',label:'曲線提早',sub:'peak / 2 / 3 / 4 μA',color:C.orange}
  ],
  method:'同一人做兩次固定負荷自行車：Test 1 做到力竭，休息後 Test 2 做 10 分鐘；同步記錄主觀疲勞、汗率與 1 Hz 汗乳酸電流。',
  findings:'• Test 2 主觀疲勞較高。\n• 疲勞後峰值以及 2、3、4 μA 到達時間都顯著提早。\n• 提供「較早反應」作為疲勞方向性特徵。',
  limitations:'• 無先驗樣本數、單一負荷、全為年輕男性。\n• 營養／水分控制有限；3 人無法進入 Test 2。\n• 兩測試更換晶片；沒有客觀多模態疲勞參照。',
  implication:'可支持「曲線時間特徵」，不支持「某濃度＝某疲勞度」。',
  notes:'COI：Nakashima 為公司 president/shareholder，未參與資料取得與分析。研究本身稱 preliminary。'
});

studySlide({
  id:'C03', year:'2022', domain:'METABOLIC PERTURBATION', color:C.blue, badge:'固定負荷＋EMS', badgeW:1.45,
  title:'EMS 條件下 sLT 更早出現', journal:'Sensors 22(24):9585', doi:'10.3390/s22249585',
  source:'Sawada et al., Sensors (2022) · PMID 36559954 · PMCID PMC9784187',
  metrics:[
    {value:'22',label:'健康年輕男性',sub:'15 人完成雙條件 20 min'},
    {value:'20',label:'sLT 可比較',sub:'有／無 EMS',color:C.cyan},
    {value:'−.52',label:'sLT差 ↔ bLA差',sub:'p<.05',color:C.blue}
  ],
  method:'在預測 VT 功率 125% 的固定負荷下，比較無 EMS 與 EMS；耳垂血乳酸每分鐘取樣，前臂汗乳酸連續量測。',
  findings:'• EMS 條件的 sLT 顯著提早。\n• sLT 時間差可解釋部分末端血乳酸差異。\n• 顯示相同外部功率下，代謝刺激改變可反映在轉折時間。',
  limitations:'• 小型全男性樣本；只有 15 人完成兩條件全程。\n• 條件次序看似固定，可能有順序效應。\n• 前一日運動／禁食控制不足；中度相關不是替代血值。',
  implication:'這是代謝刺激研究，不應誤算成第三篇疲勞效度研究。',
  notes:'COI：Nakashima 為 president/shareholder；論文聲明公司未參與研究。支援文章 S02 顯示前額/上臂汗率隨時間和部位不同。'
});

studySlide({
  id:'C04', year:'2023', domain:'SWEAT QUALITY', color:C.yellow, badge:'出汗起始', badgeW:1.15,
  title:'出汗起始不是 sLT；晚出汗會拖延 sLT', journal:'Sensors 23(7):3378', doi:'10.3390/s23073378',
  source:'Maeda et al., Sensors (2023) · PMID 37050438 · PMCID PMC10098635',
  metrics:[
    {value:'40',label:'健康男性',sub:'EP 17 / RP 23'},
    {value:'.68',label:'sLT ↔ bLT',sub:'全體',color:C.cyan},
    {value:'+106.8s',label:'晚出汗子群偏差',sub:'n=5',color:C.orange}
  ],
  method:'遞增自行車；同步量汗乳酸、局部汗率與血乳酸。依暖身時是否已出汗分早出汗 EP 與一般出汗 RP。',
  findings:'• OS–sLT 關聯弱：EP r=.12、RP r=.56。\n• sLT–bLT：EP r=.74、RP r=.61。\n• 出汗不是轉折本身；但晚出汗會使 sLT 晚於真正生理轉折。',
  limitations:'• 觀察性、單一運動、全男性。\n• 晚出汗子群僅 5 人，平均差 106.8 s 的精確度有限。\n• 汗量不足時，任何演算法都無法從尚未到達感測器的汗推斷 sLT。',
  implication:'把「已出汗且訊號穩定」設為硬性品質閘門。',
  notes:'COI：Nakashima 為 Grace Imaging president/shareholder，未參與資料取得與分析。'
});

studySlide({
  id:'C05', year:'2023', domain:'TRAINING PRESCRIPTION', color:C.purple, badge:'MLSS', badgeW:0.90,
  title:'以 sLT 估 MLSS：必須按訓練狀態分層', journal:'Scientific Reports 13:10366', doi:'10.1038/s41598-023-36983-8',
  source:'Muramoto et al., Scientific Reports (2023) · PMID 37365235 · PMCID PMC10293173',
  metrics:[
    {value:'15',label:'成人樣本',sub:'trained 11 / untrained 4'},
    {value:'≥120%',label:'訓練者多數 MLSS',sub:'80% trained',color:C.lime},
    {value:'≤115%',label:'未訓練者多數',sub:'75% untrained',color:C.orange}
  ],
  method:'以 sLT 功率的 110%、115%、120%、125% 各做 30 分鐘固定負荷；血乳酸穩態定義 MLSS，同步量大腿組織氧合。',
  findings:'• 個人 MLSS 分布為 110/115/120/125%：1/4/3/7 人。\n• sLT–VT r=.70。\n• 訓練狀態可能改變 sLT 到可持續強度的倍率。',
  limitations:'• 未訓練組只有 4 人；兩組年齡／體脂不平衡。\n• 未測 130%；單一小型研究。\n• 「120% 或 115%」是分層觀察，不是個人精準處方公式。',
  implication:'不要用單一倍率套所有人；先分層，再做個人驗證。',
  notes:'COI：Nakashima 為 shareholder/CEO；Grace Imaging 提供感測設備。'
});

studySlide({
  id:'C06', year:'2023', domain:'HYPOXIA', color:C.blue, badge:'FiO₂ 15.4%', badgeW:1.22,
  title:'低氧下仍可辨識 sLT，但研究先排除了低汗者', journal:'Scientific Reports 13:22865', doi:'10.1038/s41598-023-49369-7',
  source:'Okawara et al., Scientific Reports (2023) · PMID 38129473 · PMCID PMC10739691',
  metrics:[
    {value:'20',label:'健康受試者',sub:'常氧＋低氧'},
    {value:'.70',label:'sLT ↔ VT',sub:'hypoxia',color:C.cyan},
    {value:'.933',label:'跨評者 ICC',sub:'同評者 .782',color:C.lime}
  ],
  method:'常氧與低氧遞增自行車；同步換氣、汗乳酸與汗率，3 名評者判定 sLT。低氧 FiO₂ 15.4±0.8%。',
  findings:'• 低氧 sLT–VT r=.70；平均時間差 -15.5 s。\n• sLT 跨評者可靠度高。\n• 支援轉折在特定低氧環境的可辨識性。',
  limitations:'• 小型健康年輕男性；只測一種低氧程度。\n• 事先排除上臂最高運動汗率 <0.4 mg/cm²/min 者。\n• 輸出以電流為主，不能推論所有海拔／環境免校正。',
  implication:'選樣已排除低汗者；部署可行性不可直接用 20/20 宣稱。',
  notes:'COI：D.N. 為 Grace Imaging founder/shareholder。'
});

studySlide({
  id:'C07', year:'2024', domain:'SWIMMING', color:C.blue2, badge:'水下穿戴', badgeW:1.16,
  title:'游泳可即時量測；高相關仍伴隨部分系統偏差', journal:'European Journal of Sport Science 24(9):1302–1312', doi:'10.1002/ejsc.12179',
  source:'Okawara et al., EJSS (2024) · PMID 39126367 · PMCID PMC11369350',
  metrics:[
    {value:'24',label:'大學游泳員',sub:'58% male'},
    {value:'.824',label:'sLT速度 ↔ bLT速度',sub:'p<.01',color:C.lime},
    {value:'+0.08',label:'平均速度差',sub:'m/s',color:C.blue2}
  ],
  method:'游泳水槽遞增速度；一天有休息採血、另一天無休息。防水感測器置上臂，連續顯示 sLA。',
  findings:'• 所有測試取得即時曲線。\n• 無休息 sLT 與採血日 bLT r=.868。\n• 顯示可從陸上自行車擴展到水下場景。',
  limitations:'• 部分 Bland–Altman／回歸仍見固定或比例偏差。\n• 單一水槽、水溫、年輕訓練游泳員。\n• 有無休息本身會改變生理與閾值；不可直接沿用自行車常模。',
  implication:'固定防水、部位、溫度與測試流程，並顯示方法偏差。',
  notes:'COI：Nakashima 為 president/shareholder，未參與資料取得與分析。Grace 官網文字 DOI 多一個 0；本簡報已校正為 10.1002/ejsc.12179。'
});

studySlide({
  id:'C08', year:'2024', domain:'CLINICAL HF', color:C.orange, badge:'LacS-001', badgeW:1.08,
  title:'心衰竭試驗達主要門檻，但只有 32/50 進入比較', journal:'Scientific Reports 14:18985', doi:'10.1038/s41598-024-70001-9',
  source:'Katsumata et al., Scientific Reports (2024) · PMID 39152287 · PMCID PMC11329511',
  metrics:[
    {value:'50',label:'NYHA I–II',sub:'前瞻性臨床試驗'},
    {value:'32/50',label:'主要分析',sub:'64%',color:C.orange},
    {value:'.651',label:'sLT ↔ VT',sub:'95% CI .391–.815',color:C.cyan}
  ],
  method:'RAMP 自行車 CPET；前額汗乳酸 1 Hz；3 名獨立評者判 sLT。預設相關 ≥.60、差異 SD ≤15 W，並追蹤裝置安全。',
  findings:'• sLT–VT 差 -4.9±15.0 W；sLT ICC=.701。\n• 低／中／高汗率明確判定率 53%／100%／75%。\n• 無裝置相關不良事件；2 件心律不整歸因運動負荷。',
  limitations:'• 1 人流程偏差、12 人 sLT 難判，另有 VT 難判。\n• 只納入較輕 HF、相對高功能且多為男性。\n• 不代表 NYHA III、低汗者或大型真實世界安全性。',
  implication:'臨床報告首頁要同時顯示「準確度」與「無法判讀比例」。',
  notes:'COI：Nakashima 為 founder/shareholder；另一作者為 founder/shareholder 與感測晶片專利持有人。'
});

studySlide({
  id:'C09', year:'2025→26', domain:'DIRECT FATIGUE', color:C.orange, badge:'足球賽後 48 h', badgeW:1.50,
  title:'高速跑動越多，賽後 sLT 越傾向提早／下降', journal:'Fatigue: Biomedicine, Health & Behavior 14(1):27–41', doi:'10.1080/21641846.2025.2554557',
  source:'Takemoto et al. · Online 2025-09-07; issue 2026 · DOI 10.1080/21641846.2025.2554557',
  metrics:[
    {value:'18',label:'男性大學足球員',sub:'2 次賽前 + 1 次賽後'},
    {value:'.777',label:'sLT test–retest ICC',sub:'95% CI .506–.910',color:C.cyan},
    {value:'.64',label:'ΔsLT ↔ 高速距離',sub:'p<.05',color:C.orange}
  ],
  method:'兩次賽前遞增測試建立可靠度與 MDC95；比賽後第 2 天再測。10 Hz GNSS 記錄高速跑動距離。',
  findings:'• 高速跑動越多，賽後 sLT 越低／越早。\n• ΔsLT 與 ΔVT r=.77。\n• sLT 功率 MDC95 約 10 W；超過 MDC 的子群仍有中度關聯。',
  limitations:'• 小型、男性、單一比賽、單一賽後時間點。\n• ICC 未達部分個人監測偏好的 .90；環境與間隔影響重測。\n• 未直接對照荷爾蒙、發炎、免疫、酵素或神經肌肉標記。',
  implication:'10 W 只是一個流程示例；LA-01 必須建立自己的個人 MDC。',
  notes:'COI：Nakashima 為 president/shareholder，未參與資料取得與分析。線上日期與正式卷期必須分開記錄，避免重複。'
});

studySlide({
  id:'C10', year:'2026', domain:'HEALTHY WOMEN', color:C.lime, badge:'低汗率挑戰', badgeW:1.32,
  title:'女性 16/16 可測，但 sLT 系統性晚於 VT', journal:'International Journal of Sports Medicine 47(6):425–432', doi:'10.1055/a-2771-5130',
  source:'Sawada et al., IJSM (2026) · Epub 2026-01-12 · PMID 41525782 · 本次依摘要層級整理',
  metrics:[
    {value:'16/16',label:'sLT 可偵測',sub:'健康女性'},
    {value:'.769',label:'sLT ↔ VT',sub:'Spearman',color:C.cyan},
    {value:'.873',label:'出汗起始 ↔ 偏差',sub:'late sweat risk',color:C.orange}
  ],
  method:'健康女性接受呼吸氣體運動測試；穿戴式汗乳酸與通風膠囊汗率計同步；分析 sLT–VT 及出汗動力學。',
  findings:'• 所有人可偵測 sLT。\n• sLT 與 VT 顯著相關。\n• 但 sLT 顯著較晚，且閾值越高差異越大；晚出汗是誤差關鍵。',
  limitations:'• 僅 16 名健康女性。\n• 高相關與系統性延遲可同時存在。\n• 本次僅依 PubMed 摘要與書目整理，未把未核對的全文細節加入結論。',
  implication:'女性／低汗者需要延遲偵測與低信心狀態，不能硬套男性流程。',
  notes:'COI：Nakashima 為 president/shareholder；公司未參與研究。本篇未列在本次抓取的 Grace 官方 Paper 清單，是只看官網會漏掉的新文。'
});

studySlide({
  id:'C11', year:'2026', domain:'ARM CRANK', color:C.lime, badge:'上肢運動', badgeW:1.12,
  title:'手搖車跨型態驗證：功率相關 .904、無系統偏差', journal:'Physiological Reports 14(13):e71002', doi:'10.14814/phy2.71002',
  source:'Sawada et al., Physiological Reports (2026) · PMID 42405472 · PMCID PMC13334460',
  metrics:[
    {value:'27',label:'健康年輕成人',sub:'9 男 / 18 女'},
    {value:'.904',label:'sLT ↔ VT1 功率',sub:'time r=.859',color:C.lime},
    {value:'+0.2W',label:'平均功率差',sub:'time -7.7 s',color:C.cyan}
  ],
  method:'手搖車 5 W/min 遞增測試；前額汗乳酸、汗率、心率與呼吸氣體同步。所有人皆有足夠汗且可辨識 sLT。',
  findings:'• 功率與時間都高度相關。\n• Bland–Altman 無固定或比例偏差。\n• sLT 與 VT1 當下心率無顯著差，支援上肢 AeT 評估。',
  limitations:'• 年輕健康單一大學、受控環境、只量前額。\n• 1 分鐘階段較短；未正式評估最大有氧能力。\n• 不能直接外推脊髓損傷、自主神經或排汗異常族群。',
  implication:'跨運動型態可行，但「可出汗」仍是先決條件。',
  notes:'COI：Nakashima 為 president/shareholder；公司未參與研究。Grace 官網文字 DOI 誤植為 phy2.17002，正確為 phy2.71002。'
});

// 19 QUANTITATIVE SYNTHESIS
{
  const slide = addSlide('跨研究數字：相關係數方向一致，但不能直接排名', 'DESCRIPTIVE SYNTHESIS');
  const left = [
    ['C01 sLT–bLT',.920,C.lime],['C01 sLT–VT1',.710,C.blue],['C04 sLT–bLT',.680,C.cyan],['C05 sLT–VT',.700,C.purple]
  ];
  const right = [
    ['C06 低氧 sLT–VT',.700,C.blue],['C07 游泳 sLT–bLT',.824,C.blue2],['C08 HF sLT–VT',.651,C.orange],['C11 手搖車 sLT–VT1',.904,C.lime]
  ];
  card(slide,0.62,1.30,5.95,4.22,{fill:C.panel2,line:C.border});
  card(slide,6.77,1.30,5.94,4.22,{fill:C.panel2,line:C.border});
  text(slide,'自行車／訓練',0.92,1.60,2.10,0.24,{fontSize:13,bold:true,color:C.cyan2});
  text(slide,'情境／族群擴展',7.07,1.60,2.40,0.24,{fontSize:13,bold:true,color:C.cyan2});
  left.forEach((r,i)=>bar(slide,0.92,2.15+i*0.73,5.30,r[1],1,r[0],r[1].toFixed(3),r[2]));
  right.forEach((r,i)=>bar(slide,7.07,2.15+i*0.73,5.30,r[1],1,r[0],r[1].toFixed(3),r[2]));
  card(slide,0.90,5.88,11.55,0.80,{fill:C.panel,line:C.yellow});
  text(slide,'⚠ 不是同一 endpoint、族群、部位、流程或分析集；bar 只呈現方向，不能當作裝置性能排行榜。',1.18,6.10,11.0,0.22,{fontSize:10.7,bold:true,color:C.yellow,align:'center'});
  text(slide,'還要看：可分析率 · mean bias · limits of agreement · 固定／比例偏差 · ICC · SEM · MDC95',1.18,6.40,11.0,0.18,{fontSize:9.0,color:C.muted,align:'center'});
  note(slide,'C10 健康女性為 Spearman r=.769，但同時有系統性延遲，故不放入直觀排行榜主體以免忽略偏差。');
}

// 20 ANALYZABILITY
{
  const slide = addSlide('真正部署風險：不是每個人都能產生可判讀的 sLT', 'ANALYZABILITY');
  card(slide,0.62,1.30,7.48,4.70,{fill:C.panel2,line:C.border});
  text(slide,'研究內觀察到的可用比例',0.92,1.60,2.65,0.26,{fontSize:14,bold:true,color:C.cyan2});
  bar(slide,0.92,2.22,6.80,23,42,'2021 CVD 感測反應','23/42 · 55%',C.orange);
  bar(slide,0.92,2.95,6.80,37,50,'2024 HF 可判 sLT','37/50 · 74%',C.blue);
  bar(slide,0.92,3.68,6.80,32,50,'2024 HF 主要分析','32/50 · 64%',C.orange);
  bar(slide,0.92,4.41,6.80,16,16,'2026 健康女性','16/16 · 100%',C.lime);
  bar(slide,0.92,5.14,6.80,27,27,'2026 手搖車','27/27 · 100%',C.lime);
  card(slide,8.38,1.30,4.33,4.70,{fill:C.panel,line:C.yellow,lineWidth:1.2});
  text(slide,'為何不能直接比較？',8.67,1.64,3.75,0.28,{fontSize:15,bold:true,color:C.yellow});
  bullet(slide,'選樣不同','低氧研究先排除低汗者；HF 與健康人條件不同。',8.67,2.24,3.50,{color:C.orange,bodyH:0.44});
  bullet(slide,'環境不同','前額／上臂、溫濕度、暖身與負荷流程改變出汗。',8.67,3.16,3.50,{color:C.blue,bodyH:0.44});
  bullet(slide,'100% ≠ 普遍可行','控制環境的小樣本不代表真實世界所有人。',8.67,4.08,3.50,{color:C.lime,bodyH:0.44});
  bullet(slide,'高汗也可能難判','HF 研究中高汗率組可判率 75%，不只低汗有問題。',8.67,5.00,3.50,{color:C.cyan,bodyH:0.44});
  card(slide,1.32,6.37,10.68,0.42,{fill:C.red,transparency:88,line:C.red});
  text(slide,'產品規則：無汗／晚汗／多轉折／訊號不穩 → 「無法判讀」，不是補值成疲勞。',1.58,6.50,10.16,0.17,{fontSize:9.8,bold:true,color:C.white,align:'center'});
  note(slide,'比例來自不同研究，目的在提醒可分析率而非做統計比較。2024 HF 低/中/高汗率明確 sLT 為 53/100/75%。');
}

// 21 FATIGUE SYNTHESIS
{
  const slide = addSlide('疲勞證據只有兩篇：方向一致，外部效度仍不足', 'FATIGUE EVIDENCE');
  card(slide,0.62,1.34,5.85,4.55,{fill:C.panel2,line:C.orange,lineWidth:1.2});
  pill(slide,'C02 · IMMEDIATE',0.90,1.66,1.52,C.orange,{fontFace:ENFONT,fontSize:8.5});
  text(slide,'力竭後立即重測',0.90,2.16,3.00,0.30,{fontSize:17,bold:true,color:C.white});
  text(slide,'n=17 · 年輕男性 · 固定負荷',0.90,2.56,3.50,0.22,{fontSize:10,color:C.muted});
  // schematic curve
  segment(slide,1.02,4.72,5.95,4.72,{color:C.grid,width:1});
  segment(slide,1.02,3.05,1.02,4.72,{color:C.grid,width:1});
  const curve=(shift,color)=>{
    let prev=null;
    for(let i=0;i<=30;i++){
      const t=i/30; const xx=1.12+t*4.55; const yy=4.55-1.18/(1+Math.exp(-(t-(0.57-shift))*15));
      if(prev)segment(slide,prev[0],prev[1],xx,yy,{color,width:2}); prev=[xx,yy];
    }
  };
  curve(0,C.blue); curve(0.18,C.orange);
  text(slide,'休息／前',4.72,4.42,0.90,0.18,{fontSize:8.4,color:C.blue});
  text(slide,'疲勞後',2.86,3.25,0.90,0.18,{fontSize:8.4,color:C.orange});
  text(slide,'峰值與固定 μA 點更早（p<.01）',0.90,5.22,5.02,0.24,{fontSize:11.1,bold:true,color:C.orange,align:'center'});

  card(slide,6.86,1.34,5.85,4.55,{fill:C.panel2,line:C.orange,lineWidth:1.2});
  pill(slide,'C09 · 48 HOURS',7.14,1.66,1.52,C.orange,{fontFace:ENFONT,fontSize:8.5});
  text(slide,'足球比賽後第 2 天',7.14,2.16,3.70,0.30,{fontSize:17,bold:true,color:C.white});
  text(slide,'n=18 · 男性大學生 · GNSS 外部負荷',7.14,2.56,4.55,0.22,{fontSize:10,color:C.muted});
  metric(slide,7.14,3.07,1.56,'.777','sLT ICC',C.cyan,'test–retest');
  metric(slide,8.90,3.07,1.56,'.64','ΔsLT↔HSD',C.orange,'high-speed distance');
  metric(slide,10.66,3.07,1.56,'~10W','MDC95',C.yellow,'該流程限定');
  text(slide,'高速跑動越多 → 賽後 sLT 越低／越早',7.20,4.57,4.95,0.31,{fontSize:12.1,bold:true,color:C.orange,align:'center'});
  text(slide,'未直接對照多模態疲勞標記',7.20,5.17,4.95,0.20,{fontSize:9.3,color:C.muted,align:'center'});

  card(slide,1.05,6.24,11.22,0.59,{fill:C.panel,line:C.red});
  text(slide,'共同缺口：全為年輕男性、小樣本、單中心網絡；沒有女性／年長者／臨床族群的疲勞效度，也沒有通用 cutoff。',1.32,6.44,10.68,0.20,{fontSize:9.8,bold:true,color:C.white,align:'center'});
  note(slide,'曲線為概念示意，不是原論文數據重製。HSD = high-speed distance。兩篇皆支持較早反應方向，但時間尺度與測試設計不同。');
}

// 22 CLAIMS
{
  const slide = addSlide('可以說什麼／不能說什麼：把行銷語言鎖在證據內', 'CLAIM BOUNDARY');
  card(slide,0.62,1.30,5.85,5.23,{fill:C.panel2,line:C.lime,lineWidth:1.2});
  text(slide,'目前可支持',0.93,1.63,2.10,0.30,{fontSize:17,bold:true,color:C.lime});
  checkRow(slide,true,'非侵入、連續的汗乳酸曲線','在足夠出汗與穩定接觸下取得 1 Hz 連續訊號。',0.93,2.20,5.05);
  checkRow(slide,true,'sLT 可近似第一生理轉折','多場景與 LT1／VT1 有中度至高度關聯。',0.93,3.13,5.05);
  checkRow(slide,true,'個人內變化可能反映負荷／恢復','兩篇疲勞研究方向一致，但應標示 preliminary。',0.93,4.06,5.05);
  checkRow(slide,true,'資料不足可以被辨識','晚汗、低汗、多轉折與訊號不穩應回傳不可判讀。',0.93,4.99,5.05);

  card(slide,6.86,1.30,5.85,5.23,{fill:C.panel2,line:C.red,lineWidth:1.2});
  text(slide,'目前不支持',7.17,1.63,2.10,0.30,{fontSize:17,bold:true,color:C.red});
  checkRow(slide,false,'汗濃度直接等於血濃度','汗腺局部代謝與汗率使兩種體液不可直接互換。',7.17,2.20,5.05);
  checkRow(slide,false,'單次絕對值就是疲勞','沒有通用 μA／mmol/L 疲勞切點或 0–100 公式。',7.17,3.13,5.05);
  checkRow(slide,false,'已診斷過度訓練／受傷風險','沒有臨床結果或傷害預測試驗。',7.17,4.06,5.05);
  checkRow(slide,false,'可完全取代 CPET／完整評估','HF 可分析率與女性延遲顯示仍需替代方案與複核。',7.17,4.99,5.05);
  note(slide,'建議產品用語使用「可能的恢復/負荷反應」與「閾值信心」，避免確診式語言。');
}

// 23 UI
{
  const slide = addSlide('LA-01 建議畫面：四層資訊，不把 μA 放成疲勞分數', 'PRODUCT DISPLAY');
  card(slide,0.62,1.22,5.10,5.62,{fill:'0A1726',line:C.cyan,lineWidth:1.4});
  text(slide,'今日恢復趨勢',0.94,1.55,2.20,0.29,{fontSize:16,bold:true,color:C.white});
  pill(slide,'資料品質 PASS',3.67,1.50,1.55,C.lime,{fontSize:8.4});
  text(slide,'sLT',0.94,2.22,0.80,0.22,{fontFace:ENFONT,fontSize:11,bold:true,color:C.muted});
  text(slide,'124 W',0.94,2.50,2.20,0.55,{fontFace:ENFONT,fontSize:31,bold:true,color:C.cyan2});
  text(slide,'HR 148 bpm  ·  08:14',0.94,3.12,3.60,0.22,{fontFace:ENFONT,fontSize:10,color:C.muted});
  card(slide,0.94,3.65,4.46,1.04,{fill:C.panel2,line:C.orange});
  text(slide,'−9%',1.18,3.88,1.12,0.39,{fontFace:ENFONT,fontSize:23,bold:true,color:C.orange});
  text(slide,'相對個人同流程基準',2.45,3.84,2.55,0.24,{fontSize:11,bold:true,color:C.white});
  text(slide,'超過個人 MDC → 可能降低，建議複核',2.45,4.18,2.55,0.22,{fontSize:8.6,color:C.muted});
  text(slide,'信心',0.94,5.12,0.70,0.20,{fontSize:9.5,bold:true,color:C.white});
  slide.addShape(pptx.ShapeType.roundRect,{x:1.70,y:5.14,w:3.70,h:0.17,fill:{color:C.grid},line:{color:C.grid,transparency:100}});
  slide.addShape(pptx.ShapeType.roundRect,{x:1.70,y:5.14,w:2.82,h:0.17,fill:{color:C.yellow},line:{color:C.yellow,transparency:100}});
  text(slide,'出汗已開始 · 基線穩定 · 室溫相符',0.94,5.56,4.46,0.21,{fontSize:9.1,color:C.text});
  text(slide,'示意數字，非已驗證 cutoff',0.94,6.32,4.46,0.18,{fontSize:8.2,color:C.red,italic:true,align:'center'});

  const layers = [
    ['01','資料品質','汗起始・汗率・接觸・基線・環境',C.yellow],
    ['02','本次 sLT','時間・功率／速度・當下心率',C.cyan],
    ['03','個人內變化','同流程 rolling baseline + MDC',C.orange],
    ['04','複核訊息','RPE／HRV／CMJ／睡眠／外部負荷',C.blue]
  ];
  layers.forEach((l,i)=>{
    const y=1.34+i*1.30;
    card(slide,6.10,y,6.61,1.03,{fill:C.panel2,line:l[3]});
    slide.addShape(pptx.ShapeType.ellipse,{x:6.35,y:y+0.23,w:0.52,h:0.52,fill:{color:l[3]},line:{color:l[3],transparency:100}});
    text(slide,l[0],6.35,y+0.39,0.52,0.17,{fontFace:ENFONT,fontSize:9,bold:true,color:C.dark,align:'center'});
    text(slide,l[1],7.12,y+0.19,1.72,0.27,{fontSize:14,bold:true,color:l[3]});
    text(slide,l[2],7.12,y+0.59,5.15,0.21,{fontSize:9.8,color:C.text});
  });
  card(slide,6.50,6.61,5.81,0.28,{fill:C.red,transparency:86,line:C.red});
  text(slide,'無法判讀也是合法結果；禁止用插值偽造疲勞分數。',6.72,6.69,5.37,0.14,{fontSize:8.5,bold:true,color:C.white,align:'center'});
  note(slide,'畫面為產品概念稿。124 W、-9% 等純屬示意，不是研究 cutoff。原始 μA 可放研究模式，不作主畫面疲勞分數。');
}

// 24 ALGORITHM
{
  const slide = addSlide('最小判讀演算法：先 QC，再 ΔsLT，最後才談恢復', 'DECISION LOGIC');
  const steps = [
    ['1','QC PASS?','出汗、基線、接觸、環境'],
    ['2','同流程？','部位、暖身、負荷斜率一致'],
    ['3','算 ΔsLT','相對個人 3–5 次中位數'],
    ['4','超過 MDC？','LA-01 自建 individual error'],
    ['5','第二指標？','同方向才升級提醒']
  ];
  steps.forEach((s,i)=>{
    const x=0.62+i*2.49;
    card(slide,x,1.45,2.13,1.47,{fill:C.panel2,line:i===0?C.yellow:(i===4?C.blue:C.cyan)});
    slide.addShape(pptx.ShapeType.ellipse,{x:x+0.12,y:1.60,w:0.38,h:0.38,fill:{color:i===0?C.yellow:(i===4?C.blue:C.cyan)},line:{color:C.cyan,transparency:100}});
    text(slide,s[0],x+0.12,1.705,0.38,0.14,{fontFace:ENFONT,fontSize:8.7,bold:true,color:C.dark,align:'center'});
    text(slide,s[1],x+0.59,1.60,1.37,0.25,{fontSize:12.6,bold:true,color:C.white});
    text(slide,s[2],x+0.16,2.20,1.81,0.39,{fontSize:8.9,color:C.muted,align:'center'});
    if(i<4) slide.addShape(pptx.ShapeType.chevron,{x:x+2.20,y:1.95,w:0.22,h:0.36,fill:{color:C.grid},line:{color:C.grid,transparency:100}});
  });
  card(slide,0.62,3.35,7.32,2.52,{fill:C.panel,line:C.border});
  sectionLabel(slide,'PSEUDOCODE',0.92,3.67,1.45,C.cyan);
  text(slide,
`if QC != PASS or protocol != MATCH:\n    result = UNAVAILABLE\nelse:\n    delta = sLT_today - personal_baseline\n    if abs(delta) <= individual_MDC: STABLE\n    elif delta < -individual_MDC: POSSIBLE_REDUCED_READINESS\n    else: POSSIBLE_IMPROVEMENT`,
  0.92,4.02,6.72,1.51,{fontFace:'Courier New',fontSize:10.6,color:C.text});
  card(slide,8.23,3.35,4.48,2.52,{fill:C.panel2,line:C.orange});
  text(slide,'必要保護欄',8.52,3.69,2.10,0.27,{fontSize:14.5,bold:true,color:C.orange});
  bullet(slide,'MDC 不能借用','足球研究約 10 W 只限該流程。',8.52,4.21,3.75,{color:C.yellow,bodyH:0.34});
  bullet(slide,'負向只叫「可能」','單次下降不能診斷過度訓練。',8.52,4.93,3.75,{color:C.orange,bodyH:0.34});
  card(slide,1.43,6.31,10.47,0.45,{fill:C.cyan,transparency:87,line:C.cyan});
  text(slide,'推薦 baseline：同部位、同環境範圍、同負荷 protocol 的最近 3–5 次有效測試中位數。',1.70,6.46,9.93,0.17,{fontSize:9.3,bold:true,color:C.white,align:'center'});
  note(slide,'演算法為證據導向的最小框架，仍需在 LA-01 資料上驗證。可用 robust median/MAD 建立個人誤差，但不能用未驗證百分比對外宣稱疲勞。');
}

// 25 ROADMAP
{
  const slide = addSlide('驗證路線：把「可測」推進到「可做個人決策」', 'VALIDATION ROADMAP');
  const phases = [
    ['01','分析可靠度','同日／跨日 test–retest\nCV・SEM・MDC95','鎖定 protocol',C.cyan],
    ['02','族群與場景','女性・低汗・年長\n不同部位／溫濕度','避免選樣偏差',C.lime],
    ['03','疲勞效度','RPE・HRV・CMJ・CK\n睡眠・GNSS 負荷','多模態模型',C.orange],
    ['04','臨床／外部','多中心・預註冊\n盲化・自動演算法','獨立重現',C.purple]
  ];
  phases.forEach((p,i)=>{
    const x=0.62+i*3.03;
    card(slide,x,1.42,2.76,4.32,{fill:C.panel2,line:p[4],lineWidth:1.3});
    pill(slide,p[0],x+0.20,1.68,0.58,p[4],{fontFace:ENFONT,fontSize:9});
    text(slide,p[1],x+0.20,2.27,2.36,0.39,{fontSize:16,bold:true,color:p[4],align:'center'});
    text(slide,p[2],x+0.25,3.05,2.26,0.80,{fontSize:11.2,color:C.text,align:'center'});
    segment(slide,x+0.40,4.23,x+2.36,4.23,{color:C.border,width:1});
    text(slide,p[3],x+0.25,4.58,2.26,0.36,{fontSize:11.0,bold:true,color:C.white,align:'center'});
    if(i<3) slide.addShape(pptx.ShapeType.chevron,{x:x+2.80,y:3.15,w:0.19,h:0.45,fill:{color:C.grid},line:{color:C.grid,transparency:100}});
  });
  card(slide,1.02,6.13,11.30,0.62,{fill:C.panel,line:C.yellow});
  rich(slide,[
    {text:'先分開驗證｜',options:{bold:true,color:C.yellow}},
    {text:'「找 AeT／LT1」與「判讀疲勞」是兩個不同 intended use；前者證據較多，不代表後者自動成立。',options:{bold:true,color:C.white}}
  ],1.30,6.34,10.74,0.20,{fontSize:10.2,align:'center'});
  note(slide,'優先順序：先以 LA-01 自身資料估誤差，再做跨性別/低汗者與多模態疲勞效度，最後才是臨床宣稱。');
}

// 26 COI + QA
{
  const slide = addSlide('利益衝突與書目 QA：透明揭露，不等於獨立驗證', 'GOVERNANCE');
  metric(slide,0.62,1.33,2.25,'11/11','核心文揭露公司關係',C.yellow,'founder / CEO / president / shares');
  metric(slide,3.10,1.33,2.25,'0','本集合外部獨立研究',C.red,'依納入條件都含 Nakashima');
  metric(slide,5.58,1.33,2.25,'2','官網 DOI 文字誤植',C.orange,'連結／出版社核對修正');
  card(slide,8.06,1.33,4.65,1.12,{fill:C.panel2,line:C.lime});
  text(slide,'透明度加分項',8.34,1.56,1.55,0.20,{fontSize:9.7,bold:true,color:C.lime});
  text(slide,'多篇明載未參與資料取得／分析，或公司未參與。',8.34,1.88,4.05,0.30,{fontSize:10.6,color:C.white});

  card(slide,0.62,2.87,5.86,3.40,{fill:C.panel2,line:C.border});
  text(slide,'COI 仍需補強的設計',0.92,3.18,2.75,0.27,{fontSize:15,bold:true,color:C.cyan2});
  bullet(slide,'事前鎖定','自動閾值演算法、排除條件與主要分析集。',0.92,3.73,5.05,{color:C.cyan,bodyH:0.34});
  bullet(slide,'完整失敗資料','無汗、晚汗、多轉折與無法判讀不能消失。',0.92,4.47,5.05,{color:C.orange,bodyH:0.34});
  bullet(slide,'外部複現','無股權／無公司作者團隊，多中心盲化驗證。',0.92,5.21,5.05,{color:C.lime,bodyH:0.34});

  card(slide,6.80,2.87,5.91,3.40,{fill:C.panel2,line:C.orange});
  text(slide,'本次書目 QA 發現',7.10,3.18,2.75,0.27,{fontSize:15,bold:true,color:C.orange});
  text(slide,'官網文字',7.10,3.78,1.05,0.20,{fontSize:9.2,color:C.muted,bold:true});
  text(slide,'phy2.17002',8.27,3.76,1.45,0.22,{fontFace:ENFONT,fontSize:10.5,color:C.red});
  text(slide,'→',9.82,3.76,0.40,0.22,{fontSize:12,color:C.muted,align:'center'});
  text(slide,'phy2.71002',10.30,3.76,1.55,0.22,{fontFace:ENFONT,fontSize:10.5,bold:true,color:C.lime});
  text(slide,'官網文字',7.10,4.49,1.05,0.20,{fontSize:9.2,color:C.muted,bold:true});
  text(slide,'10.10002',8.27,4.47,1.45,0.22,{fontFace:ENFONT,fontSize:10.5,color:C.red});
  text(slide,'→',9.82,4.47,0.40,0.22,{fontSize:12,color:C.muted,align:'center'});
  text(slide,'10.1002',10.30,4.47,1.55,0.22,{fontFace:ENFONT,fontSize:10.5,bold:true,color:C.lime});
  text(slide,'漏列',7.10,5.20,1.05,0.20,{fontSize:9.2,color:C.muted,bold:true});
  text(slide,'健康女性 2026',8.27,5.18,3.58,0.22,{fontSize:10.5,bold:true,color:C.yellow});
  text(slide,'只看公司 Paper 頁會漏文；應與 PubMed／作者索引交叉。',7.10,5.65,5.10,0.26,{fontSize:9.3,color:C.text});
  note(slide,'COI 揭露不代表研究無效，但需要更高程度的預註冊、原始資料/程式碼、外部重現與完整失敗個案呈現。');
}

// 27 MONITORING
{
  const slide = addSlide('持續追蹤：每季四路查詢，保留 online 與 issue 日期', 'LIVING TRACKER');
  const sources = [
    ['ORCID','0000-0003-1105-2669',C.cyan],
    ['PubMed','Nakashima D + sweat + lactate',C.blue],
    ['Crossref','author + keyword + DOI',C.purple],
    ['Grace / J-GLOBAL','Paper + News + 作者頁',C.orange]
  ];
  sources.forEach((s,i)=>{
    const x=0.62+i*3.03;
    card(slide,x,1.39,2.77,1.34,{fill:C.panel2,line:s[2]});
    text(slide,s[0],x+0.18,1.70,2.41,0.29,{fontFace:ENFONT,fontSize:15,bold:true,color:s[2],align:'center'});
    text(slide,s[1],x+0.18,2.20,2.41,0.19,{fontFace:i===0?ENFONT:FONT,fontSize:8.6,color:C.muted,align:'center'});
  });
  card(slide,0.62,3.10,7.18,3.32,{fill:C.panel,line:C.border});
  text(slide,'新增文章最小欄位',0.92,3.43,2.45,0.27,{fontSize:15,bold:true,color:C.cyan2});
  const fields=[
    'online date／issue date／DOI／PMID／PMCID',
    '族群・性別・年齡・部位・環境・protocol',
    'sLT 定義・演算法・盲化・可分析率',
    '相關＋agreement＋ICC／SEM／MDC',
    'COI・公司參與・設備提供・專利',
    '是否真正支援疲勞，而非只有閾值'
  ];
  fields.forEach((f,i)=>{
    const x=i%2===0?0.94:4.30; const y=4.06+Math.floor(i/2)*0.69;
    slide.addShape(pptx.ShapeType.ellipse,{x,y:y+0.04,w:0.13,h:0.13,fill:{color:i<2?C.cyan:(i<4?C.blue:C.orange)},line:{color:C.cyan,transparency:100}});
    text(slide,f,x+0.22,y,3.00,0.36,{fontSize:9.5,color:C.text});
  });
  card(slide,8.10,3.10,4.61,3.32,{fill:C.panel2,line:C.lime});
  text(slide,'本次可更新交付',8.40,3.43,3.95,0.27,{fontSize:15,bold:true,color:C.lime});
  text(slide,'✓ 逐篇繁中 Markdown 報告\n\n✓ 27 欄、14 筆 CSV 追蹤表\n\n✓ 研究簡報（本檔）\n\n✓ ZIP 一次下載包',8.44,4.04,3.74,1.82,{fontSize:11.3,color:C.text});
  card(slide,1.42,6.70,10.49,0.26,{fill:C.cyan,transparency:88,line:C.cyan});
  text(slide,'建議頻率：每季固定更新；出現新 DOI／臨床試驗結果時即時增量更新。',1.66,6.77,10.01,0.13,{fontSize:8.4,bold:true,color:C.white,align:'center'});
  note(slide,'CSV 欄位可直接排序或匯入試算表。新的論文應先判斷核心/支援/排除，再更新簡報結論。');
}

// 28 REFERENCES I
{
  const slide = addSlide('核心文獻 1/2', 'REFERENCES');
  const refs = [
    ['C01','Seki Y, Nakashima D, et al. A novel device for detecting anaerobic threshold using sweat lactate during exercise. Scientific Reports. 2021;11:4929.','10.1038/s41598-021-84381-9'],
    ['C02','Okawara H, Sawada T, Nakashima D, et al. Kinetic changes in sweat lactate following fatigue during constant workload exercise. Physiological Reports. 2022;10:e15169.','10.14814/phy2.15169'],
    ['C03','Sawada T, Okawara H, Nakashima D, et al. Constant Load Pedaling Exercise Combined with Electrical Muscle Stimulation Leads to an Early Increase in Sweat Lactate Levels. Sensors. 2022;22:9585.','10.3390/s22249585'],
    ['C04','Maeda Y, Okawara H, Sawada T, Nakashima D, et al. Implications of the Onset of Sweating on the Sweat Lactate Threshold. Sensors. 2023;23:3378.','10.3390/s23073378'],
    ['C05','Muramoto Y, Nakashima D, et al. Estimation of maximal lactate steady state using the sweat lactate sensor. Scientific Reports. 2023;13:10366.','10.1038/s41598-023-36983-8'],
    ['C06','Okawara H, Iwasawa Y, Sawada T, et al. Anaerobic threshold using sweat lactate sensor under hypoxia. Scientific Reports. 2023;13:22865.','10.1038/s41598-023-49369-7']
  ];
  refs.forEach((r,i)=>{
    const y=1.23+i*0.91;
    pill(slide,r[0],0.67,y,0.58,i===1?C.orange:C.cyan,{fontFace:ENFONT,fontSize:8.4});
    text(slide,r[1],1.48,y-0.01,10.84,0.45,{fontFace:ENFONT,fontSize:9.8,color:C.text});
    link(slide,r[2],`https://doi.org/${r[2]}`,1.48,y+0.50,4.35);
  });
  note(slide,'所有 DOI 已以 PubMed/PMC 或出版社頁核對。');
}

// 29 REFERENCES II
{
  const slide = addSlide('核心文獻 2/2 ＋ 支援文章', 'REFERENCES');
  const refs = [
    ['C07','Okawara H, Sawada T, Nakashima D, et al. Lactate threshold evaluation in swimming using a sweat lactate sensor. European Journal of Sport Science. 2024;24:1302–1312.','10.1002/ejsc.12179'],
    ['C08','Katsumata Y, Muramoto Y, et al. Sweat lactate sensor for detecting anaerobic threshold in heart failure: LacS-001. Scientific Reports. 2024;14:18985.','10.1038/s41598-024-70001-9'],
    ['C09','Takemoto A, Okawara H, Sudo T, et al. A novel fatigue monitoring system using sweat lactate: a preliminary study. Fatigue. Online 2025; issue 2026;14:27–41.','10.1080/21641846.2025.2554557'],
    ['C10','Sawada T, Okawara H, Narushima S, et al. Aerobic Threshold Evaluation Using a Sweat Lactate Sensor in Healthy Women. IJSM. 2026;47:425–432.','10.1055/a-2771-5130'],
    ['C11','Sawada T, Okawara H, Minami K, et al. Validation of aerobic threshold assessment during arm crank exercise. Physiological Reports. 2026;14:e71002.','10.14814/phy2.71002']
  ];
  refs.forEach((r,i)=>{
    const y=1.18+i*0.86;
    pill(slide,r[0],0.67,y,0.58,i===2?C.orange:C.cyan,{fontFace:ENFONT,fontSize:8.4});
    text(slide,r[1],1.48,y-0.01,10.84,0.41,{fontFace:ENFONT,fontSize:9.5,color:C.text});
    link(slide,r[2],`https://doi.org/${r[2]}`,1.48,y+0.45,4.35);
  });
  card(slide,0.67,5.68,12.02,0.98,{fill:C.panel2,line:C.border});
  text(slide,'支援文章',0.92,5.96,1.18,0.20,{fontSize:10,bold:true,color:C.blue});
  text(slide,'S01 · PLOS ONE 2021 · 10.1371/journal.pone.0257549    |    S02 · Sensors 2022 · 10.3390/s22155473',2.25,5.95,9.95,0.21,{fontFace:ENFONT,fontSize:9.1,color:C.text});
  text(slide,'相鄰排除 X01 · EXERCISE-HF · 10.1016/j.conctc.2025.101522（無汗乳酸終點）',2.25,6.31,9.95,0.20,{fontFace:ENFONT,fontSize:8.8,color:C.muted});
  note(slide,'完整逐篇方法、限制、COI 與連結見 Markdown 報告及 CSV。');
}

// 30 CLOSE
{
  const slide = addSlide('結論：用 sLT 做個人趨勢；不要把汗濃度變成偽精準疲勞分數', 'DECISION');
  const cards = [
    ['01','證據核心','sLT／第一轉折在多場景可近似 LT1／VT1。',C.cyan],
    ['02','疲勞邊界','只有 n=17 與 n=18 兩篇直接研究，仍屬初步。',C.orange],
    ['03','產品原則','QC → 同流程 → 個人 baseline → MDC → 第二指標。',C.lime]
  ];
  cards.forEach((r,i)=>{
    const x=0.72+i*4.17;
    card(slide,x,1.50,3.80,2.65,{fill:C.panel2,line:r[3],lineWidth:1.3});
    pill(slide,r[0],x+0.25,1.80,0.62,r[3],{fontFace:ENFONT,fontSize:9});
    text(slide,r[1],x+0.25,2.39,3.30,0.35,{fontSize:18,bold:true,color:r[3],align:'center'});
    text(slide,r[2],x+0.34,3.10,3.12,0.55,{fontSize:11.5,color:C.text,align:'center'});
  });
  card(slide,1.02,4.74,11.28,1.24,{fill:C.panel,line:C.cyan});
  rich(slide,[
    {text:'推薦最終用語｜',options:{bold:true,color:C.cyan2}},
    {text:'「本次 sLT 相較個人同條件基準提早，超過量測誤差；可能代表恢復度降低，建議結合主觀疲勞與第二指標複核。」',options:{bold:true,color:C.white}}
  ],1.38,5.12,10.56,0.49,{fontSize:13.1,align:'center'});
  text(slide,'完整報告與可更新追蹤表已隨簡報交付  ·  Snapshot 2026-09-10',2.12,6.51,9.10,0.22,{fontFace:ENFONT,fontSize:9.4,color:C.muted,align:'center'});
  note(slide,'一句話：Grace 研究線支持 sLT 作為個人化轉折資訊；直接疲勞效度尚不足以支撐通用濃度或百分比分數。');
}

if (slideNo !== 30) throw new Error(`Expected 30 slides, got ${slideNo}`);

const out = path.resolve(__dirname, '..', 'downloads', 'grace_imaging_daisuke_nakashima_sweat_lactate_review_zhTW_2026-09-10.pptx');
fs.mkdirSync(path.dirname(out), { recursive: true });
pptx.writeFile({ fileName: out });
console.log(`Wrote ${out} (${slideNo} slides)`);

#!/usr/bin/env python3
"""scoring_ui.py — 轻量级人工评分 Web UI.

启动一个本地 HTTP 服务器，提供逐条展示 Q&A 对的评分界面。
支持快捷键打分、自动保存、过滤/搜索、查看原文。

用法:
    python3 scoring_ui.py                    # 默认端口 8787
    python3 scoring_ui.py --port 9000        # 指定端口
    python3 scoring_ui.py --domain AIOS架构   # 只展示该域

浏览器访问: http://localhost:8787
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

SCORED_FILE = Path("/vol1/1000/projects/ChatgptREST/scripts/evomap_qa/planning_qa_scored.jsonl")

# ---------------------------------------------------------------------------
# Data Layer
# ---------------------------------------------------------------------------

_records: list[dict] = []
_index_by_id: dict[str, int] = {}
_dirty = False


def load_records(domain_filter: str = "") -> None:
    global _records, _index_by_id
    _records = []
    _index_by_id = {}
    if not SCORED_FILE.exists():
        return
    for line in SCORED_FILE.read_text("utf-8").strip().split("\n"):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
            if domain_filter and rec.get("domain", "") != domain_filter:
                continue
            _records.append(rec)
            _index_by_id[rec["qa_id"]] = len(_records) - 1
        except (json.JSONDecodeError, KeyError):
            pass


def save_records() -> None:
    global _dirty
    if not _dirty:
        return
    # Re-read the full file, update only matching records, write back
    all_recs = []
    for line in SCORED_FILE.read_text("utf-8").strip().split("\n"):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
            qa_id = rec.get("qa_id", "")
            if qa_id in _index_by_id:
                rec = _records[_index_by_id[qa_id]]
            all_recs.append(rec)
        except json.JSONDecodeError:
            pass

    with open(SCORED_FILE, "w", encoding="utf-8") as f:
        for rec in all_recs:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    _dirty = False


def get_stats() -> dict:
    total = len(_records)
    scored = sum(1 for r in _records
                 if r.get("scores_human", {}).get("overall") is not None)
    domains = {}
    for r in _records:
        d = r.get("domain", "未知")
        domains[d] = domains.get(d, 0) + 1
    return {"total": total, "scored": scored, "remaining": total - scored,
            "domains": domains}


# ---------------------------------------------------------------------------
# HTML UI
# ---------------------------------------------------------------------------

HTML_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>EvoMap Q&A 评分台</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #0f1117;
    --surface: #1a1d27;
    --surface2: #242836;
    --accent: #6c5ce7;
    --accent-glow: rgba(108, 92, 231, 0.3);
    --gold: #f0b429;
    --green: #00b894;
    --red: #e17055;
    --text: #e8e8e8;
    --text2: #9ca3af;
    --border: #2d3148;
    --radius: 12px;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: 'Inter', -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
  }

  /* Top Bar */
  .topbar {
    display: flex; align-items: center; justify-content: space-between;
    padding: 12px 24px;
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    position: sticky; top: 0; z-index: 100;
  }
  .topbar h1 { font-size: 16px; font-weight: 600; color: var(--accent); }
  .topbar .stats { font-size: 13px; color: var(--text2); }
  .topbar .stats span { color: var(--green); font-weight: 600; }

  /* Progress Bar */
  .progress-bar {
    height: 3px; background: var(--border); width: 100%;
  }
  .progress-bar .fill {
    height: 100%; background: linear-gradient(90deg, var(--accent), var(--green));
    transition: width 0.3s ease;
  }

  /* Layout */
  .container {
    max-width: 1200px; margin: 0 auto; padding: 20px;
    display: grid; grid-template-columns: 1fr 340px; gap: 20px;
  }
  @media (max-width: 900px) { .container { grid-template-columns: 1fr; } }

  /* Card */
  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 20px;
  }

  /* Q&A Display */
  .qa-header {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 12px;
  }
  .qa-id { font-size: 11px; color: var(--text2); font-family: monospace; }
  .qa-domain {
    font-size: 11px; padding: 3px 8px; border-radius: 6px;
    background: var(--accent-glow); color: var(--accent); font-weight: 500;
  }
  .qa-meta {
    font-size: 12px; color: var(--text2); margin-bottom: 8px;
    display: flex; gap: 12px; flex-wrap: wrap;
  }
  .qa-meta .tag { padding: 2px 6px; background: var(--surface2); border-radius: 4px; }

  .section-label {
    font-size: 11px; font-weight: 600; text-transform: uppercase;
    color: var(--accent); letter-spacing: 1px; margin: 16px 0 6px;
  }
  .question-text {
    font-size: 14px; line-height: 1.7; color: var(--gold);
    padding: 12px; background: rgba(240,180,41,0.08);
    border-left: 3px solid var(--gold); border-radius: 0 8px 8px 0;
    max-height: 200px; overflow-y: auto; white-space: pre-wrap;
  }
  .answer-text {
    font-size: 13px; line-height: 1.7; color: var(--text);
    padding: 12px; background: var(--surface2);
    border-radius: 8px; max-height: 400px; overflow-y: auto;
    white-space: pre-wrap; word-break: break-word;
  }
  .view-full {
    display: inline-block; margin-top: 8px; font-size: 12px;
    color: var(--accent); cursor: pointer; text-decoration: underline;
  }

  /* Scoring Panel */
  .score-panel { position: sticky; top: 60px; }
  .score-panel h3 { font-size: 14px; margin-bottom: 16px; }

  .score-row {
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 14px;
  }
  .score-label {
    font-size: 13px; color: var(--text2); min-width: 80px;
  }
  .score-buttons {
    display: flex; gap: 6px;
  }
  .score-btn {
    width: 36px; height: 36px; border: 2px solid var(--border);
    border-radius: 8px; background: var(--surface2);
    color: var(--text); font-size: 14px; font-weight: 600;
    cursor: pointer; transition: all 0.15s;
    display: flex; align-items: center; justify-content: center;
  }
  .score-btn:hover { border-color: var(--accent); background: var(--accent-glow); }
  .score-btn.active {
    border-color: var(--accent); background: var(--accent);
    color: white; box-shadow: 0 0 12px var(--accent-glow);
  }
  .score-btn.active.s1 { background: var(--red); border-color: var(--red); }
  .score-btn.active.s2 { background: #e67e22; border-color: #e67e22; }
  .score-btn.active.s3 { background: #f0b429; border-color: #f0b429; color: #333; }
  .score-btn.active.s4 { background: #27ae60; border-color: #27ae60; }
  .score-btn.active.s5 { background: var(--green); border-color: var(--green); }

  .machine-ref {
    font-size: 11px; color: var(--text2); margin-left: 4px;
  }

  /* Comment */
  .comment-area {
    width: 100%; height: 60px; resize: vertical;
    background: var(--surface2); border: 1px solid var(--border);
    border-radius: 8px; padding: 8px; color: var(--text);
    font-size: 13px; font-family: inherit;
  }
  .comment-area:focus { outline: none; border-color: var(--accent); }

  /* Navigation */
  .nav-bar {
    display: flex; gap: 8px; margin-top: 16px;
  }
  .nav-btn {
    flex: 1; padding: 10px; border: none; border-radius: 8px;
    font-size: 13px; font-weight: 600; cursor: pointer;
    transition: all 0.15s;
  }
  .nav-btn.prev { background: var(--surface2); color: var(--text); }
  .nav-btn.next { background: var(--accent); color: white; }
  .nav-btn.skip { background: var(--surface2); color: var(--text2); }
  .nav-btn:hover { opacity: 0.85; transform: translateY(-1px); }

  .nav-counter {
    text-align: center; font-size: 12px; color: var(--text2); margin-top: 8px;
  }

  /* Filter */
  .filter-row {
    display: flex; gap: 8px; margin-bottom: 16px; align-items: center;
  }
  .filter-select {
    background: var(--surface2); border: 1px solid var(--border);
    color: var(--text); padding: 6px 10px; border-radius: 6px;
    font-size: 13px;
  }
  .filter-select:focus { outline: none; border-color: var(--accent); }

  /* Key hint */
  .key-hint {
    font-size: 11px; color: var(--text2); text-align: center;
    margin-top: 12px; line-height: 1.6;
  }
  .key-hint kbd {
    background: var(--surface2); padding: 2px 6px; border-radius: 4px;
    font-family: monospace; border: 1px solid var(--border);
  }

  /* Toast */
  .toast {
    position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
    background: var(--green); color: white; padding: 8px 20px;
    border-radius: 8px; font-size: 13px; font-weight: 500;
    opacity: 0; transition: opacity 0.3s; pointer-events: none;
    z-index: 999;
  }
  .toast.show { opacity: 1; }
</style>
</head>
<body>

<div class="topbar">
  <h1>🧠 EvoMap Q&A 评分台</h1>
  <div class="stats">
    已评 <span id="stat-scored">0</span> / <span id="stat-total">0</span>
    &nbsp;|&nbsp; 剩余 <span id="stat-remaining" style="color: var(--gold);">0</span>
  </div>
</div>
<div class="progress-bar"><div class="fill" id="progress-fill" style="width: 0%"></div></div>

<div class="container">
  <!-- Left: Q&A Content -->
  <div>
    <div class="filter-row">
      <select class="filter-select" id="filter-domain" onchange="applyFilter()">
        <option value="">全部域</option>
      </select>
      <select class="filter-select" id="filter-status" onchange="applyFilter()">
        <option value="">全部状态</option>
        <option value="unscored">未评分</option>
        <option value="scored">已评分</option>
      </select>
      <select class="filter-select" id="filter-type" onchange="applyFilter()">
        <option value="">全部类型</option>
        <option value="conversational">对话式</option>
        <option value="research_report">调研报告</option>
        <option value="plan_document">方案文档</option>
        <option value="tool_script">脚本工具</option>
      </select>
    </div>

    <div class="card" id="qa-card">
      <div class="qa-header">
        <span class="qa-id" id="qa-id">—</span>
        <span class="qa-domain" id="qa-domain">—</span>
      </div>
      <div class="qa-meta">
        <span class="tag" id="qa-type">—</span>
        <span class="tag" id="qa-route">—</span>
        <span class="tag" id="qa-file">—</span>
        <span class="tag" id="qa-gate" style="font-weight:600;">—</span>
      </div>

      <div class="section-label">❓ 问题</div>
      <div class="question-text" id="qa-question">加载中...</div>

      <div class="section-label">💡 答案</div>
      <div class="answer-text" id="qa-answer">加载中...</div>
      <span class="view-full" id="view-full-btn" onclick="viewFull()">📄 查看原文</span>
    </div>
  </div>

  <!-- Right: Scoring Panel -->
  <div class="score-panel card">
    <h3>📊 评分 <span style="font-size: 11px; color: var(--text2); font-weight: 400;">1=无效 5=优秀</span></h3>

    <div class="score-row">
      <span class="score-label">清晰度 <span class="machine-ref" id="ref-clarity"></span></span>
      <div class="score-buttons" id="score-clarity"></div>
    </div>
    <div class="score-row">
      <span class="score-label">正确性 <span class="machine-ref" id="ref-correctness"></span></span>
      <div class="score-buttons" id="score-correctness"></div>
    </div>
    <div class="score-row">
      <span class="score-label">证据 <span class="machine-ref" id="ref-evidence"></span></span>
      <div class="score-buttons" id="score-evidence"></div>
    </div>
    <div class="score-row">
      <span class="score-label">可执行 <span class="machine-ref" id="ref-actionability"></span></span>
      <div class="score-buttons" id="score-actionability"></div>
    </div>
    <div class="score-row">
      <span class="score-label">风险 <span class="machine-ref" id="ref-risk"></span></span>
      <div class="score-buttons" id="score-risk"></div>
    </div>
    <div class="score-row">
      <span class="score-label">对齐 <span class="machine-ref" id="ref-alignment"></span></span>
      <div class="score-buttons" id="score-alignment"></div>
    </div>
    <div class="score-row">
      <span class="score-label">完整度 <span class="machine-ref" id="ref-completeness"></span></span>
      <div class="score-buttons" id="score-completeness"></div>
    </div>

    <hr style="border-color: var(--border); margin: 12px 0;">

    <div class="score-row">
      <span class="score-label" style="font-weight:600; color:var(--gold);">总分</span>
      <div class="score-buttons" id="score-overall"></div>
    </div>

    <div class="section-label" style="margin-top: 12px;">💬 评语</div>
    <textarea class="comment-area" id="comment" placeholder="可选"></textarea>

    <div class="nav-bar">
      <button class="nav-btn prev" onclick="navigate(-1)">← 上一条</button>
      <button class="nav-btn skip" onclick="navigate(1)">跳过</button>
      <button class="nav-btn next" onclick="submitAndNext()">保存 & 下一条 →</button>
    </div>

    <div class="nav-counter" id="nav-counter">0 / 0</div>

    <div class="key-hint">
      快捷键: <kbd>1</kbd>-<kbd>5</kbd> 总分 &nbsp;
      <kbd>←</kbd> 上一条 &nbsp; <kbd>→</kbd> 下一条 &nbsp;
      <kbd>Enter</kbd> 保存&下一条
    </div>
  </div>
</div>

<div class="toast" id="toast">✅ 已保存</div>

<script>
let records = [];
let filteredIndices = [];
let currentPos = 0;
const DIMS = ['clarity','correctness','evidence','actionability','risk','alignment','completeness','overall'];
const DIM_LABELS = {clarity:'清晰度',correctness:'正确性',evidence:'证据',actionability:'可执行',risk:'风险',alignment:'对齐',completeness:'完整度',overall:'总分'};
let currentScores = {};

// Init score buttons
DIMS.forEach(dim => {
  const container = document.getElementById('score-' + dim);
  for (let v = 1; v <= 5; v++) {
    const btn = document.createElement('button');
    btn.className = 'score-btn';
    btn.textContent = v;
    btn.dataset.dim = dim;
    btn.dataset.val = v;
    btn.onclick = () => setScore(dim, v);
    container.appendChild(btn);
  }
});

async function loadData() {
  const resp = await fetch('/api/records');
  const data = await resp.json();
  records = data.records;
  updateStats(data.stats);
  populateFilters();
  applyFilter();
}

function updateStats(stats) {
  document.getElementById('stat-scored').textContent = stats.scored;
  document.getElementById('stat-total').textContent = stats.total;
  document.getElementById('stat-remaining').textContent = stats.remaining;
  const pct = stats.total > 0 ? (stats.scored / stats.total * 100) : 0;
  document.getElementById('progress-fill').style.width = pct + '%';
}

function populateFilters() {
  const domains = new Set(records.map(r => r.domain));
  const sel = document.getElementById('filter-domain');
  domains.forEach(d => {
    const opt = document.createElement('option');
    opt.value = d; opt.textContent = d;
    sel.appendChild(opt);
  });
}

function applyFilter() {
  const domain = document.getElementById('filter-domain').value;
  const status = document.getElementById('filter-status').value;
  const type = document.getElementById('filter-type').value;

  filteredIndices = [];
  records.forEach((r, i) => {
    if (domain && r.domain !== domain) return;
    if (type && r.source_type !== type) return;
    if (status === 'unscored' && r.scores_human?.overall != null) return;
    if (status === 'scored' && r.scores_human?.overall == null) return;
    filteredIndices.push(i);
  });
  currentPos = 0;
  showCurrent();
}

function showCurrent() {
  if (filteredIndices.length === 0) {
    document.getElementById('qa-question').textContent = '没有匹配的记录';
    document.getElementById('qa-answer').textContent = '';
    document.getElementById('nav-counter').textContent = '0 / 0';
    return;
  }
  const idx = filteredIndices[currentPos];
  const r = records[idx];

  document.getElementById('qa-id').textContent = r.qa_id;
  document.getElementById('qa-domain').textContent = r.domain;
  document.getElementById('qa-type').textContent = r.source_type;
  document.getElementById('qa-route').textContent = '路由: ' + (r.route_auto || '—');
  document.getElementById('qa-file').textContent = r.source_file?.split('/').slice(-1)[0] || '';
  document.getElementById('qa-question').textContent = r.question;
  document.getElementById('qa-answer').textContent = r.answer_summary;
  document.getElementById('view-full-btn').dataset.path = r.answer_full_path || '';
  document.getElementById('nav-counter').textContent = (currentPos + 1) + ' / ' + filteredIndices.length;

  // Show gate status
  const gate = r.gate || {};
  const gateEl = document.getElementById('qa-gate');
  if (gate.is_valid_qa === false) {
    gateEl.textContent = '❌ 无效QA';
    gateEl.style.color = 'var(--red)';
  } else if (gate.has_reuse_value === false) {
    gateEl.textContent = '📦 已归档';
    gateEl.style.color = 'var(--gold)';
  } else {
    gateEl.textContent = '✅ 有效';
    gateEl.style.color = 'var(--green)';
  }

  // Show machine reference scores
  const rubric = r.rubric_auto || {};
  ['clarity','correctness','evidence','actionability','risk','alignment','completeness'].forEach(d => {
    const ref = document.getElementById('ref-' + d);
    const val = rubric[d];
    if (val != null) {
      ref.textContent = '(机器: ' + (1 + val * 4).toFixed(1) + ')';
    } else {
      ref.textContent = '';
    }
  });

  // Restore existing scores
  currentScores = {};
  DIMS.forEach(dim => {
    const existing = r.scores_human?.[dim];
    if (existing != null) {
      currentScores[dim] = existing;
    }
    updateScoreButtons(dim);
  });
  document.getElementById('comment').value = r.scores_human?.comment || '';
}

function setScore(dim, val) {
  currentScores[dim] = val;
  updateScoreButtons(dim);
}

function updateScoreButtons(dim) {
  const container = document.getElementById('score-' + dim);
  const btns = container.querySelectorAll('.score-btn');
  btns.forEach(btn => {
    const v = parseInt(btn.dataset.val);
    btn.classList.remove('active', 's1', 's2', 's3', 's4', 's5');
    if (currentScores[dim] === v) {
      btn.classList.add('active', 's' + v);
    }
  });
}

async function submitAndNext() {
  if (filteredIndices.length === 0) return;
  const idx = filteredIndices[currentPos];
  const qa_id = records[idx].qa_id;

  const scores = {};
  DIMS.forEach(d => { scores[d] = currentScores[d] || null; });
  scores.comment = document.getElementById('comment').value;

  const resp = await fetch('/api/score', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({qa_id, scores})
  });
  const result = await resp.json();

  // Update local record
  records[idx].scores_human = scores;
  records[idx].status = scores.overall ? 'scored' : records[idx].status;
  updateStats(result.stats);

  showToast();
  navigate(1);
}

function navigate(delta) {
  if (filteredIndices.length === 0) return;
  currentPos = Math.max(0, Math.min(filteredIndices.length - 1, currentPos + delta));
  showCurrent();
}

function viewFull() {
  const path = document.getElementById('view-full-btn').dataset.path;
  if (path) {
    window.open('/api/file?path=' + encodeURIComponent(path), '_blank');
  }
}

function showToast() {
  const t = document.getElementById('toast');
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 1500);
}

// Keyboard shortcuts
document.addEventListener('keydown', e => {
  if (e.target.tagName === 'TEXTAREA') return;
  if (e.key >= '1' && e.key <= '5') {
    setScore('overall', parseInt(e.key));
  } else if (e.key === 'ArrowLeft') {
    navigate(-1);
  } else if (e.key === 'ArrowRight') {
    navigate(1);
  } else if (e.key === 'Enter') {
    submitAndNext();
  }
});

loadData();
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# HTTP Handler
# ---------------------------------------------------------------------------

class ScoringHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress default logs

    def _json_response(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html_response(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _text_response(self, text: str) -> None:
        body = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/" or parsed.path == "":
            self._html_response(HTML_PAGE)
            return

        if parsed.path == "/api/records":
            recs_out = []
            for r in _records:
                recs_out.append({
                    "qa_id": r.get("qa_id", ""),
                    "domain": r.get("domain", ""),
                    "source_type": r.get("source_type", ""),
                    "source_file": r.get("source_file", ""),
                    "question": r.get("question", ""),
                    "answer_summary": r.get("answer_summary", ""),
                    "answer_full_path": r.get("answer_full_path", ""),
                    "route_auto": r.get("route_auto", ""),
                    "rubric_auto": r.get("rubric_auto", {}),
                    "gate": r.get("gate", {}),
                    "scores_human": r.get("scores_human", {}),
                    "status": r.get("status", ""),
                })
            self._json_response({"records": recs_out, "stats": get_stats()})
            return

        if parsed.path == "/api/file":
            qs = parse_qs(parsed.query)
            fpath = qs.get("path", [""])[0]
            if fpath and os.path.isfile(fpath):
                try:
                    text = Path(fpath).read_text("utf-8", errors="replace")
                    self._text_response(text)
                except Exception as e:
                    self._text_response(f"Error: {e}")
            else:
                self._text_response("File not found")
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        if self.path == "/api/score":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            data = json.loads(body)

            qa_id = data.get("qa_id", "")
            scores = data.get("scores", {})

            global _dirty
            if qa_id in _index_by_id:
                idx = _index_by_id[qa_id]
                _records[idx]["scores_human"] = scores
                _records[idx]["human_scorer"] = "manual_ui"
                _records[idx]["human_scored_at"] = datetime.now(timezone.utc).isoformat()
                if scores.get("overall") is not None:
                    _records[idx]["status"] = "scored"
                _dirty = True
                # Auto-save every 5 scores
                scored_count = sum(1 for r in _records
                                   if r.get("scores_human", {}).get("overall") is not None)
                if scored_count % 5 == 0:
                    save_records()

            self._json_response({"ok": True, "stats": get_stats()})
            return

        self.send_response(404)
        self.end_headers()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Q&A Scoring UI")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--domain", type=str, default="")
    args = parser.parse_args()

    print(f"Loading records from {SCORED_FILE}...")
    load_records(args.domain)
    stats = get_stats()
    print(f"  Total: {stats['total']}, Scored: {stats['scored']}, Remaining: {stats['remaining']}")

    server = HTTPServer(("0.0.0.0", args.port), ScoringHandler)
    print(f"\n🧠 EvoMap Scoring UI running at:")
    print(f"   http://localhost:{args.port}")
    print(f"\n   Press Ctrl+C to stop (scores auto-saved)\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nSaving final scores...")
        save_records()
        print("Done.")
        server.server_close()


if __name__ == "__main__":
    main()

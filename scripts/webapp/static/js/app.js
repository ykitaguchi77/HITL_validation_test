/* App orchestrator: blind annotator/session flow, practice GT calibration, submit.
 * Model identity is never shown (blinding). Sessions run in order:
 * 練習 -> Scratch -> Session 1..8; completion persisted in localStorage. */
(function (HITL) {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const api = async (url, opts) => {
    const r = await fetch(url, opts);
    if (!r.ok) throw new Error(`${url} -> ${r.status} ${await r.text()}`);
    return r.json();
  };
  const pad2 = (n) => String(n).padStart(2, "0");

  class App {
    constructor() {
      this.config = null;
      this.classByKey = {};
      this.run = null;           // {annotator, sessions:[...]}
      this.sessionData = null;   // {key,label,is_hitl,is_practice,images:[...]}
      this.sessionKey = null; this.isHitl = false; this.isPractice = false;
      this.idx = 0;
      this.active = "eyelid";
      this.currentInitial = null;
      this.sessionId = null;
      this.annotator = "";
      this.view = null; this.metrics = null; this.tools = null;
      this._timer = null; this._reviewing = false; this._gtNodes = null;
      this._timing = false;   // an image is actively being timed (not paused/finished)
      this._paused = false;   // timing paused because the window lost focus
      this._hbTimer = null;   // heartbeat interval
      this._confirming = false;   // pre-submit confirmation screen is showing
      this._starting = false;     // a startSession is in progress (blocks re-entry)
      this._loadSeq = 0;          // loadCurrent generation (stale loads bail before render)
    }

    async init() {
      this.config = await api("/api/config");
      this.config.classes.forEach((c) => (this.classByKey[c.key] = c));
      const asel = $("annotator-select");
      this.config.annotators.forEach((a) => {
        const o = document.createElement("option");
        o.value = a;
        o.textContent = a === "test" ? "練習用（本番に含めない）" : a;
        asel.appendChild(o);
      });
      asel.onchange = () => this._loadRun();

      // Pause timing + metrics whenever the window is hidden or loses focus (the
      // annotator opened another window), and resume on return. Covers tab switch,
      // minimize (visibilitychange) and other-app focus (blur/focus).
      document.addEventListener("visibilitychange", () =>
        document.hidden ? this._pauseTiming() : this._resumeTiming());
      window.addEventListener("blur", () => this._pauseTiming());
      window.addEventListener("focus", () => this._resumeTiming());

      await this._loadRun();
    }

    /* ---- setup: annotator -> session list ---- */
    async _loadRun() {
      this.annotator = $("annotator-select").value;
      this.run = await api(`/api/run/${this.annotator}`);
      this._renderSessionList();
    }

    _doneKey() { return `hitl_done_${this.annotator}`; }
    _doneSet() {
      try { return new Set(JSON.parse(localStorage.getItem(this._doneKey()) || "[]")); }
      catch (e) { return new Set(); }
    }
    _markDone(key) {
      const s = this._doneSet(); s.add(key);
      localStorage.setItem(this._doneKey(), JSON.stringify([...s]));
    }
    // completed-attempt counter per session (so redo = next attempt; recorded in data)
    _attemptsKey() { return `hitl_attempts_${this.annotator}`; }
    _attempts() {
      try { return JSON.parse(localStorage.getItem(this._attemptsKey()) || "{}"); }
      catch (e) { return {}; }
    }
    _attemptCount(key) { return this._attempts()[key] || 0; }
    _incAttempt(key) {
      const a = this._attempts(); a[key] = (a[key] || 0) + 1;
      localStorage.setItem(this._attemptsKey(), JSON.stringify(a));
    }

    _renderSessionList() {
      const done = this._doneSet();
      const wrap = $("session-list"); wrap.innerHTML = "";
      const sessions = this.run.sessions;
      // practice is always re-runnable; real sessions unlock only after both practice
      // sessions are done at least once, then proceed strictly in order.
      const allPracticeDone = sessions.filter((s) => s.is_practice).every((s) => done.has(s.key));
      const nextReal = sessions.find((s) => !s.is_practice && !done.has(s.key));
      const nextRealKey = nextReal ? nextReal.key : null;
      const isEnabled = (s) => {
        if (s.is_practice) return true;                 // practice: always re-runnable
        if (done.has(s.key)) return true;               // completed real session: clickable to redo (confirm)
        return allPracticeDone && s.key === nextRealKey; // next undone real session, in order
      };
      const nextHighlight = sessions.find((s) => isEnabled(s) && !done.has(s.key));
      sessions.forEach((s) => {
        const isDone = done.has(s.key);
        const btn = document.createElement("button");
        btn.className = "session-btn" + (isDone ? " done" : "")
          + (s === nextHighlight ? " next" : "");
        btn.textContent = `${isDone ? "✓ " : ""}${s.label}  (${s.n_images}枚)`;
        btn.disabled = !isEnabled(s);
        btn.onclick = () => this.startSession(s);
        wrap.appendChild(btn);
      });
      if (allPracticeDone && !nextRealKey) {
        const p = document.createElement("p");
        p.className = "muted"; p.textContent = "本番の全セッション完了 🎉（練習は再実行可）";
        wrap.appendChild(p);
      }
    }

    /* ---- session ---- */
    async startSession(s) {
      // guard against a rapid second click while /api/session is in flight: two
      // concurrent startSession -> two loadCurrent -> the prefill rendered TWICE
      // (2 shapes per class). Re-entrancy guard + hiding the list both prevent it.
      if (this._starting) return;
      const completed = this._attemptCount(s.key);
      const attempt = completed + 1;   // this run's attempt number (1 = first)
      if (this._doneSet().has(s.key) && !s.is_practice) {
        if (!confirm(`「${s.label}」は完了済みです（${completed}回完了）。\nやり直しますか？\n`
          + `これは ${attempt} 回目の試行として新たに記録されます（前回の記録は残ります）。`)) return;
      }
      this._starting = true;
      $("setup").classList.add("hidden");   // hide the session list at once (no 2nd click)
      $("app").classList.remove("hidden");
      try {
      this.attempt = attempt;
      this.sessionKey = s.key; this.isHitl = s.is_hitl; this.isPractice = !!s.is_practice;
      const ts = new Date();
      const stamp = `${ts.getFullYear()}${pad2(ts.getMonth() + 1)}${pad2(ts.getDate())}-${pad2(ts.getHours())}${pad2(ts.getMinutes())}${pad2(ts.getSeconds())}`;
      this.sessionId = `${this.annotator}_${s.key}_a${attempt}_${stamp}`;
      this.sessionData = await api(`/api/session/${this.annotator}/${s.key}`);
      this.idx = 0; this._reviewing = false;

      $("phase-label").textContent = s.label + (attempt > 1 ? `（${attempt}回目）` : "");
      $("hitl-note").textContent = this.isPractice
        ? "練習: 提出後に正解(GT)を点線表示します（解析対象外）"
        : (this.isHitl ? "予測を修正中（モデルは非表示）" : "Scratch: ゼロから作成");
      $("submit-btn").textContent = "提出して次へ →";

      // create canvas/tools/metrics once, then reuse across sessions (avoids dup listeners)
      if (!this.view) {
        this.view = new HITL.CanvasView("canvas");
        this.metrics = new HITL.Metrics();
        this.view.metrics = this.metrics;
        this.tools = new HITL.ToolController(this.view, this.metrics, this);
        this._buildSidebar();
        this._bindToolbar();
      }
      await this.loadCurrent();
      } finally {
        this._starting = false;
      }
    }

    /* ---- image flow ---- */
    async loadCurrent() {
      const seq = ++this._loadSeq;   // any newer loadCurrent supersedes this one
      const img = this.sessionData.images[this.idx];
      $("progress").textContent = `${this.idx + 1} / ${this.sessionData.images.length}`;
      // block input + hide the image until the prefill is ready (no mid-input pop-in)
      this._setLoading(true, this.isHitl ? "推論中… しばらくお待ちください" : "読み込み中…");
      this._confirming = false; this._setConfirmOverlay(false);
      $("submit-btn").textContent = "提出して次へ →"; $("revise-btn").classList.add("hidden");
      this._clearGT();
      await this.view.loadImage(img.url, img.width, img.height);
      if (seq !== this._loadSeq) return;   // a newer load started; don't render this one

      this.currentInitial = null;
      if (this.isHitl) {   // practice + HITL have a prefill; scratch does not
        const res = await api("/api/predict", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ annotator: this.annotator, session_key: this.sessionKey,
            image_id: img.image_id }),
        });
        if (seq !== this._loadSeq) return;   // superseded during inference -> skip render
        this.currentInitial = res.initial;
        this._renderInitial(res.initial);
      }
      this.tools.pushInitial();
      this.tools.setTool(this.isHitl ? "select" : "polygon");
      this.setActiveClass("eyelid");
      // start effort timing ONLY now (after image+prefill ready) so inference/load
      // latency is not counted as annotation time
      this.metrics.reset();
      this._setLoading(false);
      this._paused = false;
      this._timing = true;
      this._startTimer();
      $("status").textContent = "";
      this.onChange();
    }

    _setLoading(on, text) {
      const o = $("loading-overlay");
      if (!o) return;
      if (on) { o.textContent = text || "読み込み中…"; o.classList.remove("hidden"); }
      else { o.classList.add("hidden"); }
    }

    _renderInitial(initial) {
      this.config.classes.forEach((c) => {
        (initial[c.key] || []).forEach((d) => {
          if (c.kind === "polygon") this.view.addPolygon(c.key, c.color, d);
          else this.view.addEllipse(c.key, c.color, d);
        });
      });
      this.view.layer.batchDraw();
    }

    // Topbar 提出: on a fresh image open the confirmation state; while confirming,
    // the same button acts as 確認OK (it is relabeled "確認OK・次へ →").
    submit() {
      if (this._confirming) { this._confirmOk(); return; }
      // all 3 classes must be present before a submission is allowed
      const missing = this._missingClasses();
      if (missing.length) {
        alert(`未入力のクラスがあります: ${missing.map((c) => c.name).join("・")}\n`
          + "3クラス（まぶた・虹彩・瞳孔）すべてを描いてから提出してください。");
        return;
      }
      // 提出 -> 確認. Deselect everything so the review shows clean outlines (no
      // anchors/highlights). Pause timing (review/rating time is not counted). The
      // top-right buttons become 確認OK / 修正 / 中断. For practice, show the GT here.
      this.tools.deselect();
      this.metrics.pause();
      this._stopTimer();
      this._timing = false;
      this._confirming = true;
      this._setConfirmOverlay(true);
      $("submit-btn").textContent = "確認OK・次へ →";
      $("revise-btn").classList.remove("hidden");
      if (this.isPractice) this._showPracticeGT();
    }

    // class metas that have no shape yet (submission requires all 3)
    _missingClasses() {
      const present = new Set(this.view.shapes.map((s) => s.classKey));
      return this.config.classes.filter((c) => !present.has(c.key));
    }

    _setConfirmOverlay(on) {
      const o = $("confirm-overlay");
      if (o) o.classList.toggle("hidden", !on);
    }
    _exitConfirm() {
      this._confirming = false;
      this._setConfirmOverlay(false);
      this._clearGT();
      $("submit-btn").textContent = "提出して次へ →";
      $("revise-btn").classList.add("hidden");
    }
    _confirmOk() {
      if (!this._confirming) return;
      this._exitConfirm();
      this._finalizeSubmit();
    }
    _confirmEdit() {   // back to editing this image; timing resumes where it paused
      if (!this._confirming) return;
      this._exitConfirm();
      this.metrics.resume(); this._paused = false;
      this._timing = true; this._startTimer();
    }
    _confirmAbort() {
      if (!this._confirming) return;
      this.abort();   // abort() clears the confirm state
    }

    // practice only: show the merged GT outline + Dice on the confirmation screen
    // (dry-run — nothing is saved), so a separate GT-review step is not needed.
    async _showPracticeGT() {
      try {
        const img = this.sessionData.images[this.idx];
        const annotation = this.view.getAnnotation();
        const res = await api("/api/practice_gt", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ annotator: this.annotator, session_key: this.sessionKey,
            image_id: img.image_id, annotation }),
        });
        if (!this._confirming) return;   // user already left the confirmation
        this._showGT(res.gt);
        const per = res.scores ? Object.entries(res.scores)
          .map(([k, v]) => `${k} ${v}`).join("  ") : "";
        $("status").textContent = `正解(GT)=点線  mean Dice ${res.mean_dice}  [${per}]`;
      } catch (e) { /* GT display is best-effort */ }
    }

    // 確認OK -> 苦痛の記録(Paas) -> save. Metrics stay paused since 提出, so the
    // duration reflects work up to 提出 and excludes confirmation/rating time.
    async _finalizeSubmit() {
      const img = this.sessionData.images[this.idx];
      const annotation = this.view.getAnnotation();
      const metrics = this.metrics.snapshot();   // duration frozen at 提出 (paused)
      const effort = await this._askEffort();    // Paas 1-9, after the confirmation
      $("status").textContent = "保存中…";
      await api("/api/submit", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: this.sessionId, annotator: this.annotator,
          session_key: this.sessionKey, image_id: img.image_id, attempt: this.attempt,
          annotation, initial: this.currentInitial, metrics, effort }),
      });
      $("status").textContent = "保存完了";
      this._advance();
    }

    // Single-item Paas mental-effort rating (1-9). Resolves when a button is
    // clicked. Shown after the timer stops so it never inflates duration.
    _askEffort() {
      return new Promise((resolve) => {
        const ov = $("effort-overlay"), wrap = $("effort-scale");
        wrap.innerHTML = "";
        for (let i = 1; i <= 9; i++) {
          const b = document.createElement("button");
          b.className = "effort-btn"; b.textContent = i;
          b.onclick = () => { ov.classList.add("hidden"); resolve(i); };
          wrap.appendChild(b);
        }
        ov.classList.remove("hidden");
      });
    }

    _advance() {
      this.idx += 1;
      if (this.idx >= this.sessionData.images.length) { this._finishSession(); return; }
      this.loadCurrent();
    }

    _finishSession() {
      this._stopTimer();
      this._timing = false;
      this._clearGT();
      this._incAttempt(this.sessionKey);   // count this completed attempt
      this._markDone(this.sessionKey);
      $("app").classList.add("hidden");
      $("setup").classList.remove("hidden");
      $("phase-desc").textContent = `「${$("phase-label").textContent}」完了。次のセッションを選んでください。`;
      this._loadRun();   // refresh list with updated completion
    }

    // Fallback for when a session cannot be continued (time, etc.): discard this
    // session's partial records on the server and return to the menu WITHOUT marking
    // it done, so it is redone cleanly from the start.
    async abort() {
      if (!confirm("このセッションを中断しますか？\nこのセッションの記録は破棄され、最初からやり直しになります。")) return;
      this._exitConfirm();
      this._stopTimer(); this._timing = false; this._reviewing = false;
      try {
        await api("/api/abort", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: this.sessionId }) });
      } catch (e) { /* ignore */ }
      $("app").classList.add("hidden");
      $("setup").classList.remove("hidden");
      $("phase-desc").textContent = "セッションを中断しました（記録は破棄）。同じセッションを最初からやり直せます。";
      this._loadRun();
    }

    /* ---- practice GT overlay (read-only, distinct dashed style) ---- */
    _showGT(gt) {
      this._clearGT();
      this._gtNodes = [];
      const s = this.view.scale;
      for (const key of this.config.classes.map((c) => c.key)) {
        const m = this.classByKey[key]; if (!m) continue;
        (gt[key] || []).forEach((d) => {
          let node;
          if (m.kind === "polygon") {
            const flat = []; d.forEach((p) => flat.push(p[0], p[1]));
            node = new Konva.Line({ points: flat, closed: true, stroke: m.color,
              strokeWidth: 3 / s, dash: [12 / s, 7 / s], listening: false });
          } else {
            node = new Konva.Ellipse({ x: d.cx, y: d.cy, radiusX: d.rx, radiusY: d.ry,
              rotation: d.rotation || 0, stroke: m.color, strokeWidth: 3 / s,
              dash: [12 / s, 7 / s], listening: false });
          }
          this.view.world.add(node); this._gtNodes.push(node);
        });
      }
      this.view.layer.batchDraw();
    }
    _clearGT() {
      if (this._gtNodes) { this._gtNodes.forEach((n) => n.destroy()); this._gtNodes = null;
        if (this.view) this.view.layer.batchDraw(); }
    }

    /* ---- sidebar / UI ---- */
    _buildSidebar() {
      const ul = $("class-list"); ul.innerHTML = "";
      this.config.classes.forEach((c) => {
        const li = document.createElement("li");
        li.className = "class-item"; li.dataset.key = c.key;
        li.innerHTML =
          `<span class="swatch" style="background:${c.color}"></span>
           <span class="name">${c.name}</span>
           <span class="kind">${c.kind === "polygon" ? "多角形" : "楕円"}</span>
           <span class="count">0</span>
           <span class="vis" title="表示切替">👁</span>`;
        li.onclick = (e) => {
          if (e.target.classList.contains("vis")) { this._toggleVis(c.key, e.target); return; }
          this.setActiveClass(c.key);
          const existing = this.view.shapesOf(c.key);
          if (existing.length) { this.tools.setTool("select"); this.tools.select(existing[0]); }
          else { this.tools.setTool(c.kind === "polygon" ? "polygon" : "ellipse"); this.tools.deselect(); }
        };
        ul.appendChild(li);
      });
    }

    _toggleVis(key, el) {
      const on = el.style.opacity !== "0.3";
      this.view.shapesOf(key).forEach((s) => s.group.visible(!on));
      el.style.opacity = on ? "0.3" : "0.8";
      this.view.layer.batchDraw();
    }

    setActiveClass(key) {
      this.active = key;
      this.metrics.setActiveClass(key);
      document.querySelectorAll(".class-item").forEach((li) =>
        li.classList.toggle("active", li.dataset.key === key));
    }

    _bindToolbar() {
      document.querySelectorAll("#toolbar .tool").forEach((b) =>
        (b.onclick = () => this.tools.setTool(b.dataset.tool)));
      $("undo").onclick = () => this.tools.undo();
      $("redo").onclick = () => this.tools.redo();
      $("delete").onclick = () => this.tools.deleteSelected();
      $("fit").onclick = () => this.view.fit();
      $("maximize").onclick = () => this.view.maximize();
      const fillBtn = $("fill");
      fillBtn.classList.toggle("active", this.view.showFill);
      fillBtn.onclick = () => {
        this.view.setShowFill(!this.view.showFill);
        fillBtn.classList.toggle("active", this.view.showFill);
      };
      // brightness / contrast sliders (global image display; persist across images)
      const br = $("brightness"), ct = $("contrast"), bv = $("brightness-val"), cv = $("contrast-val");
      const applyBr = () => { bv.textContent = br.value; this.view.setBrightness(+br.value / 100); };
      const applyCt = () => { cv.textContent = ct.value; this.view.setContrast(+ct.value); };
      br.oninput = applyBr; ct.oninput = applyCt;
      $("reset-adjust").onclick = () => { br.value = 0; ct.value = 0; applyBr(); applyCt(); };
      $("submit-btn").onclick = () => this.submit();
      $("revise-btn").onclick = () => this._confirmEdit();
      $("abort-btn").onclick = () => this.abort();
    }

    onChange() {
      const counts = {};
      this.view.shapes.forEach((s) => (counts[s.classKey] = (counts[s.classKey] || 0) + 1));
      document.querySelectorAll(".class-item").forEach((li) => {
        li.querySelector(".count").textContent = counts[li.dataset.key] || 0;
      });
      this._renderMetrics();
    }

    setHint(t) { $("hint").textContent = t; }
    classMeta(key) { return this.classByKey[key]; }
    activeClass() { return this.active; }

    /* ---- timer / live metrics ---- */
    _startTimer() {
      this._stopTimer();
      this._timer = setInterval(() => {
        const sec = Math.floor(this.metrics._elapsedMs() / 1000);   // active time only
        $("timer").textContent = `${pad2(Math.floor(sec / 60))}:${pad2(sec % 60)}`;
        this._renderMetrics();
      }, 500);
      this._hbTimer = setInterval(() => this.metrics.heartbeat(), 15000);  // away-from-desk audit
    }
    _stopTimer() {
      if (this._timer) clearInterval(this._timer); this._timer = null;
      if (this._hbTimer) clearInterval(this._hbTimer); this._hbTimer = null;
    }

    // pause/resume the active-time clock + metrics on window focus loss/gain
    _pauseTiming() {
      if (!this._timing || this._paused) return;
      this._paused = true;
      this.metrics.pause();
      this._stopTimer();                 // freeze the visible timer + heartbeats
      this._setPauseOverlay(true);
    }
    _resumeTiming() {
      if (!this._timing || !this._paused) return;
      if (document.hidden || !document.hasFocus()) return;   // still not fully active
      this._paused = false;
      this.metrics.resume();
      this._startTimer();
      this._setPauseOverlay(false);
    }
    _setPauseOverlay(on) {
      const o = $("pause-overlay");
      if (o) o.classList.toggle("hidden", !on);
    }

    _renderMetrics() {
      const m = this.metrics;
      const rows = [
        ["クリック", m.total_clicks],
        ["マウス移動(px)", Math.round(m.mouse_distance_px)],
        ["頂点 追加/移動/削除", `${m.vertices_added}/${m.vertices_moved}/${m.vertices_deleted}`],
        ["図形 作成/削除", `${m.shapes_created}/${m.shapes_deleted}`],
        ["undo/redo", `${m.undo_count}/${m.redo_count}`],
        ["zoom/pan", `${m.zoom_count}/${m.pan_count}`],
      ];
      $("metrics-table").innerHTML = rows.map(
        (r) => `<tr><td>${r[0]}</td><td>${r[1]}</td></tr>`).join("");
    }
  }

  window.addEventListener("DOMContentLoaded", () => {
    const app = new App();
    HITL.app = app;   // debug/test hook
    app.init().catch((e) => { alert("初期化エラー: " + e.message); console.error(e); });
  });
})(window.HITL = window.HITL || {});

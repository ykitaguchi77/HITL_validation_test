/* Tool controller: tool switching, drawing polygons / OBB ellipses, selection,
 * pan/zoom, undo-redo history, and keyboard shortcuts.
 * `app` must provide: activeClass(), classMeta(key)->{color,kind,name},
 *                     setHint(str), onChange().
 */
(function (HITL) {
  "use strict";

  const CLOSE_PX = 10; // screen px to first vertex to close a polygon

  // distance from point p={x,y} to segment a-b ([x,y]) in image coords
  function segDist(p, a, b) {
    const vx = b[0] - a[0], vy = b[1] - a[1];
    const len2 = vx * vx + vy * vy;
    let t = len2 ? ((p.x - a[0]) * vx + (p.y - a[1]) * vy) / len2 : 0;
    t = Math.max(0, Math.min(1, t));
    return Math.hypot(p.x - (a[0] + t * vx), p.y - (a[1] + t * vy));
  }

  class ToolController {
    constructor(view, metrics, app) {
      this.view = view; this.metrics = metrics; this.app = app;
      this.tool = "select";
      this.selected = null;
      this.draft = null;          // in-progress polygon: {shape, committed:[[x,y],...]}
      this.ellipseDraft = null;   // {shape, p0}
      this.extend = null;         // appending points to a selected polygon: {shape, committed, orig}
      this._extendJustFinished = false; // swallow the dblclick's trailing mouseup
      this.panning = false; this._panLast = null; this._spaceDown = false;
      this._press = null;         // pending mousedown for click-vs-drag
      this._touch = { pan: null, dist: 0 };
      this.history = []; this.hidx = -1;
      this.vsel = null;           // selected vertex: {shape, i}
      this.view.commit = () => this.commit();
      this.view.onVertexSelect = (shape, i) => this.selectVertex(shape, i);
      this._bind();
    }

    /* ---- history ---- */
    serialize() {
      return this.view.shapes.map((s) => ({ classKey: s.classKey, kind: s.kind, data: s.toData() }));
    }
    pushInitial() { this.history = [this.serialize()]; this.hidx = 0; }
    commit() {
      this.history = this.history.slice(0, this.hidx + 1);
      this.history.push(this.serialize());
      this.hidx = this.history.length - 1;
    }
    restore(snap) {
      this.deselect();
      this.view.clearShapes();
      for (const s of snap) {
        const m = this.app.classMeta(s.classKey);
        if (s.kind === "polygon") this.view.addPolygon(s.classKey, m.color, s.data);
        else this.view.addEllipse(s.classKey, m.color, s.data);
      }
      this.view.layer.batchDraw();
      this.app.onChange();
    }
    undo() { if (this.hidx > 0) { this.hidx--; this.restore(this.history[this.hidx]); this.metrics.undo(); } }
    redo() { if (this.hidx < this.history.length - 1) { this.hidx++; this.restore(this.history[this.hidx]); this.metrics.redo(); } }

    /* ---- tool switching ---- */
    setTool(name) {
      this._cancelDraft();
      this._press = null;
      this.tool = name;
      document.querySelectorAll("#toolbar .tool").forEach((b) =>
        b.classList.toggle("active", b.dataset.tool === name));
      const hints = {
        select: "図形クリックで選択／頂点クリックで選択→ドラッグ移動・Backspace/Escで頂点削除／何もない所をドラッグで画像移動／ポリゴン選択中にShift+クリックで点を追加（ダブルクリックで確定）",
        polygon: "クリックで頂点追加／最初の点付近クリックかダブルクリックで閉じる／何もない所をドラッグで画像移動",
        ellipse: "ドラッグで楕円を作成／選択ツールで回転・リサイズ",
        pan: "ドラッグで画像移動／ホイール・2本指で拡大縮小",
      };
      this.app.setHint(hints[name] || "");
      this.view.stage.container().style.cursor = name === "pan" ? "grab" : "default";
    }

    /* ---- selection ---- */
    select(shape) {
      if (this.selected === shape) return;
      this.deselect();
      this.selected = shape;
      shape.group.moveToTop();   // active class on top -> editable even where it overlaps other classes
      shape.setEditable(true); shape.setSelected(true);
      this.view.layer.batchDraw();
    }
    deselect() {
      this.clearVertexSel();
      if (this.selected) { this.selected.setEditable(false); this.selected.setSelected(false); }
      this.selected = null;
      this.view.layer.batchDraw();
    }

    /* ---- vertex selection / deletion ---- */
    selectVertex(shape, i) {
      if (this.selected !== shape) this.select(shape);
      this.clearVertexSel();
      this.vsel = { shape, i };
      shape.highlightVertex(i);
      this.app.setHint("頂点を選択中 — Backspace / Esc で削除、ドラッグで移動");
    }
    clearVertexSel() {
      if (this.vsel) { this.vsel.shape.clearVertexSel(); this.vsel = null; }
    }
    deleteSelectedVertex() {
      if (!this.vsel) return false;
      const { shape, i } = this.vsel;
      if (shape.kind !== "polygon" || shape.points.length <= 3) {
        this.app.setHint("ポリゴンは3点以上必要です"); return false;
      }
      this.vsel = null;
      shape._deleteVertex(i);   // guards, metrics, rebuild, commit
      this.app.onChange();
      return true;
    }
    deleteSelected() {
      if (!this.selected) return;
      this.view.removeShape(this.selected);
      this.selected = null;
      this.metrics.shapeDeleted();
      this.commit(); this.app.onChange();
    }

    // move the whole selected shape by (dx,dy) image px (commit handled by caller)
    _nudge(dx, dy) {
      const s = this.selected;
      if (!s) return;
      if (s.kind === "polygon") {
        s.points = s.points.map((p) => [p[0] + dx, p[1] + dy]);
        this.clearVertexSel();
        s._rebuild();                       // redraw line + reposition anchors
      } else if (s.kind === "ellipse") {
        s.node.x(s.node.x() + dx); s.node.y(s.node.y() + dy);
        if (s.transformer) s.transformer.forceUpdate();
        this.view.layer.batchDraw();
      }
      this.app.onChange();
    }

    /* ---- event binding ---- */
    _bind() {
      const stage = this.view.stage;
      stage.on("mousedown", (e) => this._down(e));
      stage.on("mousemove", () => this._move());
      stage.on("mouseup", () => this._up());
      stage.on("dblclick", () => this._dbl());
      stage.on("contextmenu", (e) => e.evt.preventDefault());
      this.view.container.addEventListener("wheel", (e) => {
        e.preventDefault();
        const f = e.deltaY < 0 ? 1.12 : 1 / 1.12;
        this.view.zoomAt(f, stage.getPointerPosition());
        this._rescaleDraftMarkers();
        this.metrics.zoom();
      }, { passive: false });

      this._bindTouch();
      window.addEventListener("keydown", (e) => this._key(e, true));
      window.addEventListener("keyup", (e) => this._key(e, false));
    }

    /* Touch: 1-finger drag = pan, 2-finger pinch = zoom. */
    _bindTouch() {
      const c = this.view.container;
      const dist = (e) => Math.hypot(
        e.touches[0].clientX - e.touches[1].clientX,
        e.touches[0].clientY - e.touches[1].clientY);

      c.addEventListener("touchstart", (e) => {
        e.preventDefault();
        if (e.touches.length === 1) {
          this._touch.pan = { x: e.touches[0].clientX, y: e.touches[0].clientY };
          this._touch.dist = 0; this.metrics.pan();
        } else if (e.touches.length === 2) {
          this._touch.pan = null; this._touch.dist = dist(e); this.metrics.zoom();
        }
      }, { passive: false });

      c.addEventListener("touchmove", (e) => {
        e.preventDefault();
        if (e.touches.length === 1 && this._touch.pan) {
          const t = e.touches[0];
          const dx = t.clientX - this._touch.pan.x, dy = t.clientY - this._touch.pan.y;
          this.view.world.position({ x: this.view.world.x() + dx, y: this.view.world.y() + dy });
          this._touch.pan = { x: t.clientX, y: t.clientY };
          this.view.layer.batchDraw();
        } else if (e.touches.length === 2 && this._touch.dist) {
          const nd = dist(e);
          const rect = c.getBoundingClientRect();
          const center = {
            x: (e.touches[0].clientX + e.touches[1].clientX) / 2 - rect.left,
            y: (e.touches[0].clientY + e.touches[1].clientY) / 2 - rect.top };
          this.view.zoomAt(nd / this._touch.dist, center);
          this._rescaleDraftMarkers();
          this._touch.dist = nd;
        }
      }, { passive: false });

      const end = (e) => {
        if (e.touches.length === 0) { this._touch.pan = null; this._touch.dist = 0; }
        else if (e.touches.length === 1) {
          this._touch.pan = { x: e.touches[0].clientX, y: e.touches[0].clientY };
          this._touch.dist = 0;
        }
      };
      c.addEventListener("touchend", end);
      c.addEventListener("touchcancel", end);
    }

    _imgPt() { return this.view.pointerImage(); }

    _down(e) {
      const left = e.evt.button === 0;
      if (left) this.metrics.click();
      this._extendJustFinished = false;   // a fresh press cancels the dblclick guard

      // explicit pan: pan tool, middle button, or space held
      if (this.tool === "pan" || e.evt.button === 1 || this._spaceDown) {
        this._startPan(this.view.stage.getPointerPosition());
        return;
      }
      const pt = this._imgPt();
      if (!pt) return;

      // ellipse creation is drag-based -> begin immediately
      if (this.tool === "ellipse" && left) { this._ellipseStart(pt); return; }

      // Shift+click while a polygon is selected: enter "add points" mode and append
      // the clicked vertices to that EXISTING polygon (integrated into it, not a new
      // shape). Stays active until double-click / Enter (commit) or Esc (cancel).
      if (this.tool === "select" && left && e.evt.shiftKey &&
          !this.extend && this.selected && this.selected.kind === "polygon") {
        this._startExtend(this.selected, pt);
        return;
      }

      // a press on a Transformer handle (resize anchor / rotater) belongs to
      // Konva.Transformer — let it resize/rotate the ellipse, don't pan or select
      if (e.target && e.target.getParent &&
          e.target.getParent() instanceof Konva.Transformer) {
        return;
      }

      // polygon & select: decide click-vs-drag on move/up (drag on empty bg = pan)
      const onVertex = !!(e.target && e.target.name && e.target.name() === "vertex");
      const grp = e.target && e.target.getParent && e.target.getParent();
      const shape = grp && grp.shapeRef ? grp.shapeRef : null;
      this._press = { screen: this.view.stage.getPointerPosition(), img: pt,
                      onVertex, onShape: !!shape, shape, button: e.evt.button, moved: false };

      // select tool: don't select on mousedown. A press resolves on move/up:
      //   drag  -> pan the whole image (unless grabbing the current selection)
      //   click -> select the shape under the cursor, or deselect on empty
      // This lets you drag anywhere — even over a polygon/ellipse fill — to pan
      // when nothing (or something else) is selected.
    }

    _startPan(screen) {
      this.panning = true; this._panLast = screen;
      this.metrics.pan();
      this.view.stage.container().style.cursor = "grabbing";
    }

    _move() {
      const screen = this.view.stage.getPointerPosition();
      const pt = this._imgPt();
      if (pt) this.metrics.mouseMove(pt);

      if (this.panning && this._panLast && screen) {
        const dx = screen.x - this._panLast.x, dy = screen.y - this._panLast.y;
        this.view.world.position({ x: this.view.world.x() + dx, y: this.view.world.y() + dy });
        this._panLast = screen; this.view.layer.batchDraw();
        return;
      }
      if (this.draft && pt) { this._polyPreview(pt); return; }
      if (this.extend && pt) { this._extendPreview(pt); return; }
      if (this.ellipseDraft && pt) { this._ellipseDrag(pt); return; }

      // left / one-finger drag starting on empty background -> pan the image
      if (this._press && screen && !this._press.moved) {
        const d = Math.hypot(screen.x - this._press.screen.x, screen.y - this._press.screen.y);
        if (d > 4) {
          this._press.moved = true;
          const pr = this._press;
          const grabSelected = pr.shape && pr.shape === this.selected;
          // a vertex of the selected polygon, or the selected ellipse body, is
          // dragged by Konva itself; anything else drags the whole image (pan)
          const editingHandle = pr.onVertex || (grabSelected && pr.shape.kind === "ellipse");
          if (!editingHandle) {
            this._startPan(this._press.screen);
            const dx = screen.x - this._panLast.x, dy = screen.y - this._panLast.y;
            this.view.world.position({ x: this.view.world.x() + dx, y: this.view.world.y() + dy });
            this._panLast = screen; this.view.layer.batchDraw();
          }
        }
      }
    }

    _up() {
      if (this.panning) {
        this.panning = false; this._panLast = null;
        this.view.stage.container().style.cursor = this.tool === "pan" ? "grab" : "default";
        this._press = null;
        return;
      }
      if (this.ellipseDraft) { this._ellipseFinish(); this._press = null; return; }

      // a click only counts if the press did not turn into a drag
      const pr = this._press; this._press = null;
      if (this._extendJustFinished) { this._extendJustFinished = false; return; } // dblclick tail
      if (pr && !pr.moved && pr.button === 0) {
        if (this.extend) this._extendClick(pr.img);       // append a point to the polygon
        else if (this.tool === "polygon") this._polyClick(pr.img);
        else if (this.tool === "select" && !pr.onVertex) {
          // shape/class selection is sidebar-only; a canvas click just clears the
          // highlighted vertex (does NOT select/deselect a shape).
          this.clearVertexSel();
        }
      }
    }

    _dbl() {
      if (this.draft) this._polyFinish();
      else if (this.extend) { this._extendFinish(); this._extendJustFinished = true; }
    }

    /* ---- polygon drawing ---- */
    _polyClick(pt) {
      const cls = this.app.activeClass();
      const m = this.app.classMeta(cls);
      if (m.kind !== "polygon") { this.app.setHint("このクラスはポリゴンではありません"); return; }
      if (!this.draft) {
        const shape = this.view.addPolygon(cls, m.color, [[pt.x, pt.y]]);
        this.draft = { shape, committed: [[pt.x, pt.y]], markers: [], color: m.color };
        this._addDraftMarker(pt);
        return;
      }
      // close if near first point (screen distance)
      const first = this.draft.committed[0];
      const s = this.view.scale;
      const dpx = Math.hypot((pt.x - first[0]) * s, (pt.y - first[1]) * s);
      if (this.draft.committed.length >= 3 && dpx < CLOSE_PX) { this._polyFinish(); return; }
      this.draft.committed.push([pt.x, pt.y]);
      this._addDraftMarker(pt);
    }

    _addDraftMarker(pt) {
      const s = this.view.scale;
      const c = new Konva.Circle({
        x: pt.x, y: pt.y, radius: 5 / s, fill: "#fff",
        stroke: this.draft.color, strokeWidth: 2 / s, listening: false,
      });
      this.view.world.add(c);
      this.draft.markers.push(c);
      this.view.layer.batchDraw();
    }

    _clearDraftMarkers() {
      if (this.draft && this.draft.markers) this.draft.markers.forEach((m) => m.destroy());
    }
    _polyPreview(pt) {
      const d = this.draft;
      d.shape.points = d.committed.concat([[pt.x, pt.y]]);
      d.shape.line.points(d.shape._flat());
      this.view.layer.batchDraw();
    }
    _polyFinish() {
      const d = this.draft; this.draft = null;
      d.markers.forEach((m) => m.destroy());
      if (d.committed.length < 3) { this.view.removeShape(d.shape); this.view.layer.batchDraw(); return; }
      d.shape.points = d.committed;
      d.shape.line.points(d.shape._flat());
      this.metrics.shapeCreated();
      // 完成後は選択ツールへ。エリアをクリックすれば頂点をドラッグできる。
      this.setTool("select");
      this.select(d.shape);
      this.commit(); this.app.onChange();
    }

    /* ---- extend: append points to an existing (selected) polygon ---- */
    _startExtend(shape, pt) {
      const orig = shape.points.map((p) => [p[0], p[1]]);
      shape.setEditable(false);                       // hide interactive anchors while extending
      this.extend = { shape, committed: orig.map((p) => [p[0], p[1]]), orig, markers: [] };
      // show a dot on every vertex so the points stay visible during editing
      this.extend.committed.forEach((p) => this._extendMarker(p[0], p[1]));
      this._extendClick(pt);                          // place the first new point
      this.app.setHint("点を追加中 — クリックで追加・ダブルクリック/Enterで確定・Escで取消");
    }
    _extendMarker(x, y) {
      const s = this.view.scale;
      const c = new Konva.Circle({ x, y, radius: 5 / s, fill: "#fff",
        stroke: this.extend.shape.color, strokeWidth: 2 / s, listening: false });
      this.view.world.add(c);
      this.extend.markers.push(c);
    }
    _extendClick(pt) {
      const ex = this.extend;
      this._insertAtNearestEdge(ex.committed, pt);   // grow the outline at the nearest edge
      ex.shape.points = ex.committed.map((p) => [p[0], p[1]]);
      ex.shape.line.points(ex.shape._flat());
      this._extendMarker(pt.x, pt.y);
      this.metrics.vertexAdded();
      this.view.layer.batchDraw();
    }
    _extendPreview(pt) {
      const ex = this.extend;
      const pts = ex.committed.map((p) => [p[0], p[1]]);
      this._insertAtNearestEdge(pts, pt);            // preview where the point will land
      ex.shape.points = pts;
      ex.shape.line.points(ex.shape._flat());
      this.view.layer.batchDraw();
    }
    // insert p={x,y} into the closed polygon `pts` on the edge nearest to it, so the
    // new vertex connects to its two neighbours and the area grows locally (instead
    // of appending at the end, which would link distant vertices across the seam)
    _insertAtNearestEdge(pts, p) {
      const n = pts.length;
      let best = 0, bestD = Infinity;
      for (let i = 0; i < n; i++) {
        const d = segDist(p, pts[i], pts[(i + 1) % n]);
        if (d < bestD) { bestD = d; best = i; }
      }
      pts.splice(best + 1, 0, [p.x, p.y]);
      return best + 1;
    }
    _clearExtendMarkers() {
      if (this.extend && this.extend.markers) this.extend.markers.forEach((m) => m.destroy());
    }
    _extendFinish() {
      const ex = this.extend;
      this._clearExtendMarkers();
      this.extend = null;
      // drop consecutive duplicate points (e.g. from the closing double-click)
      const pts = ex.committed.filter((p, i) => i === 0 ||
        Math.hypot(p[0] - ex.committed[i - 1][0], p[1] - ex.committed[i - 1][1]) > 0.5);
      ex.shape.points = pts;
      ex.shape.setEditable(true);                     // rebuild anchors from new points
      this.app.setHint("");
      this.commit(); this.app.onChange();
    }
    _cancelExtend() {
      if (!this.extend) return;
      const ex = this.extend;
      this._clearExtendMarkers();
      this.extend = null;
      ex.shape.points = ex.orig;                      // revert to the original outline
      ex.shape.setEditable(true);
      this.app.setHint("");
      this.view.layer.batchDraw();
    }

    /* ---- ellipse drawing ---- */
    _ellipseStart(pt) {
      const cls = this.app.activeClass();
      const m = this.app.classMeta(cls);
      if (m.kind !== "ellipse") { this.app.setHint("このクラスは楕円ではありません"); return; }
      const shape = this.view.addEllipse(cls, m.color, { cx: pt.x, cy: pt.y, rx: 1, ry: 1, rotation: 0 });
      this.ellipseDraft = { shape, p0: pt };
    }
    _ellipseDrag(pt) {
      const { shape, p0 } = this.ellipseDraft;
      shape.node.x((p0.x + pt.x) / 2); shape.node.y((p0.y + pt.y) / 2);
      shape.node.radiusX(Math.max(1, Math.abs(pt.x - p0.x) / 2));
      shape.node.radiusY(Math.max(1, Math.abs(pt.y - p0.y) / 2));
      this.view.layer.batchDraw();
    }
    _ellipseFinish() {
      const { shape } = this.ellipseDraft; this.ellipseDraft = null;
      if (shape.node.radiusX() < 3 || shape.node.radiusY() < 3) { this.view.removeShape(shape); return; }
      this.metrics.shapeCreated();
      this.setTool("select");
      this.select(shape);
      this.commit(); this.app.onChange();
    }

    _cancelDraft() {
      if (this.draft) {
        this._clearDraftMarkers();
        this.view.removeShape(this.draft.shape); this.draft = null;
      }
      if (this.ellipseDraft) { this.view.removeShape(this.ellipseDraft.shape); this.ellipseDraft = null; }
      if (this.extend) this._cancelExtend();
      this.view.layer.batchDraw();
    }

    _rescaleDraftMarkers() {
      const s = this.view.scale;
      const rescale = (m) => { m.radius(5 / s); m.strokeWidth(2 / s); };
      if (this.draft && this.draft.markers) this.draft.markers.forEach(rescale);
      if (this.extend && this.extend.markers) this.extend.markers.forEach(rescale);
    }

    /* ---- keyboard ---- */
    _key(e, down) {
      if (e.target && /input|select|textarea/i.test(e.target.tagName)) return;
      if (e.code === "Space") {
        // while drawing a polygon or adding points, Space drops a point at the cursor
        if (down && !e.repeat && (this.extend || (this.tool === "polygon" && !this.panning))) {
          e.preventDefault();
          const pt = this._imgPt();
          if (pt) { if (this.extend) this._extendClick(pt); else this._polyClick(pt); }
          return;
        }
        this._spaceDown = down;
        if (!down && !this.panning)
          this.view.stage.container().style.cursor = this.tool === "pan" ? "grab" : "default";
        return;
      }
      // arrow keys nudge the selected shape by 1 image px; one undo step per gesture
      const NUDGE = { ArrowUp: [0, -1], ArrowDown: [0, 1], ArrowLeft: [-1, 0], ArrowRight: [1, 0] };
      if (NUDGE[e.key]) {
        if (!this.selected) return;
        e.preventDefault();
        if (down) { this._nudge(NUDGE[e.key][0], NUDGE[e.key][1]); this._nudgeDirty = true; }
        else if (this._nudgeDirty) { this._nudgeDirty = false; this.metrics.vertexMoved(); this.commit(); }
        return;
      }
      if (!down) return;
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") { e.preventDefault(); this.undo(); return; }
      if ((e.ctrlKey || e.metaKey) && (e.key.toLowerCase() === "y" ||
          (e.shiftKey && e.key.toLowerCase() === "z"))) { e.preventDefault(); this.redo(); return; }
      switch (e.key.toLowerCase()) {
        case "v": this.setTool("select"); break;
        case "p": this.setTool("polygon"); break;
        case "e": this.setTool("ellipse"); break;
        case "f": this.view.fit(); break;
        case "enter":
          if (this.draft) this._polyFinish();
          else if (this.extend) this._extendFinish();        // 追加した点を確定
          break;
        case "escape":
          e.preventDefault();
          if (this.extend) this._cancelExtend();             // 追加を取消（元の形に戻す）
          else if (this.draft || this.ellipseDraft) this._cancelDraft();
          else if (this.vsel) this.deleteSelectedVertex();   // 選択頂点を削除
          else this.deselect();
          break;
        case "delete": case "backspace":
          e.preventDefault();
          if (this.vsel) this.deleteSelectedVertex();         // 選択頂点を削除
          else this.deleteSelected();                          // 図形ごと削除
          break;
      }
    }
  }

  HITL.ToolController = ToolController;
})(window.HITL = window.HITL || {});

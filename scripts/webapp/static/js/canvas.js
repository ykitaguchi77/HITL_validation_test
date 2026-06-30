/* Konva canvas view: image display, zoom/pan, and editable shape primitives
 * (polygon + OBB ellipse). All shape geometry is stored in IMAGE pixel coords.
 */
(function (HITL) {
  "use strict";

  const ANCHOR = 5;      // anchor radius in screen px
  const STROKE = 2;      // shape stroke in screen px
  const TF_ANCHOR = 16;     // ellipse transformer handle size in screen px (easy to grab)
  const TF_ROT_OFFSET = 28; // rotate handle distance above the box in screen px
  const FILL_ALPHA = 0.18;  // interior tint when fill is ON (0 = no fill, still clickable)
  let _uid = 0;

  function hexA(hex, a) {
    const n = parseInt(hex.slice(1), 16);
    return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
  }

  /* ---------------- Polygon shape ---------------- */
  class PolygonShape {
    constructor(view, classKey, color, points) {
      this.id = ++_uid; this.kind = "polygon";
      this.view = view; this.classKey = classKey; this.color = color;
      this.points = points.map((p) => [p[0], p[1]]); // [[x,y],...]
      this.editable = false;
      this.selVertex = -1;           // currently highlighted vertex (-1 = none)
      this.group = new Konva.Group();
      this.line = new Konva.Line({
        closed: true, stroke: color, fill: hexA(color, view.showFill === false ? 0 : FILL_ALPHA),
        strokeWidth: STROKE, hitStrokeWidth: 12,
      });
      this.group.add(this.line);
      this.group.shapeRef = this;
      this.anchors = [];
      this.midpoints = [];
      view.world.add(this.group);
      this._rebuild();
    }

    _flat() { const f = []; this.points.forEach((p) => f.push(p[0], p[1])); return f; }

    _rebuild() {
      this.selVertex = -1;
      this.line.points(this._flat());
      this.anchors.forEach((a) => a.destroy());
      this.midpoints.forEach((m) => m.destroy());
      this.anchors = []; this.midpoints = [];
      if (this.editable) this._buildHandles();
      this.updateScale();
      this.view.layer.batchDraw();
    }

    _buildHandles() {
      const s = this.view.scale;
      this.points.forEach((p, i) => {
        const c = new Konva.Circle({
          x: p[0], y: p[1], radius: ANCHOR / s, fill: "#fff", name: "vertex",
          stroke: this.color, strokeWidth: 2 / s, draggable: true,
        });
        c.on("dragmove", () => { this.points[i] = [c.x(), c.y()]; this.line.points(this._flat());
          this._positionMidpoints(); this.view.layer.batchDraw(); });
        c.on("dragend", () => { this.view.metrics && this.view.metrics.vertexMoved();
          this.view.commit && this.view.commit(); });
        c.on("mousedown", (e) => {
          if (e.evt.altKey || e.evt.button === 2) { e.cancelBubble = true; this._deleteVertex(i); return; }
          if (e.evt.button === 0) this.view.onVertexSelect && this.view.onVertexSelect(this, i);
        });
        c.on("mouseenter", () => (this.view.stage.container().style.cursor = "pointer"));
        c.on("mouseleave", () => (this.view.stage.container().style.cursor = ""));
        this.group.add(c); this.anchors.push(c);
      });
      this.points.forEach((_, i) => {
        const m = new Konva.Circle({ radius: ANCHOR / s * 0.8, fill: this.color,
          opacity: 0.5, stroke: "#fff", strokeWidth: 1 / s });
        m.on("mousedown", (e) => {
          e.cancelBubble = true;
          if (e.evt.button !== 0) return;
          const newIdx = this._insertVertex(i);       // rebuilds anchors
          const anchor = this.anchors[newIdx];
          if (anchor) {
            this.view.onVertexSelect && this.view.onVertexSelect(this, newIdx);
            anchor.startDrag();                        // drag the new point in the same gesture
          }
        });
        m.on("mouseenter", () => (this.view.stage.container().style.cursor = "copy"));
        m.on("mouseleave", () => (this.view.stage.container().style.cursor = ""));
        this.group.add(m); this.midpoints.push(m);
      });
      this._positionMidpoints();
      this.anchors.forEach((a) => a.moveToTop()); // vertices always above midpoints
      this._styleAnchors();
    }

    _styleAnchors() {
      const s = this.view.scale;
      this.anchors.forEach((a, idx) => {
        a.radius(ANCHOR / s);                       // 一定サイズ（拡大しない）
        if (idx === this.selVertex) { a.fill(this.color); a.stroke("#fff"); }  // 色で強調
        else { a.fill("#fff"); a.stroke(this.color); }
      });
    }

    highlightVertex(i) { this.selVertex = i; this._styleAnchors(); this.view.layer.batchDraw(); }
    clearVertexSel() { this.selVertex = -1; this._styleAnchors(); this.view.layer.batchDraw(); }

    _positionMidpoints() {
      const n = this.points.length;
      this.midpoints.forEach((m, i) => {
        const a = this.points[i], b = this.points[(i + 1) % n];
        m.position({ x: (a[0] + b[0]) / 2, y: (a[1] + b[1]) / 2 });
      });
    }

    _insertVertex(i) {
      const n = this.points.length;
      const a = this.points[i], b = this.points[(i + 1) % n];
      this.points.splice(i + 1, 0, [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]);
      this.view.metrics && this.view.metrics.vertexAdded();
      this._rebuild();
      this.view.commit && this.view.commit();
      return i + 1; // index of the newly inserted vertex
    }

    _deleteVertex(i) {
      if (this.points.length <= 3) return;
      this.points.splice(i, 1);
      this.view.metrics && this.view.metrics.vertexDeleted();
      this._rebuild();
      this.view.commit && this.view.commit();
    }

    addPoint(pt) { this.points.push([pt.x, pt.y]); this.line.points(this._flat());
      this.view.layer.batchDraw(); }

    setEditable(b) { if (this.editable === b) return; this.editable = b; this._rebuild(); }

    setSelected(b) { this.line.strokeWidth((b ? STROKE + 1 : STROKE) / this.view.scale); }

    // fill ON = visible tint; OFF = alpha 0 (invisible) but still hit-tested -> clickable
    applyFill(on) { this.line.fill(hexA(this.color, on ? FILL_ALPHA : 0)); }

    updateScale() {
      const s = this.view.scale;
      this.line.strokeWidth(STROKE / s);
      this.anchors.forEach((a) => a.strokeWidth(2 / s));
      this._styleAnchors();
      this.midpoints.forEach((m) => { m.radius(ANCHOR / s * 0.8); m.strokeWidth(1 / s); });
    }

    toData() { return this.points.map((p) => [p[0], p[1]]); }
    destroy() { this.group.destroy(); }
  }

  /* ---------------- Ellipse (OBB) shape ---------------- */
  class EllipseShape {
    constructor(view, classKey, color, data) {
      this.id = ++_uid; this.kind = "ellipse";
      this.view = view; this.classKey = classKey; this.color = color;
      this.group = new Konva.Group();
      this.node = new Konva.Ellipse({
        x: data.cx, y: data.cy, radiusX: data.rx, radiusY: data.ry,
        rotation: data.rotation || 0, stroke: color,
        fill: hexA(color, view.showFill === false ? 0 : FILL_ALPHA),
        strokeWidth: STROKE, draggable: false, hitStrokeWidth: 12,
      });
      this.node.on("dragend", () => { this.view.metrics && this.view.metrics.vertexMoved();
        this.view.commit && this.view.commit(); });
      this.node.on("transformend", () => { this._bake();
        this.view.metrics && this.view.metrics.vertexMoved();
        this.view.commit && this.view.commit(); });
      this.group.add(this.node);
      this.group.shapeRef = this;
      view.world.add(this.group);
      this.transformer = null;
      this.updateScale();
    }

    _bake() {
      // fold scale from the transformer back into radii so data stays clean
      const sx = this.node.scaleX(), sy = this.node.scaleY();
      this.node.radiusX(Math.max(1, this.node.radiusX() * sx));
      this.node.radiusY(Math.max(1, this.node.radiusY() * sy));
      this.node.scaleX(1); this.node.scaleY(1);
    }

    setEditable(b) {
      this.node.draggable(b);
      if (b && !this.transformer) {
        this.transformer = new Konva.Transformer({
          rotateEnabled: true, keepRatio: false,
          enabledAnchors: ["top-left", "top-right", "bottom-left", "bottom-right",
            "middle-left", "middle-right", "top-center", "bottom-center"],
          borderStroke: this.color, anchorStroke: this.color, anchorFill: "#fff",
          anchorCornerRadius: 3, ignoreStroke: true,
          // sizes are in screen px and stay constant at any zoom because the
          // transformer lives on the (unscaled) layer, not the scaled world group
          anchorSize: TF_ANCHOR, rotateAnchorOffset: TF_ROT_OFFSET,
          borderStrokeWidth: 1.5, anchorStrokeWidth: 1.5,
        });
        this.view.layer.add(this.transformer);   // unscaled -> zoom-independent handles
        this.transformer.nodes([this.node]);
        this.updateScale();
      } else if (!b && this.transformer) {
        this.transformer.destroy(); this.transformer = null;
      }
      this.view.layer.batchDraw();
    }

    setSelected(b) { this.node.strokeWidth((b ? STROKE + 1 : STROKE) / this.view.scale); }

    applyFill(on) { this.node.fill(hexA(this.color, on ? FILL_ALPHA : 0)); }

    updateScale() {
      const s = this.view.scale;
      this.node.strokeWidth(STROKE / s);
      // transformer handles live on the unscaled layer, so their size is already
      // constant in screen px and needs no per-zoom adjustment here
      if (this.transformer) this.transformer.forceUpdate();
    }

    toData() {
      this._bake();
      return { cx: this.node.x(), cy: this.node.y(),
        rx: this.node.radiusX(), ry: this.node.radiusY(),
        rotation: ((this.node.rotation() % 360) + 360) % 360 };
    }
    destroy() { if (this.transformer) this.transformer.destroy(); this.group.destroy(); }
  }

  /* ---------------- Canvas view ---------------- */
  class CanvasView {
    constructor(containerId) {
      const el = document.getElementById(containerId);
      this.container = el;
      el.style.touchAction = "none";   // ブラウザのスクロール/ズームを無効化（自前で処理）
      this.stage = new Konva.Stage({ container: containerId,
        width: el.clientWidth, height: el.clientHeight });
      this.layer = new Konva.Layer();
      this.stage.add(this.layer);
      this.world = new Konva.Group();
      this.layer.add(this.world);
      this.imageNode = null;
      this.scale = 1;
      this.shapes = [];
      this.metrics = null;
      this.showFill = false;  // default: no interior fill (toggleable; survives image loads)
      this.brightness = 0; this.contrast = 0;   // image display filters (persist across images)
      this.imgW = 0; this.imgH = 0;
      window.addEventListener("resize", () => this._resize());
    }

    setShowFill(on) {
      this.showFill = on;
      this.shapes.forEach((s) => s.applyFill && s.applyFill(on));
      this.layer.batchDraw();
    }

    // brightness in [-1,1], contrast in [-100,100] (Konva filter ranges); persists across images
    setBrightness(v) {
      this.brightness = v;
      if (this.imageNode) { this.imageNode.brightness(v); this.layer.batchDraw(); }
    }
    setContrast(v) {
      this.contrast = v;
      if (this.imageNode) { this.imageNode.contrast(v); this.layer.batchDraw(); }
    }

    _resize() {
      this.stage.width(this.container.clientWidth);
      this.stage.height(this.container.clientHeight);
      this.layer.batchDraw();
    }

    loadImage(url, w, h) {
      return new Promise((resolve) => {
        const img = new Image();
        img.onload = () => {
          this.clearShapes();
          if (this.imageNode) this.imageNode.destroy();
          this.imgW = w || img.naturalWidth; this.imgH = h || img.naturalHeight;
          this.imageNode = new Konva.Image({ image: img, x: 0, y: 0,
            width: this.imgW, height: this.imgH, listening: false });
          this.world.add(this.imageNode);
          this.imageNode.moveToBottom();
          // brightness/contrast filters (re-apply persisted values to each new image)
          this.imageNode.cache();
          this.imageNode.filters([Konva.Filters.Brighten, Konva.Filters.Contrast]);
          this.imageNode.brightness(this.brightness || 0);
          this.imageNode.contrast(this.contrast || 0);
          this.maximize();   // default view: fill the window
          resolve();
        };
        img.src = url;
      });
    }

    fit() {
      const pad = 24;
      const sx = (this.stage.width() - pad * 2) / this.imgW;
      const sy = (this.stage.height() - pad * 2) / this.imgH;
      this._applyScale(Math.min(sx, sy));   // contain: whole image visible
    }

    // fill the window with the image (cover): maximize on-screen size, may crop edges
    maximize() {
      const sx = this.stage.width() / this.imgW;
      const sy = this.stage.height() / this.imgH;
      this._applyScale(Math.max(sx, sy));
    }

    _applyScale(s) {
      this.scale = s;
      this.world.scale({ x: s, y: s });
      this.world.position({
        x: (this.stage.width() - this.imgW * s) / 2,
        y: (this.stage.height() - this.imgH * s) / 2,
      });
      this.refreshScale();
      this.layer.batchDraw();
    }

    zoomAt(factor, pointer) {
      const old = this.scale;
      const ns = Math.max(0.05, Math.min(40, old * factor));
      const mx = (pointer.x - this.world.x()) / old;
      const my = (pointer.y - this.world.y()) / old;
      this.scale = ns;
      this.world.scale({ x: ns, y: ns });
      this.world.position({ x: pointer.x - mx * ns, y: pointer.y - my * ns });
      this.refreshScale();
      this.layer.batchDraw();
    }

    refreshScale() { this.shapes.forEach((s) => s.updateScale()); }

    screenToImage(pt) {
      return { x: (pt.x - this.world.x()) / this.scale,
               y: (pt.y - this.world.y()) / this.scale };
    }
    pointerImage() { const p = this.stage.getPointerPosition(); return p ? this.screenToImage(p) : null; }

    addPolygon(classKey, color, points) {
      const s = new PolygonShape(this, classKey, color, points);
      this.shapes.push(s); return s;
    }
    addEllipse(classKey, color, data) {
      const s = new EllipseShape(this, classKey, color, data);
      this.shapes.push(s); return s;
    }
    removeShape(shape) {
      const i = this.shapes.indexOf(shape);
      if (i >= 0) { this.shapes.splice(i, 1); shape.destroy(); this.layer.batchDraw(); }
    }
    shapesOf(classKey) { return this.shapes.filter((s) => s.classKey === classKey); }
    clearShapes() { this.shapes.forEach((s) => s.destroy()); this.shapes = []; }

    getAnnotation() {
      const out = { eyelid: [], caruncle: [], iris: [], pupil: [] };
      this.shapes.forEach((s) => { if (out[s.classKey]) out[s.classKey].push(s.toData()); });
      return out;
    }
  }

  HITL.CanvasView = CanvasView;
  HITL.PolygonShape = PolygonShape;
  HITL.EllipseShape = EllipseShape;
})(window.HITL = window.HITL || {});

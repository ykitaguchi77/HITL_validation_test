/* Per-image interaction metrics tracker.
 * Mouse distance is accumulated in IMAGE pixel coordinates (zoom-independent).
 * Per-class time/clicks/vertex edits are attributed to the currently active class.
 */
(function (HITL) {
  "use strict";

  const CLASS_KEYS = ["eyelid", "caruncle", "iris", "pupil"];

  function blankPerClass() {
    const o = {};
    for (const k of CLASS_KEYS) {
      o[k] = { clicks: 0, time_sec: 0, vertices_edited: 0 };
    }
    return o;
  }

  class Metrics {
    constructor() { this.reset(); }

    reset() {
      this.start = performance.now();
      this.lastImagePt = null;          // last pointer pos in image coords
      this.mouse_distance_px = 0;
      this.total_clicks = 0;
      this.vertices_added = 0;
      this.vertices_moved = 0;
      this.vertices_deleted = 0;
      this.shapes_created = 0;
      this.shapes_deleted = 0;
      this.undo_count = 0;
      this.redo_count = 0;
      this.zoom_count = 0;
      this.pan_count = 0;
      this.per_class = blankPerClass();
      this.activeClass = null;
      this._classSince = performance.now();
    }

    setActiveClass(key) {
      this._flushClassTime();
      this.activeClass = key;
      this._classSince = performance.now();
    }

    _flushClassTime() {
      if (this.activeClass && this.per_class[this.activeClass]) {
        const now = performance.now();
        this.per_class[this.activeClass].time_sec += (now - this._classSince) / 1000;
        this._classSince = now;
      }
    }

    mouseMove(imgPt) {
      if (this.lastImagePt) {
        const dx = imgPt.x - this.lastImagePt.x;
        const dy = imgPt.y - this.lastImagePt.y;
        this.mouse_distance_px += Math.hypot(dx, dy);
      }
      this.lastImagePt = imgPt;
    }

    click() {
      this.total_clicks += 1;
      if (this.activeClass) this.per_class[this.activeClass].clicks += 1;
    }

    vertexAdded()  { this.vertices_added += 1;  this._clsVertex(); }
    vertexMoved()  { this.vertices_moved += 1;  this._clsVertex(); }
    vertexDeleted(){ this.vertices_deleted += 1; this._clsVertex(); }
    _clsVertex()   { if (this.activeClass) this.per_class[this.activeClass].vertices_edited += 1; }

    shapeCreated() { this.shapes_created += 1; }
    shapeDeleted() { this.shapes_deleted += 1; }
    undo() { this.undo_count += 1; }
    redo() { this.redo_count += 1; }
    zoom() { this.zoom_count += 1; }
    pan()  { this.pan_count += 1; }

    snapshot() {
      this._flushClassTime();
      return {
        duration_sec: (performance.now() - this.start) / 1000,
        mouse_distance_px: this.mouse_distance_px,
        total_clicks: this.total_clicks,
        vertices_added: this.vertices_added,
        vertices_moved: this.vertices_moved,
        vertices_deleted: this.vertices_deleted,
        shapes_created: this.shapes_created,
        shapes_deleted: this.shapes_deleted,
        undo_count: this.undo_count,
        redo_count: this.redo_count,
        zoom_count: this.zoom_count,
        pan_count: this.pan_count,
        per_class: this.per_class,
      };
    }
  }

  HITL.Metrics = Metrics;
})(window.HITL = window.HITL || {});

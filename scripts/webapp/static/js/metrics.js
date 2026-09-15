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
      // timestamped action log (seconds of ACTIVE time from image ready); powers
      // the effort-vs-quality curve and derived time-to-first-action / idle time.
      this.events = [];
      this.first_action_sec = null;
      // focus-loss pausing: time while the window is inactive is excluded from
      // duration / event clocks (annotator switched to another window).
      this._pausedMs = 0;
      this._paused = false;
      this._pauseStart = 0;
      // periodic heartbeats (to spot away-from-desk gaps even without a blur).
      this.heartbeats = [];
    }

    // active elapsed ms = wall time since start, minus any paused intervals
    _elapsedMs() {
      let paused = this._pausedMs;
      if (this._paused) paused += performance.now() - this._pauseStart;
      return performance.now() - this.start - paused;
    }

    // record one timestamped action on the ACTIVE clock; keeps first-action latency
    _log(type) {
      const t = this._elapsedMs() / 1000;
      if (this.first_action_sec === null) this.first_action_sec = t;
      this.events.push({ t: +t.toFixed(3), type, cls: this.activeClass });
    }

    // pause/resume timing on window focus loss/gain
    pause() {
      if (this._paused) return;
      this._flushClassTime();          // don't attribute paused time to a class
      this._paused = true;
      this._pauseStart = performance.now();
    }
    resume() {
      if (!this._paused) return;
      this._pausedMs += performance.now() - this._pauseStart;
      this._paused = false;
      this._classSince = performance.now();
      this.lastImagePt = null;         // ignore the cursor jump on return (no phantom distance)
    }

    heartbeat() {
      this.heartbeats.push({ t: +(this._elapsedMs() / 1000).toFixed(1), wall: Date.now() });
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
      if (this._paused) return;         // don't accumulate distance while inactive
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
      this._log("click");
    }

    vertexAdded()  { this.vertices_added += 1;  this._clsVertex(); this._log("v+"); }
    vertexMoved()  { this.vertices_moved += 1;  this._clsVertex(); this._log("v~"); }
    vertexDeleted(){ this.vertices_deleted += 1; this._clsVertex(); this._log("v-"); }
    _clsVertex()   { if (this.activeClass) this.per_class[this.activeClass].vertices_edited += 1; }

    shapeCreated() { this.shapes_created += 1; this._log("s+"); }
    shapeDeleted() { this.shapes_deleted += 1; this._log("s-"); }
    undo() { this.undo_count += 1; this._log("undo"); }
    redo() { this.redo_count += 1; this._log("redo"); }
    zoom() { this.zoom_count += 1; this._log("zoom"); }
    pan()  { this.pan_count += 1; this._log("pan"); }

    // idle = sum of gaps (>IDLE_GAP s) between consecutive actions and after the
    // last action, measuring hesitation/thinking within the working period.
    _idleSec(now) {
      const IDLE_GAP = 2.0;
      if (this.first_action_sec === null) return 0;
      let idle = 0, prev = this.first_action_sec;
      for (const e of this.events) {
        const gap = e.t - prev;
        if (gap > IDLE_GAP) idle += gap;
        prev = e.t;
      }
      const tail = now - prev;
      if (tail > IDLE_GAP) idle += tail;
      return idle;
    }

    snapshot() {
      this._flushClassTime();
      const now = this._elapsedMs() / 1000;
      return {
        duration_sec: now,
        paused_time_sec: this._pausedMs / 1000,
        heartbeats: this.heartbeats,
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
        time_to_first_action_sec: this.first_action_sec,
        idle_time_sec: this._idleSec(now),
        per_class: this.per_class,
        events: this.events,
      };
    }
  }

  HITL.Metrics = Metrics;
})(window.HITL = window.HITL || {});

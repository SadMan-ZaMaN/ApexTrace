/* A replay clock with controls, shared by the overview hero and the Lap compare map.
 *
 * It only keeps time: t (seconds into the lap) advances with real elapsed time
 * multiplied by the speed (x1, x2, x4), and every change calls onFrame(t), which
 * the page uses to draw the cars. Seeking (the timeline, a click on the track or
 * a chart) just sets t. Nothing here knows about F1.
 *
 *   const replay = new AT.Replay(container, { duration: 82.8, onFrame: (t) => draw(t) });
 *   replay.play(); replay.seek(41.2); replay.setSpeed(2);
 */
AT.Replay = class {
  constructor(container, { duration, onFrame, loop = false, hold = 2.5, showTime = true }) {
    this.duration = duration;
    this.onFrame = onFrame;
    this.loop = loop;          // overview: start again after a short hold; Lap compare: stop at the end
    this.hold = hold;
    this.t = 0;
    this.speed = 1;
    this.playing = false;
    this.visible = true;
    this.raf = null;
    this.last = null;
    this.build(container, showTime);
  }

  // ---------------------------------------------------------------- controls (plain DOM)
  build(container, showTime) {
    this.button = AT.el("button", { type: "button", class: "replay-btn" }, "Play");
    this.button.addEventListener("click", () => this.toggle());
    const speeds = AT.el("div", { class: "replay-speeds", role: "group", "aria-label": "Replay speed" });
    this.speedButtons = [1, 2, 4].map((speed) => {
      const b = AT.el("button", { type: "button", "aria-pressed": String(speed === 1) }, `×${speed}`);
      b.addEventListener("click", () => this.setSpeed(speed));
      speeds.append(b);
      return b;
    });
    // the timeline: a range input from 0 to the lap time, 0.01 s steps
    this.range = AT.el("input", { type: "range", class: "replay-range", min: "0", max: String(this.duration),
      step: "0.01", value: "0", "aria-label": "Position in the lap (seconds)" });
    this.range.addEventListener("input", () => this.seek(Number(this.range.value)));
    this.timeNode = showTime ? AT.el("span", { class: "replay-time num" }, AT.lapTime(0)) : null;
    container.replaceChildren(this.button, speeds, this.range, ...(this.timeNode ? [this.timeNode] : []));
  }

  label() {
    this.button.textContent = this.playing ? "Pause" : this.t >= this.duration ? "Replay" : "Play";
    this.button.setAttribute("aria-label", this.playing ? "Pause the replay" : "Play the replay");
  }

  // ---------------------------------------------------------------- the clock
  render() {
    const t = Math.min(this.t, this.duration);
    this.range.value = String(t);
    if (this.timeNode) this.timeNode.textContent = AT.lapTime(t);
    this.onFrame(t);
  }

  frame(now) {
    this.raf = null;
    if (!this.playing || !this.visible) { this.last = null; return; }
    if (this.last !== null) this.t += ((now - this.last) / 1000) * this.speed;   // real time x speed
    this.last = now;
    if (this.t >= this.duration) {
      if (this.loop && this.t > this.duration + this.hold) {
        this.t = 0;
      } else if (!this.loop) {
        this.t = this.duration;
        this.playing = false;
        this.label();
      }
    }
    this.render();
    if (this.playing) this.raf = requestAnimationFrame((n) => this.frame(n));
  }

  run() {
    if (this.raf === null) { this.last = null; this.raf = requestAnimationFrame((n) => this.frame(n)); }
  }

  play() {
    if (this.t >= this.duration) this.t = 0;
    this.playing = true;
    this.label();
    this.run();
  }

  pause() {
    this.playing = false;
    this.label();
  }

  toggle() {
    if (this.playing) this.pause();
    else this.play();
  }

  seek(t) {
    this.t = Math.max(0, Math.min(this.duration, t));
    this.label();
    this.render();
  }

  setSpeed(speed) {
    this.speed = speed;
    this.speedButtons.forEach((b, i) => b.setAttribute("aria-pressed", String([1, 2, 4][i] === speed)));
  }

  setVisible(visible) {
    this.visible = visible;
    if (visible && this.playing) this.run();
  }

  destroy() {
    this.playing = false;
    if (this.raf !== null) cancelAnimationFrame(this.raf);
    this.raf = null;
  }
};

/** Index of the sample nearest to a point (px, py) in screen units: used for "click the track to jump there". */
AT.nearestSample = (xs, ys, px, py) => {
  let best = 0, bestDistance = Infinity;
  for (let i = 0; i < xs.length; i++) {
    const d = (xs[i] - px) ** 2 + (ys[i] - py) ** 2;
    if (d < bestDistance) { bestDistance = d; best = i; }
  }
  return best;
};

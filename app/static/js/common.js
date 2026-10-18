/* Shared helpers for every page. No framework: plain functions collected on one
 * object, AT ("ApexTrace"), so each page script can use them.
 *
 * Safety rule used everywhere: text that comes from data (driver names, team
 * names, places) is put on the page with textContent, never as HTML.
 */
const AT = (() => {
  /** 82.595 -> "1:22.595" (a lap time as shown on a timing screen) */
  function lapTime(seconds) {
    if (seconds == null || !isFinite(seconds)) return "–";
    const minutes = Math.floor(seconds / 60);
    const rest = seconds - minutes * 60;
    return `${minutes}:${rest.toFixed(3).padStart(6, "0")}`;
  }

  /** 0.2049 -> "+0.205", -0.1 -> "−0.100" (a real minus sign, as timing screens print it) */
  function signed(value, digits = 3) {
    if (value == null || !isFinite(value)) return "–";
    const text = Math.abs(value).toFixed(digits);
    return (value < 0 ? "−" : "+") + text;
  }

  /** Blend colour a toward colour b: mix("#ff8000", "#ffffff", 0.5) = halfway to white.
   *  Used to give the second driver of the same team a lighter shade of the team colour. */
  function mix(a, b, amount) {
    const ca = d3.rgb(a), cb = d3.rgb(b);
    return d3.rgb(ca.r + (cb.r - ca.r) * amount, ca.g + (cb.g - ca.g) * amount, ca.b + (cb.b - ca.b) * amount).formatHex();
  }

  /** How different two colours look (distance in the CIE Lab colour space; < ~25 = easy to confuse on a chart). */
  function colourDistance(a, b) {
    const la = d3.lab(a), lb = d3.lab(b);
    return Math.hypot(la.l - lb.l, la.a - lb.a, la.b - lb.b);
  }

  /** fetch + JSON, with the server's error message if it sent one */
  async function getJSON(url) {
    const response = await fetch(url);
    let body = null;
    try { body = await response.json(); } catch (error) { body = null; }
    if (!response.ok) {
      const error = new Error((body && body.error) || `${response.status} ${response.statusText}`);
      error.status = response.status;
      error.body = body;
      throw error;
    }
    return body;
  }

  /** Tiny DOM builder: el("span", {class: "code"}, "NOR") -> <span class="code">NOR</span>.
   *  Strings become text nodes (safe); other arguments must be DOM nodes. */
  function el(tag, attributes = {}, ...children) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attributes)) {
      if (value == null || value === false) continue;
      if (key === "style" && typeof value === "object") Object.assign(node.style, value);
      else node.setAttribute(key, value === true ? "" : value);
    }
    for (const child of children) {
      if (child == null) continue;
      node.append(typeof child === "string" || typeof child === "number" ? document.createTextNode(String(child)) : child);
    }
    return node;
  }

  /** Linear interpolation of ys at x, for sorted xs (like numpy.interp). */
  function interp(x, xs, ys) {
    if (x <= xs[0]) return ys[0];
    if (x >= xs[xs.length - 1]) return ys[ys.length - 1];
    const i = d3.bisectRight(xs, x);           // first index with xs[i] > x
    const f = (x - xs[i - 1]) / (xs[i] - xs[i - 1]);
    return ys[i - 1] + f * (ys[i] - ys[i - 1]);
  }

  /** The value of the last sample at or before x (for on/off and gear: no in-between values exist). */
  function stepValue(x, xs, ys) {
    const i = d3.bisectRight(xs, x) - 1;
    return ys[Math.max(0, Math.min(ys.length - 1, i))];
  }

  /** Fit points into a w x h box (keeping proportions), y flipped so north is up. */
  function fitTrack(xs, ys, width, height, padding) {
    const [x0, x1] = d3.extent(xs), [y0, y1] = d3.extent(ys);
    const scale = Math.min((width - 2 * padding) / (x1 - x0), (height - 2 * padding) / (y1 - y0));
    const ox = (width - (x1 - x0) * scale) / 2, oy = (height - (y1 - y0) * scale) / 2;
    return {
      x: (x) => ox + (x - x0) * scale,
      y: (y) => height - oy - (y - y0) * scale,
      scale,
    };
  }

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  return { lapTime, signed, mix, colourDistance, getJSON, el, interp, stepValue, fitTrack, reducedMotion };
})();

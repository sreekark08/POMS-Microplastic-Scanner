/* =====================================================================
 * POMS · Team Ecosphere — frontend for the FastAPI + OpenCV backend
 *
 *   POST /update_params   { blur, threshold, min_area }
 *   POST /set_source      { source: 0 }            (webcam)
 *   POST /upload_video    multipart/form-data, field "file"
 *   GET  /stats           -> { live_count, avg_count, danger_level }
 *   GET  /video_feed      MJPEG  -> <img id="normal-feed">
 *   GET  /processed_feed  MJPEG  -> <img id="processed-feed">
 *
 * The page is served by FastAPI itself, so API_BASE_URL stays "" (same origin).
 * ===================================================================== */
const API_BASE_URL = "";
const $ = id => document.getElementById(id);
const rnd = (a, b) => a + Math.random() * (b - a);

const DEFAULTS = { blur: 3, thr: 105, area: 50 };
const STREAMS = { "normal-feed": "/video_feed", "processed-feed": "/processed_feed" };
const REC = {
  safe: { t: "Maintain current water source. No additional aggressive filtration required.", c: "var(--green)", cls: "safe", lbl: "SAFE", ic: "✔" },
  mod:  { t: "Install a 1-micron mechanical sediment filter and utilize activated carbon block filters.", c: "var(--amber)", cls: "mod", lbl: "MODERATE HAZARD", ic: "⚠" },
  crit: { t: "IMMEDIATE ACTION: Do not consume. Implement a Reverse Osmosis (RO) membrane system and sub-micron (0.1 µm) glass fiber filtration.", c: "var(--red)", cls: "crit", lbl: "CRITICAL HAZARD", ic: "☣" }
};
const S = { running: true, source: "camera", fileName: "", live: 0, avg: 0, level: "safe", online: false };

/* ---------- Helpers ---------- */
// Accepts "SAFE", "Moderate Hazard", "CRITICAL HAZARD", etc.; falls back to the average.
function normLevel(d, avg) {
  const s = String(d || "").toLowerCase();
  if (s.includes("crit")) return "crit";
  if (s.includes("mod")) return "mod";
  if (s.includes("safe")) return "safe";
  return avg < 5 ? "safe" : avg <= 20 ? "mod" : "crit";
}
// Exact FastAPI keys: blur, threshold, min_area. Blur is always forced to an odd kernel size.
function params() {
  let blur = +$("blur").value;
  if (blur % 2 === 0) blur += 1;
  return { blur, threshold: +$("thr").value, min_area: +$("area").value };
}
async function post(path, body, isForm) {
  try {
    const r = await fetch(API_BASE_URL + path, {
      method: "POST",
      headers: isForm ? {} : { "Content-Type": "application/json" },
      body: isForm ? body : JSON.stringify(body)
    });
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r;
  } catch (e) { console.warn("POMS backend:", path, e.message); }
}
function setConn(on) {
  S.online = on;
  $("conn-dot").classList.toggle("off", !on);
  $("conn-txt").textContent = on ? "Backend connected" : "Backend offline";
  $("lbl1").textContent = $("lbl2").textContent = !S.running ? "PAUSED" : on ? "LIVE STREAM" : "OFFLINE";
}

/* ---------- MJPEG streams (browser pulls them straight from FastAPI) ---------- */
function startStream(id) { $(id).src = API_BASE_URL + STREAMS[id] + "?t=" + Date.now(); }
function startStreams() { Object.keys(STREAMS).forEach(startStream); }
function stopStreams() { Object.keys(STREAMS).forEach(id => $(id).removeAttribute("src")); }
// If a stream drops (server restart, camera reconnect) retry every 3 s while running.
Object.keys(STREAMS).forEach(id => {
  $(id).onerror = () => { setConn(false); setTimeout(() => { if (S.running) startStream(id); }, 3000); };
});

/* ---------- Sliders -> POST /update_params ---------- */
function syncLabels() { $("v-blur").textContent = $("blur").value; $("v-thr").textContent = $("thr").value; $("v-area").textContent = $("area").value; }
let sendTimer;
function sendParams() { clearTimeout(sendTimer); sendTimer = setTimeout(() => post("/update_params", params()), 60); }
["blur", "thr", "area"].forEach(id => $(id).addEventListener("input", () => {
  if (id === "blur" && $("blur").value % 2 === 0) $("blur").value = +$("blur").value + 1;
  syncLabels(); sendParams();
}));
$("reset").onclick = () => {
  $("blur").value = DEFAULTS.blur; $("thr").value = DEFAULTS.thr; $("area").value = DEFAULTS.area;
  syncLabels(); post("/update_params", params());
};

/* ---------- Start / Pause: pauses the stream connections and stats polling ---------- */
$("toggle").onclick = () => {
  S.running = !S.running;
  $("toggle").innerHTML = S.running
    ? '<svg viewBox="0 0 24 24"><path d="M8 5v14M16 5v14"/></svg>Pause Scanner'
    : '<svg viewBox="0 0 24 24"><path d="M6 4l14 8-14 8z"/></svg>Start Scanner';
  $("dot").classList.toggle("off", !S.running);
  S.running ? startStreams() : stopStreams();
  setConn(S.online);
};

/* ---------- Input source ---------- */
document.querySelectorAll("input[name=src]").forEach(r => r.onchange = async () => {
  S.source = r.value;
  $("drop").classList.toggle("show", S.source === "upload");
  if (S.source === "camera") { await post("/set_source", { source: 0 }); startStreams(); }
});
const drop = $("drop");
drop.onclick = () => $("file").click();
drop.ondragover = e => { e.preventDefault(); drop.classList.add("over"); };
drop.ondragleave = () => drop.classList.remove("over");
drop.ondrop = e => { e.preventDefault(); drop.classList.remove("over"); if (e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]); };
$("file").onchange = e => e.target.files[0] && setFile(e.target.files[0]);
async function setFile(f) {
  if (!/\.(mp4|avi|mov)$/i.test(f.name)) { $("fname").textContent = "Unsupported type — use .mp4, .avi or .mov"; return; }
  S.fileName = f.name; $("fname").textContent = "Uploading " + f.name + "…";
  const fd = new FormData(); fd.append("file", f);
  const r = await post("/upload_video", fd, true);
  $("fname").textContent = r ? "✓ " + f.name : "✘ Upload failed — is the backend running?";
  if (r) startStreams();   // reconnect so the streams pick up the new video source
}

/* ---------- Live stats: GET /stats -> { live_count, avg_count, danger_level } ---------- */
setInterval(async () => {
  if (!S.running) return;
  try {
    const r = await fetch(API_BASE_URL + "/stats", { cache: "no-store" });
    if (!r.ok) throw new Error("HTTP " + r.status);
    const d = await r.json();
    S.live = +d.live_count || 0; S.avg = +d.avg_count || 0;
    S.level = normLevel(d.danger_level, S.avg);
    setConn(true); render();
  } catch (e) { setConn(false); }
}, 500);

function render() {
  const R = REC[S.level];
  const ml = $("m-live");
  if (ml.textContent != S.live) { ml.textContent = S.live; ml.classList.remove("bump"); void ml.offsetWidth; ml.classList.add("bump"); }
  $("m-avg").textContent = S.avg.toFixed(1);
  const gb = $("gauge").firstElementChild; gb.style.width = Math.min(100, S.avg / 30 * 100) + "%"; gb.style.background = R.c;
  $("m-badge").innerHTML = '<span class="ic">' + R.ic + "</span>" + R.lbl;
  $("m-badge").className = "badge " + R.cls;
  $("rec-t").textContent = R.t; $("rec").style.borderLeftColor = R.c;
}

/* ---------- Diagnostic report (.txt) ---------- */
$("dl").onclick = () => {
  const p = params(), R = REC[S.level];
  const src = S.source === "upload" ? "Uploaded video file" + (S.fileName ? " (" + S.fileName + ")" : "") : "Live camera feed (device 0)";
  const txt = [
    "==========================================",
    "  POMS DIAGNOSTIC REPORT — Team Ecosphere",
    "  Plastic Optical Microplastic Scanner",
    "==========================================",
    "Timestamp        : " + new Date().toLocaleString(),
    "Input source     : " + src,
    "",
    "--- Calibration Settings ---",
    "Gaussian Blur    : " + p.blur + " x " + p.blur + " kernel",
    "Binary Threshold : " + p.threshold,
    "Min Area         : " + p.min_area + " px²",
    "",
    "--- Results ---",
    "Instantaneous count : " + S.live,
    "30-frame average    : " + S.avg.toFixed(2),
    "Classification      : " + R.lbl,
    "",
    "--- Recommended Filtration ---",
    R.t,
    "",
    "Generated by POMS · Team Ecosphere"
  ].join("\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([txt], { type: "text/plain" }));
  a.download = "POMS_report_" + new Date().toISOString().replace(/[:.]/g, "-") + ".txt";
  a.click(); URL.revokeObjectURL(a.href);
};

/* ---------- Interactive hero particle field (decorative, independent of the streams) ---------- */
(() => {
  const cv = $("hc"), g = cv.getContext("2d"), N = 460, m = { x: -99, y: -99 };
  const q = [...Array(34)].map(() => ({ x: rnd(60, 400), y: rnd(60, 400), vx: rnd(-.5, .5), vy: rnd(-.5, .5), r: rnd(2, 6), h: rnd(0, 360), ph: rnd(0, 6) }));
  const mv = e => { const b = cv.getBoundingClientRect(), p = e.touches ? e.touches[0] : e; m.x = (p.clientX - b.left) * N / b.width; m.y = (p.clientY - b.top) * N / b.height; };
  cv.onmousemove = cv.ontouchmove = mv; cv.onmouseleave = () => { m.x = -99; };
  cv.onclick = e => { mv(e); for (let i = 0; i < 6; i++) q.push({ x: m.x, y: m.y, vx: rnd(-2, 2), vy: rnd(-2, 2), r: rnd(2, 6), h: rnd(0, 360), ph: 0 }); while (q.length > 90) q.shift(); };
  (function f(t) {
    g.fillStyle = "#0B192C"; g.fillRect(0, 0, N, N); g.strokeStyle = "#243B55"; g.lineWidth = 1;
    for (let r = 60; r <= 220; r += 40) { g.beginPath(); g.arc(230, 230, r, 0, 6.28); g.stroke(); }
    g.beginPath(); g.moveTo(230, 10); g.lineTo(230, 450); g.moveTo(10, 230); g.lineTo(450, 230); g.stroke();
    const a = t / 2500; g.strokeStyle = "rgba(226,217,200,.4)"; g.beginPath();
    g.moveTo(230 + Math.cos(a) * 220, 230 + Math.sin(a) * 220); g.lineTo(230 - Math.cos(a) * 220, 230 - Math.sin(a) * 220); g.stroke();
    for (const p of q) {
      const dx = p.x - m.x, dy = p.y - m.y, d = Math.hypot(dx, dy) || 1;
      if (d < 90) { p.vx += dx / d * .12; p.vy += dy / d * .12; }
      p.vx = p.vx * .99 + rnd(-.03, .03); p.vy = p.vy * .99 + rnd(-.03, .03); p.x += p.vx; p.y += p.vy;
      const cx = p.x - 230, cy = p.y - 230, dd = Math.hypot(cx, cy); if (dd > 210) { p.vx -= cx / dd * .3; p.vy -= cy / dd * .3; }
      const gl = p.r * (3 + Math.sin(t / 300 + p.ph)) + (d < 90 ? 10 : 0), gr = g.createRadialGradient(p.x, p.y, 0, p.x, p.y, gl);
      gr.addColorStop(0, "#FAF6EE"); gr.addColorStop(.35, `hsla(${200 + p.h / 8},70%,75%,.55)`); gr.addColorStop(1, "rgba(11,25,44,0)");
      g.fillStyle = gr; g.beginPath(); g.arc(p.x, p.y, gl, 0, 6.28); g.fill();
      if (d < 90) { g.strokeStyle = "#3ddc84"; g.strokeRect(p.x - p.r - 5, p.y - p.r - 5, 2 * p.r + 10, 2 * p.r + 10); }
    }
    requestAnimationFrame(f);
  })(0);
})();

/* ---------- Icon chips + reveal-on-scroll ---------- */
document.querySelectorAll(".chip").forEach(c => c.onclick = () => {
  document.querySelectorAll(".chip").forEach(x => x.classList.remove("on"));
  c.classList.add("on"); $("chipinfo").textContent = c.dataset.t;
});
const io = new IntersectionObserver(es => es.forEach(e => e.isIntersecting && e.target.classList.add("in")), { threshold: .1 });
document.querySelectorAll(".step,.chips,.panel,.scr,.card").forEach(el => { el.classList.add("rv"); io.observe(el); });

/* ---------- Boot: push the slider values to the backend so both start in sync ---------- */
syncLabels(); render(); setConn(false);
post("/update_params", params());

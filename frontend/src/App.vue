<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import {
  Activity, Bot, BrainCircuit, History, LoaderCircle,
  Mic, MicOff, PlugZap, Radar, RefreshCw, Send,
  Trash2, Volume2, VolumeX, Wifi, WifiOff,
} from "lucide-vue-next";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const WS_BASE  = API_BASE.replace(/^http/, "ws");
const STORAGE_KEY = "jarvis.chat.history.v9";

const input    = ref("");
const messages = ref(loadLocalHistory());
const tools    = ref([]);
const health   = ref(null);
const ws       = ref(null);
const connected   = ref(false);
const connecting  = ref(false);
const typing      = ref(false);
const sending     = ref(false);
const streamId    = ref(null);
const streamText  = ref("");
const recognition = ref(null);
const micState    = ref("idle");
const micError    = ref("");
const panel       = ref("chat");
const chatScroll  = ref(null);
const reminderPollInterval = ref(null);
const voiceEnabled = ref(true);
const coreState    = ref("idle");
const canvasRef    = ref(null);

let animCtx = null;

const canSend = computed(() => input.value.trim().length > 0 && !sending.value);
const connectionLabel = computed(() => {
  if (connected.value) return "WebSocket activo";
  if (connecting.value) return "Conectando";
  return "REST listo";
});
const micLabel = computed(() => {
  if (micState.value === "listening") return "Escuchando";
  if (micState.value === "unsupported") return "No disponible";
  if (micState.value === "error") return "Error de microfono";
  return "Microfono listo";
});
const userCount      = computed(() => messages.value.filter(m => m.role === "user").length);
const assistantCount = computed(() => messages.value.filter(m => m.role === "assistant").length);

// ══════════════════════════════════════════════════════════════════
//  JARVIS CORE — Canvas 2D "Fractal Orbital City"
//  Objetivo: replicar la imagen de referencia:
//    • Anillo exterior oscuro y sólido (como una esfera contenedora)
//    • Masa densa de fragmentos angulares tipo ciudad/circuito en órbita
//    • Filamentos de luz que irradian desde el centro
//    • Luz dorada concentrada en el núcleo, oscuridad en el borde
// ══════════════════════════════════════════════════════════════════
function initJarvisCore() {
  const canvas = canvasRef.value;
  if (!canvas) return;
  const ctx = canvas.getContext("2d");

  let W, H, cx, cy, R;
  let t = 0;
  let raf;
  let currentState = "idle";

  // ── Seed aleatoria fija para que los fragmentos no cambien en resize ──
  let rngSeed = 42;
  function rng() {
    rngSeed = (rngSeed * 1664525 + 1013904223) & 0xffffffff;
    return (rngSeed >>> 0) / 0xffffffff;
  }

  function resize() {
    W = canvas.width  = window.innerWidth;
    H = canvas.height = window.innerHeight;
    cx = W / 2;
    cy = H / 2;
    R  = Math.min(W, H) * 0.40;
    rngSeed = 42; // reset para reproducibilidad
    buildAll();
  }

  // ─────────────────────────────────────────────────
  //  CAPA 1 — Fragmentos estructurales (el "polvo de ciudad")
  //  Segmentos angulares agrupados en clusters orbitales
  // ─────────────────────────────────────────────────
  const CLUSTERS = [];

  function buildAll() {
    CLUSTERS.length = 0;

    // Zona de fragmentos: 0.35R … 1.05R (justo como la imagen)
    const CLUSTER_COUNT = 420;
    for (let i = 0; i < CLUSTER_COUNT; i++) {
      // Distribución radial con más densidad en el borde del anillo (~0.7-0.95R)
      const u   = rng();
      const rad = R * (0.32 + 0.78 * Math.pow(u, 0.55));

      const ang  = rng() * Math.PI * 2;
      const spd  = (0.00018 + rng() * 0.00055) * (rng() > 0.5 ? 1 : -1);

      // Cada cluster tiene 2–6 segmentos interconectados
      const segCount = 2 + Math.floor(rng() * 5);
      const segs = [];
      let ox = 0, oy = 0;
      for (let s = 0; s < segCount; s++) {
        const len   = R * (0.015 + rng() * 0.065);
        const dir   = rng() * Math.PI * 2;
        const nx    = ox + Math.cos(dir) * len;
        const ny    = oy + Math.sin(dir) * len;
        const thick = 0.4 + rng() * 2.2;
        // Brillo inversamente proporcional al radio (más brillante cerca del centro)
        const brightness = Math.max(0, 1.0 - (rad / R) * 0.7) + rng() * 0.3;
        // Hue en el espectro ámbar-dorado (20–48°)
        const hue = 18 + rng() * 32;
        const sat = 80 + rng() * 20;
        const lum = 40 + brightness * 50;
        segs.push({ x0: ox, y0: oy, x1: nx, y1: ny, thick, hue, sat, lum, brightness });
        ox = nx; oy = ny;
      }

      CLUSTERS.push({ ang, rad, spd, segs,
        // Pequeña oscilación radial
        drAmp: rng() * R * 0.03,
        drPha: rng() * Math.PI * 2,
        // Opacidad base según profundidad simulada
        baseAlpha: 0.35 + rng() * 0.65,
      });
    }
  }

  // ─────────────────────────────────────────────────
  //  CAPA 2 — Filamentos de luz (los "rayos" desde el centro)
  // ─────────────────────────────────────────────────
  const FILAMENTS = [];
  function buildFilaments() {
    FILAMENTS.length = 0;
    for (let i = 0; i < 28; i++) {
      const ang    = rng() * Math.PI * 2;
      const len    = R * (0.28 + rng() * 0.55);
      const width  = 0.5 + rng() * 2.5;
      const spd    = (0.00008 + rng() * 0.00025) * (rng() > 0.5 ? 1 : -1);
      const bright = 0.3 + rng() * 0.7;
      const curve  = (rng() - 0.5) * 0.6; // curvatura del filamento
      FILAMENTS.push({ ang, len, width, spd, bright, curve });
    }
  }

  // ─────────────────────────────────────────────────
  //  CAPA 3 — Anillo exterior oscuro sólido (el "shell")
  //  Como en la imagen: borde negro mate que da profundidad
  // ─────────────────────────────────────────────────
  function drawShell() {
    // Cara interior del shell (oscurece el borde exterior)
    const g = ctx.createRadialGradient(cx, cy, R * 0.72, cx, cy, R * 1.08);
    g.addColorStop(0,    "rgba(0,0,0,0)");
    g.addColorStop(0.45, "rgba(0,0,0,0.45)");
    g.addColorStop(0.75, "rgba(0,0,0,0.78)");
    g.addColorStop(1,    "rgba(0,0,0,0.96)");
    ctx.beginPath();
    ctx.arc(cx, cy, R * 1.08, 0, Math.PI * 2);
    ctx.fillStyle = g;
    ctx.fill();

    // Contorno exterior negro (la silueta circular)
    ctx.beginPath();
    ctx.arc(cx, cy, R * 1.06, 0, Math.PI * 2);
    ctx.strokeStyle = "rgba(0,0,0,0.98)";
    ctx.lineWidth   = R * 0.05;
    ctx.stroke();

    // Anillo de borde interior (fina línea dorada)
    ctx.beginPath();
    ctx.arc(cx, cy, R, 0, Math.PI * 2);
    ctx.strokeStyle = "rgba(100,50,5,0.45)";
    ctx.lineWidth   = 1.2;
    ctx.stroke();
  }

  // ─────────────────────────────────────────────────
  //  CAPA 4 — Luz central (el núcleo brillante)
  // ─────────────────────────────────────────────────
  function drawCentralGlow(mult) {
    const pulse = 1 + Math.sin(t * 2.2) * 0.07;

    // Halo exterior amplio
    const g1 = ctx.createRadialGradient(cx, cy, 0, cx, cy, R * 0.62 * pulse);
    g1.addColorStop(0,    `rgba(255,240,150,${0.50 * mult})`);
    g1.addColorStop(0.08, `rgba(255,200,60,${0.42 * mult})`);
    g1.addColorStop(0.22, `rgba(255,130,15,${0.28 * mult})`);
    g1.addColorStop(0.50, `rgba(200,70,5,${0.12 * mult})`);
    g1.addColorStop(0.80, `rgba(120,35,2,${0.05 * mult})`);
    g1.addColorStop(1,    "rgba(0,0,0,0)");
    ctx.beginPath();
    ctx.arc(cx, cy, R * 0.62 * pulse, 0, Math.PI * 2);
    ctx.fillStyle = g1;
    ctx.fill();

    // Punto caliente central muy brillante
    const g2 = ctx.createRadialGradient(cx, cy, 0, cx, cy, R * 0.10 * pulse);
    g2.addColorStop(0,   `rgba(255,255,220,${0.98 * mult})`);
    g2.addColorStop(0.25,`rgba(255,230,100,${0.90 * mult})`);
    g2.addColorStop(0.60,`rgba(255,160,30,${0.60 * mult})`);
    g2.addColorStop(1,   "rgba(255,80,0,0)");
    ctx.beginPath();
    ctx.arc(cx, cy, R * 0.10 * pulse, 0, Math.PI * 2);
    ctx.fillStyle = g2;
    ctx.fill();

    // Los 3 loops internos de energía del núcleo (como la imagen)
    ctx.save();
    for (let i = 0; i < 3; i++) {
      const a0 = t * (0.22 + i * 0.09) + i * 1.1;
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(a0);
      ctx.scale(1, 0.28 + i * 0.07);
      ctx.beginPath();
      ctx.arc(0, 0, R * (0.14 + i * 0.055), 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(255,${150 + i*20},${20+i*10},${(0.55 - i*0.12) * mult})`;
      ctx.lineWidth   = 1.8 - i * 0.4;
      ctx.stroke();
      ctx.restore();
    }
    ctx.restore();
  }

  // ─────────────────────────────────────────────────
  //  CAPA 5 — Filamentos de luz que irradian del centro
  // ─────────────────────────────────────────────────
  function drawFilaments(mult) {
    for (let i = 0; i < FILAMENTS.length; i++) {
      const f  = FILAMENTS[i];
      f.ang   += f.spd;
      const x0 = cx;
      const y0 = cy;
      const x1 = cx + Math.cos(f.ang) * f.len;
      const y1 = cy + Math.sin(f.ang) * f.len;

      const grad = ctx.createLinearGradient(x0, y0, x1, y1);
      grad.addColorStop(0,   `rgba(255,200,80,${f.bright * 0.6 * mult})`);
      grad.addColorStop(0.4, `rgba(255,130,20,${f.bright * 0.3 * mult})`);
      grad.addColorStop(1,   "rgba(200,80,5,0)");

      // Curvatura simulada con quadraticCurveTo
      const cpx = cx + Math.cos(f.ang + f.curve) * f.len * 0.5;
      const cpy = cy + Math.sin(f.ang + f.curve) * f.len * 0.5;

      ctx.beginPath();
      ctx.moveTo(x0, y0);
      ctx.quadraticCurveTo(cpx, cpy, x1, y1);
      ctx.strokeStyle = grad;
      ctx.lineWidth   = f.width;
      ctx.stroke();
    }
  }

  // ─────────────────────────────────────────────────
  //  CAPA 6 — Fragmentos orbitales (masa principal)
  // ─────────────────────────────────────────────────
  function drawClusters(speedMult, alphaMult) {
    for (let i = 0; i < CLUSTERS.length; i++) {
      const c  = CLUSTERS[i];
      c.ang   += c.spd * speedMult;

      const dr = Math.sin(t * 1.2 + c.drPha) * c.drAmp;
      const r  = c.rad + dr;
      const bx = cx + Math.cos(c.ang) * r;
      const by = cy + Math.sin(c.ang) * r;

      // Opacidad de profundidad: más opaco en el lado "frontal" del órbita
      const depthFade = 0.45 + 0.55 * (0.5 + 0.5 * Math.cos(c.ang - t * 0.25));
      const alpha     = c.baseAlpha * depthFade * alphaMult;

      ctx.save();
      ctx.translate(bx, by);
      ctx.rotate(c.ang + t * 0.08); // los clusters rotan sobre sí mismos muy lento

      for (let s = 0; s < c.segs.length; s++) {
        const sg = c.segs[s];
        const a  = sg.brightness * alpha;
        ctx.beginPath();
        ctx.moveTo(sg.x0, sg.y0);
        ctx.lineTo(sg.x1, sg.y1);
        ctx.strokeStyle = `hsla(${sg.hue},${sg.sat}%,${sg.lum}%,${a})`;
        ctx.lineWidth   = sg.thick;
        ctx.stroke();
      }
      ctx.restore();
    }
  }

  // ─────────────────────────────────────────────────
  //  CAPA 7 — Tinte de estado (listening/speaking)
  // ─────────────────────────────────────────────────
  function drawStateTint() {
    if (currentState === "idle") return;
    const pulse = 0.5 + 0.5 * Math.sin(t * (currentState === "listening" ? 5 : 3.5));
    const col   = currentState === "listening"
      ? `rgba(46,234,255,${0.08 * pulse})`
      : `rgba(255,220,60,${0.10 * pulse})`;
    const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, R * 0.9);
    g.addColorStop(0,   col);
    g.addColorStop(0.5, col);
    g.addColorStop(1,   "rgba(0,0,0,0)");
    ctx.beginPath();
    ctx.arc(cx, cy, R * 0.9, 0, Math.PI * 2);
    ctx.fillStyle = g;
    ctx.fill();
  }

  // ─────────────────────────────────────────────────
  //  CAPA 8 — HUD decorativo (esquinas, marcas, etiquetas)
  // ─────────────────────────────────────────────────
  function drawHUD() {
    const col  = "rgba(140,70,8,0.30)";
    const col2 = "rgba(180,90,15,0.22)";
    ctx.strokeStyle = col;
    ctx.lineWidth   = 1;

    // Barra superior
    const bw = R * 0.55;
    ctx.beginPath();
    ctx.moveTo(cx - bw, cy - R * 1.16);
    ctx.lineTo(cx + bw * 0.6, cy - R * 1.16);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(cx - bw, cy - R * 1.16);
    ctx.lineTo(cx - bw, cy - R * 1.12);
    ctx.stroke();

    // Bloque derecho de la barra superior
    ctx.fillStyle = col2;
    ctx.fillRect(cx + bw * 0.65, cy - R * 1.175, R * 0.12, R * 0.028);

    // Línea vertical derecha
    const rx = cx + R * 1.14; const ry1 = cy - R * 0.55; const ry2 = cy + R * 0.2;
    ctx.beginPath();
    ctx.moveTo(rx, ry1); ctx.lineTo(rx, ry2); ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(rx, ry2); ctx.lineTo(rx - R * 0.06, ry2); ctx.stroke();

    // Línea vertical inferior derecha
    const rx2 = cx + R * 1.18; const ry3 = cy + R * 0.55;
    ctx.beginPath();
    ctx.moveTo(rx2, ry3); ctx.lineTo(rx2, ry3 + R * 0.25); ctx.stroke();

    // Mini engranaje
    const gx = cx + R * 1.10; const gy = cy + R * 1.04; const gr = R * 0.027;
    ctx.beginPath(); ctx.arc(gx, gy, gr, 0, Math.PI*2);
    ctx.strokeStyle = "rgba(180,90,15,0.28)"; ctx.lineWidth = 1; ctx.stroke();
    for (let i = 0; i < 8; i++) {
      const ga = (i / 8) * Math.PI * 2 + t * 0.45;
      ctx.beginPath();
      ctx.moveTo(gx + Math.cos(ga)*gr, gy + Math.sin(ga)*gr);
      ctx.lineTo(gx + Math.cos(ga)*gr*1.7, gy + Math.sin(ga)*gr*1.7);
      ctx.stroke();
    }

    // Marcas del anillo exterior (como un medidor)
    for (let i = 0; i < 90; i++) {
      const a     = (i / 90) * Math.PI * 2 + t * 0.015;
      const isBig = i % 9 === 0;
      const r0    = R * 1.02;
      const r1    = r0 + (isBig ? R * 0.045 : R * 0.018);
      ctx.beginPath();
      ctx.moveTo(cx + Math.cos(a)*r0, cy + Math.sin(a)*r0);
      ctx.lineTo(cx + Math.cos(a)*r1, cy + Math.sin(a)*r1);
      ctx.strokeStyle = isBig ? "rgba(160,80,10,0.40)" : "rgba(120,55,5,0.20)";
      ctx.lineWidth   = isBig ? 1.5 : 0.7;
      ctx.stroke();
    }
  }

  // ─────────────────────────────────────────────────
  //  LOOP PRINCIPAL
  // ─────────────────────────────────────────────────
  function getSpeedMult() {
    if (currentState === "listening") return 3.2;
    if (currentState === "speaking")  return 2.2;
    return 1.0;
  }

  function loop() {
    raf = requestAnimationFrame(loop);
    t  += 0.005;

    // Motion blur suave — el rastro largo da aspecto de movimiento real
    ctx.fillStyle = "rgba(1,2,4,0.32)";
    ctx.fillRect(0, 0, W, H);

    const spd = getSpeedMult();

    // Orden de capas (de fondo a frente):
    drawStateTint();      // tinte de estado
    drawFilaments(1.0);   // rayos del centro
    drawClusters(spd, 1.0); // fragmentos orbitales
    drawCentralGlow(1.0); // luz central encima de los fragmentos
    drawShell();          // shell oscuro tapa el exterior (encima de todo)
    drawHUD();            // decoración HUD (encima del shell)
  }

  resize();
  window.addEventListener("resize", resize);
  buildFilaments();
  loop();

  animCtx = {
    setState: (s) => { currentState = s; },
    cleanup:  () => { cancelAnimationFrame(raf); window.removeEventListener("resize", resize); }
  };
}

watch(coreState, (val) => animCtx?.setState(val));

// ─────────────────────────────────────────────────────────────────
onMounted(async () => {
  await nextTick();
  initJarvisCore();
  setupSpeechRecognition();
  await refreshBackendState();
  connectWebSocket();
  startReminderPolling();
  setTimeout(() => {
    speakText("Hola señor, ¿cómo está? Estoy listo para ayudarlo el día de hoy.");
  }, 1500);
});

onBeforeUnmount(() => {
  ws.value?.close();
  recognition.value?.abort?.();
  if (reminderPollInterval.value) clearInterval(reminderPollInterval.value);
  animCtx?.cleanup();
});

watch(messages, () => {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(messages.value.slice(-80)));
  nextTick(scrollToBottom);
}, { deep: true });

function loadLocalHistory() {
  try {
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    return Array.isArray(stored) && stored.length ? stored : [welcomeMessage()];
  } catch { return [welcomeMessage()]; }
}
function welcomeMessage() {
  return { id: crypto.randomUUID(), role: "assistant", content: "Sistema JARVIS inicializado. Canal de asistencia listo.", time: new Date().toISOString() };
}

async function refreshBackendState() {
  try {
    const [h, t2, m] = await Promise.all([
      fetch(`${API_BASE}/health`),
      fetch(`${API_BASE}/tools`),
      fetch(`${API_BASE}/memory?n=12`),
    ]);
    health.value = await h.json();
    tools.value  = (await t2.json()).tools || [];
    const mem    = await m.json();
    const hist   = (mem.conversation || []).map(i => ({ id: crypto.randomUUID(), role: i.role || i.source || "assistant", content: i.content, time: new Date().toISOString() }));
    if (hist.length && messages.value.length <= 1) messages.value = hist;
  } catch (e) { health.value = { status: "offline", llm: "sin conexion", error: e.message }; }
}

function connectWebSocket() {
  if (ws.value && [WebSocket.OPEN, WebSocket.CONNECTING].includes(ws.value.readyState)) return;
  connecting.value = true;
  const socket = new WebSocket(`${WS_BASE}/ws/chat`);
  ws.value = socket;
  socket.onopen    = () => { connected.value = true;  connecting.value = false; };
  socket.onmessage = e  => { handleSocketPayload(JSON.parse(e.data)); };
  socket.onerror   = () => { connected.value = false; connecting.value = false; };
  socket.onclose   = () => { connected.value = false; connecting.value = false; };
}

async function handleSocketPayload(p) {
  if (p.type === "status") health.value = { ...(health.value||{}), status: p.status, llm: p.llm, tools: p.tools };
  if (p.type === "typing") typing.value = p.active;
  if (p.type === "chunk")  { streamText.value += p.content; updateStreamingMessage(streamText.value); }
  if (p.type === "done")   { finalizeStreamingMessage(p.message?.content || streamText.value, p.message?.tool_used, p.message?.tool_success ?? null, p.message?.tool_output ?? null); if (p.message?.tool_used) await refreshBackendState(); }
  if (p.type === "error")  { finalizeStreamingMessage(p.message || "No pude completar la respuesta."); }
}

function pushMessage(role, content, extra = {}) {
  const m = { id: crypto.randomUUID(), role, content, time: new Date().toISOString(), ...extra };
  messages.value.push(m);
  return m;
}
function createStreamingMessage() {
  const item = pushMessage("assistant", "", { streaming: true });
  streamId.value = item.id;
  streamText.value = "";
}
function updateStreamingMessage(content) {
  const item = messages.value.find(m => m.id === streamId.value);
  if (item) item.content = content;
}
function finalizeStreamingMessage(content, toolUsed = null, toolSuccess = null, toolOutput = null) {
  const item = messages.value.find(m => m.id === streamId.value);
  if (item) { item.content = content; item.streaming = false; item.toolUsed = toolUsed; item.toolSuccess = toolSuccess; item.toolOutput = toolOutput; }
  else { pushMessage("assistant", content, { toolUsed, toolSuccess, toolOutput }); }
  speakText(content);
  sending.value = false; typing.value = false; streamId.value = null; streamText.value = "";
}

async function sendMessage() {
  const text = input.value.trim();
  if (!text || sending.value) return;
  pushMessage("user", text);
  input.value = ""; sending.value = true;
  createStreamingMessage();
  if (connected.value && ws.value?.readyState === WebSocket.OPEN) { ws.value.send(JSON.stringify({ message: text })); return; }
  await sendWithRest(text);
}

async function sendWithRest(text) {
  try {
    typing.value = true;
    const res  = await fetch(`${API_BASE}/chat`, { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({ message: text }) });
    if (!res.ok) { const d = await res.json().catch(()=>({})); throw new Error(d.detail || "Error de backend"); }
    const data = await res.json();
    finalizeStreamingMessage(data.response, data.tool_used, data.success, null);
  } catch (e) { finalizeStreamingMessage(`Error: ${e.message}`); }
}

function startReminderPolling() {
  const poll = async () => {
    try {
      const res  = await fetch(`${API_BASE}/reminders/alerts`);
      const data = await res.json();
      (data.alerts || []).forEach(a => {
        const msg = `Recordatorio: ${a.message}`;
        pushMessage("assistant", msg, { toolUsed: "reminder", toolSuccess: true, toolOutput: msg });
        speakText(`Recordatorio: ${a.message}`);
      });
    } catch (_) {}
  };
  poll();
  reminderPollInterval.value = setInterval(poll, 60000);
}

function setupSpeechRecognition() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) { micState.value = "unsupported"; return; }
  const rec = new SR();
  rec.lang = "es-CO"; rec.continuous = false; rec.interimResults = false;
  rec.onstart  = () => { micState.value = "listening"; coreState.value = "listening"; micError.value = ""; };
  rec.onresult = e  => { const tx = Array.from(e.results).map(r => r[0].transcript).join("").trim(); if (tx) { input.value = tx; sendMessage(); } };
  rec.onerror  = e  => { micState.value = "error"; micError.value = e.error; coreState.value = "idle"; };
  rec.onend    = ()  => { if (micState.value === "listening") { micState.value = "idle"; coreState.value = "idle"; } };
  recognition.value = rec;
}

function toggleMic() {
  if (!recognition.value) return;
  if (micState.value === "listening") { recognition.value.stop(); micState.value = "idle"; coreState.value = "idle"; return; }
  recognition.value.start();
}

async function speakText(text) {
  if (!voiceEnabled.value || !text?.trim()) return;
  coreState.value = "speaking";
  try { await fetch(`${API_BASE}/tts/speak`, { method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({ text }) }); } catch (_) {}
  setTimeout(() => { if (coreState.value === "speaking") coreState.value = "idle"; }, 4000);
}

function toggleVoice() {
  voiceEnabled.value = !voiceEnabled.value;
  if (!voiceEnabled.value) fetch(`${API_BASE}/tts/stop`, { method:"POST" }).catch(()=>{});
}

function clearHistory() { messages.value = [welcomeMessage()]; }
function scrollToBottom() { if (chatScroll.value) chatScroll.value.scrollTop = chatScroll.value.scrollHeight; }
function formatTime(v) { return new Intl.DateTimeFormat("es-CO", { hour:"2-digit", minute:"2-digit" }).format(new Date(v)); }
</script>

<template>
  <main class="shell">
    <div class="bg-scanlines"></div>

    <!-- NÚCLEO — canvas ocupa toda la pantalla de fondo -->
    <canvas ref="canvasRef" class="jarvis-canvas"></canvas>

    <!-- HUD del estado -->
    <div class="core-hud" :class="coreState">
      <span v-if="coreState === 'listening'">◈ &nbsp;ESCUCHANDO</span>
      <span v-else-if="coreState === 'speaking'">◈ &nbsp;RESPONDIENDO</span>
      <span v-else>J · A · R · V · I · S</span>
    </div>

    <!-- SIDEBAR IZQUIERDO -->
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark"><Bot :size="18" /></div>
        <div><h1>JARVIS</h1><p>Virtual assistant</p></div>
      </div>

      <div class="section-title">Sistema</div>
      <div class="status-grid">
        <article class="metric">
          <Wifi v-if="connected" :size="12" /><WifiOff v-else :size="12" />
          <span>{{ connectionLabel }}</span>
        </article>
        <article class="metric"><BrainCircuit :size="12" /><span>{{ health?.llm || "sin LLM" }}</span></article>
        <article class="metric"><Radar :size="12" /><span>{{ tools.length || 0 }} herramientas</span></article>
        <article class="metric"><Activity :size="12" /><span>{{ health?.status || "cargando" }}</span></article>
      </div>

      <div class="panel-switch">
        <button :class="{ active: panel === 'chat' }"    @click="panel = 'chat'"><Bot :size="11" /> Chat</button>
        <button :class="{ active: panel === 'history' }" @click="panel = 'history'"><History :size="11" /> Historial</button>
      </div>

      <div class="section-title">Herramientas</div>
      <div class="tools-list">
        <div v-for="tool in tools" :key="tool.name" class="tool-item">
          <span>{{ tool.name }}</span>
          <small>{{ tool.description }}</small>
        </div>
      </div>
    </aside>

    <!-- WORKSPACE — transparente, el núcleo se ve detrás -->
    <section class="workspace">
      <header class="topbar">
        <div>
          <span class="eyebrow">Sistema activo</span>
          <h2>Chat neural</h2>
        </div>
        <div class="top-actions">
          <button class="icon-button" @click="refreshBackendState" title="Actualizar"><RefreshCw :size="12" /></button>
          <button class="icon-button" @click="connectWebSocket"    title="Reconectar"><PlugZap   :size="12" /></button>
          <button class="icon-button" @click="toggleVoice" :title="voiceEnabled ? 'Silenciar' : 'Activar voz'">
            <Volume2 v-if="voiceEnabled" :size="12" /><VolumeX v-else :size="12" />
          </button>
          <button class="icon-button danger" @click="clearHistory" title="Limpiar"><Trash2 :size="12" /></button>
        </div>
      </header>

      <div v-if="panel === 'chat'" ref="chatScroll" class="chat-window">
        <article v-for="message in messages" :key="message.id"
          class="message" :class="[message.role, { streaming: message.streaming }]">
          <div class="avatar">
            <Bot v-if="message.role === 'assistant'" :size="12" />
            <span v-else>U</span>
          </div>
          <div class="bubble">
            <div class="meta">
              <span>{{ message.role === "assistant" ? "JARVIS" : "Usuario" }}</span>
              <time>{{ formatTime(message.time) }}</time>
            </div>
            <p>{{ message.content }}</p>
            <div v-if="message.toolUsed" class="tool-badge"
              :class="{ 'tool-ok': message.toolSuccess, 'tool-fail': message.toolSuccess === false }">
              <span>{{ message.toolSuccess ? '✦' : '✕' }} {{ message.toolUsed }}</span>
              <span v-if="message.toolOutput" class="tool-output">{{ message.toolOutput.slice(0,100) }}</span>
            </div>
          </div>
        </article>
        <div v-if="typing" class="typing"><LoaderCircle :size="12" /><span>Procesando señal...</span></div>
      </div>

      <div v-else class="history-panel">
        <article class="history-card"><span>{{ userCount }}</span><p>Enviados</p></article>
        <article class="history-card"><span>{{ assistantCount }}</span><p>Recibidos</p></article>
        <article v-for="message in messages.slice().reverse()" :key="message.id" class="history-row">
          <strong>{{ message.role === "assistant" ? "JARVIS" : "Usuario" }}</strong>
          <span>{{ message.content }}</span>
        </article>
      </div>

      <footer class="composer">
        <div class="mic-state" :class="micState">
          <span class="dot"></span>{{ micLabel }}
          <small v-if="micError">{{ micError }}</small>
        </div>
        <div class="input-row">
          <button class="mic-button" :class="{ active: micState === 'listening' }" @click="toggleMic">
            <MicOff v-if="micState === 'unsupported'" :size="14" /><Mic v-else :size="14" />
          </button>
          <textarea v-model="input" rows="1" placeholder="Escribe o dicta una orden para Jarvis..."
            @keydown.enter.exact.prevent="sendMessage"></textarea>
          <button class="send-button" :disabled="!canSend" @click="sendMessage"><Send :size="14" /></button>
        </div>
      </footer>
    </section>
  </main>
</template>
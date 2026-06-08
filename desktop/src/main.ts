import { register } from "@tauri-apps/plugin-global-shortcut";
import { isPermissionGranted, requestPermission, sendNotification } from "@tauri-apps/plugin-notification";
import { Activity, Bell, Bot, Brain, Mic, MicOff, Radio, Send, Settings, Sparkles, Zap } from "lucide";
import "./styles.css";

type Envelope = { type: string; payload: Record<string, unknown>; ts?: string };
type ChatItem = { role: "user" | "assistant" | "system"; text: string; meta?: string };

const API = "http://127.0.0.1:8000";
const WS = "ws://127.0.0.1:8000/ws";

const state = {
  connected: false,
  status: "starting",
  listening: false,
  wakeWordEnabled: true,
  wakeWord: "jarvis",
  voiceEngine: "unavailable",
  llm: "not configured",
  chat: [
    {
      role: "assistant",
      text: "Sistema de escritorio iniciado. Esperando enlace con el nucleo local.",
      meta: "Jarvis"
    }
  ] as ChatItem[],
  events: [] as Envelope[]
};

const app = document.querySelector<HTMLElement>("#app");
let socket: WebSocket | null = null;
let reconnectTimer: number | undefined;

function icon(name: string, size = 18) {
  const icons = { Activity, Bell, Bot, Brain, Mic, MicOff, Radio, Send, Settings, Sparkles, Zap };
  const node = icons[name as keyof typeof icons] as unknown as [string, Record<string, string>, [string, Record<string, string>][]] | undefined;
  if (!node) return "";
  const [, attrs, children] = node;
  const attrText = attrsToText({ ...attrs, width: String(size), height: String(size), "stroke-width": "1.8" });
  const childText = children.map(([tag, childAttrs]) => `<${tag} ${attrsToText(childAttrs)}></${tag}>`).join("");
  return `<svg ${attrText}>${childText}</svg>`;
}

function attrsToText(attrs: Record<string, string>) {
  return Object.entries(attrs)
    .map(([key, value]) => `${key}="${escapeHtml(String(value))}"`)
    .join(" ");
}

function render() {
  if (!app) return;
  const statusClass = state.connected ? "online" : "offline";
  const listenLabel = state.listening ? "Escuchando" : "Pausado";
  const micIcon = state.listening ? icon("Mic", 22) : icon("MicOff", 22);

  app.innerHTML = `
    <section class="shell">
      <aside class="left-rail">
        <div class="mark">${icon("Bot", 26)}</div>
        <button class="rail-btn active" title="Comando">${icon("Sparkles", 20)}</button>
        <button class="rail-btn" title="Estado">${icon("Activity", 20)}</button>
        <button class="rail-btn" title="Ajustes">${icon("Settings", 20)}</button>
      </aside>

      <section class="orb-panel">
        <div class="topline">
          <span class="status-dot ${statusClass}"></span>
          <span>${state.connected ? "Nucleo enlazado" : "Reconectando nucleo"}</span>
        </div>
        <div class="assistant-orb ${state.listening ? "listening" : ""}">
          <div class="orb-core">${micIcon}</div>
          <div class="ring ring-a"></div>
          <div class="ring ring-b"></div>
          <div class="ring ring-c"></div>
        </div>
        <h1>JARVIS</h1>
        <p class="subtitle">Asistente local activo con voz, WebSocket y acceso de escritorio.</p>
        <div class="control-row">
          <button id="toggleListen" class="primary">${micIcon}<span>${listenLabel}</span></button>
          <button id="notify" title="Probar notificacion">${icon("Bell", 18)}</button>
        </div>
        <div class="metrics">
          <div><span>Motor voz</span><strong>${state.voiceEngine}</strong></div>
          <div><span>Wake word</span><strong>${state.wakeWordEnabled ? state.wakeWord : "off"}</strong></div>
          <div><span>Modelo</span><strong>${state.llm}</strong></div>
        </div>
      </section>

      <section class="workspace">
        <header class="command-header">
          <div>
            <span class="eyebrow">${icon("Radio", 15)} Streaming en vivo</span>
            <h2>Centro de mando</h2>
          </div>
          <div class="pulse ${state.status}">${state.status}</div>
        </header>

        <section id="conversation" class="conversation">
          ${state.chat.map((item) => `
            <article class="message ${item.role}">
              <span>${item.meta ?? item.role}</span>
              <p>${escapeHtml(item.text)}</p>
            </article>
          `).join("")}
        </section>

        <form id="chatForm" class="composer">
          <input id="message" autocomplete="off" placeholder="Pide algo a Jarvis..." />
          <button title="Enviar">${icon("Send", 18)}</button>
        </form>
      </section>

      <aside class="right-panel">
        <div class="panel-head">${icon("Brain", 19)} Telemetria</div>
        <div class="switch-row">
          <span>Wake word real</span>
          <label class="switch">
            <input id="wakeSwitch" type="checkbox" ${state.wakeWordEnabled ? "checked" : ""} />
            <i></i>
          </label>
        </div>
        <label class="field">
          <span>Palabra</span>
          <input id="wakeWord" value="${escapeHtml(state.wakeWord)}" />
        </label>
        <div class="event-list">
          ${state.events.slice(0, 8).map((event) => `
            <div class="event">
              <strong>${escapeHtml(event.type)}</strong>
              <span>${escapeHtml(JSON.stringify(event.payload).slice(0, 90))}</span>
            </div>
          `).join("")}
        </div>
      </aside>
    </section>
  `;

  bindUi();
  const conversation = document.querySelector("#conversation");
  conversation?.scrollTo({ top: conversation.scrollHeight });
}

function bindUi() {
  document.querySelector("#toggleListen")?.addEventListener("click", () => {
    send(state.listening ? "stop_listening" : "start_listening");
  });
  document.querySelector("#notify")?.addEventListener("click", () => notify("Jarvis esta escuchando", "El proceso local sigue activo en segundo plano."));
  document.querySelector<HTMLFormElement>("#chatForm")?.addEventListener("submit", (event) => {
    event.preventDefault();
    const input = document.querySelector<HTMLInputElement>("#message");
    const text = input?.value.trim();
    if (!text) return;
    state.chat.push({ role: "user", text, meta: "Tu" });
    input!.value = "";
    render();
    send("chat", { message: text, source: "desktop" });
  });
  document.querySelector<HTMLInputElement>("#wakeSwitch")?.addEventListener("change", (event) => {
    send("voice.config", { wake_word_enabled: (event.target as HTMLInputElement).checked });
  });
  document.querySelector<HTMLInputElement>("#wakeWord")?.addEventListener("change", (event) => {
    send("voice.config", { wake_word: (event.target as HTMLInputElement).value.trim() });
  });
}

function connect() {
  clearTimeout(reconnectTimer);
  socket = new WebSocket(WS);
  socket.addEventListener("open", () => {
    state.connected = true;
    render();
  });
  socket.addEventListener("close", () => {
    state.connected = false;
    render();
    reconnectTimer = window.setTimeout(connect, 1200);
  });
  socket.addEventListener("message", (event) => handleEvent(JSON.parse(event.data)));
}

function handleEvent(envelope: Envelope) {
  if (envelope.type === "state") {
    const payload = envelope.payload;
    state.status = String(payload.status ?? state.status);
    state.listening = Boolean(payload.listening);
    state.wakeWordEnabled = Boolean(payload.wake_word_enabled);
    state.wakeWord = String(payload.wake_word ?? state.wakeWord);
    state.voiceEngine = String(payload.voice_engine ?? state.voiceEngine);
    state.llm = String(payload.llm ?? state.llm);
  }
  if (envelope.type === "chat.assistant" || envelope.type === "chat.result") {
    const text = String(envelope.payload.text ?? envelope.payload.response ?? "");
    if (text) state.chat.push({ role: "assistant", text, meta: "Jarvis" });
  }
  if (envelope.type === "voice.heard") {
    state.chat.push({ role: "system", text: String(envelope.payload.text ?? ""), meta: "Voz detectada" });
  }
  state.events.unshift(envelope);
  state.events = state.events.slice(0, 30);
  render();
}

function send(type: string, payload: Record<string, unknown> = {}) {
  if (socket?.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ type, payload }));
  }
}

async function notify(title: string, body: string) {
  let permissionGranted = await isPermissionGranted();
  if (!permissionGranted) {
    const permission = await requestPermission();
    permissionGranted = permission === "granted";
  }
  if (permissionGranted) {
    sendNotification({ title, body });
  }
}

async function registerHotkeys() {
  try {
    await register("CommandOrControl+Shift+J", () => send(state.listening ? "stop_listening" : "start_listening"));
    await register("CommandOrControl+Shift+Space", () => {
      const input = document.querySelector<HTMLInputElement>("#message");
      input?.focus();
    });
  } catch (error) {
    state.events.unshift({ type: "hotkey.error", payload: { error: String(error) } });
  }
}

function escapeHtml(value: string) {
  return value.replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char] ?? char));
}

fetch(`${API}/health`).catch(() => undefined);
render();
connect();
registerHotkeys();

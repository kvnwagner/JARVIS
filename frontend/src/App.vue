<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import {
  Activity,
  Bot,
  BrainCircuit,
  History,
  LoaderCircle,
  Mic,
  MicOff,
  PlugZap,
  Radar,
  RefreshCw,
  Send,
  Sparkles,
  Trash2,
  Wifi,
  WifiOff,
} from "lucide-vue-next";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const WS_BASE = API_BASE.replace(/^http/, "ws");
const STORAGE_KEY = "jarvis.chat.history.v8";

const input = ref("");
const messages = ref(loadLocalHistory());
const tools = ref([]);
const health = ref(null);
const ws = ref(null);
const connected = ref(false);
const connecting = ref(false);
const typing = ref(false);
const sending = ref(false);
const streamId = ref(null);
const streamText = ref("");
const recognition = ref(null);
const micState = ref("idle");
const micError = ref("");
const panel = ref("chat");
const chatScroll = ref(null);

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
const userCount = computed(() => messages.value.filter((item) => item.role === "user").length);
const assistantCount = computed(() => messages.value.filter((item) => item.role === "assistant").length);

onMounted(async () => {
  setupSpeechRecognition();
  await refreshBackendState();
  connectWebSocket();
});

onBeforeUnmount(() => {
  ws.value?.close();
  recognition.value?.abort?.();
});

watch(messages, () => {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(messages.value.slice(-80)));
  nextTick(scrollToBottom);
}, { deep: true });

function loadLocalHistory() {
  try {
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    return Array.isArray(stored) && stored.length ? stored : [welcomeMessage()];
  } catch {
    return [welcomeMessage()];
  }
}

function welcomeMessage() {
  return {
    id: crypto.randomUUID(),
    role: "assistant",
    content: "Sistema JARVIS inicializado. Canal de asistencia listo.",
    time: new Date().toISOString(),
  };
}

async function refreshBackendState() {
  try {
    const [healthResponse, toolsResponse, memoryResponse] = await Promise.all([
      fetch(`${API_BASE}/health`),
      fetch(`${API_BASE}/tools`),
      fetch(`${API_BASE}/memory?n=12`),
    ]);
    health.value = await healthResponse.json();
    const toolsData = await toolsResponse.json();
    tools.value = toolsData.tools || [];

    const memoryData = await memoryResponse.json();
    const backendHistory = (memoryData.conversation || []).map((item) => ({
      id: crypto.randomUUID(),
      role: item.role || item.source || "assistant",
      content: item.content,
      time: new Date().toISOString(),
    }));
    if (backendHistory.length && messages.value.length <= 1) {
      messages.value = backendHistory;
    }
  } catch (error) {
    health.value = { status: "offline", llm: "sin conexion", error: error.message };
  }
}

function connectWebSocket() {
  if (ws.value && [WebSocket.OPEN, WebSocket.CONNECTING].includes(ws.value.readyState)) return;
  connecting.value = true;

  const socket = new WebSocket(`${WS_BASE}/ws/chat`);
  ws.value = socket;

  socket.onopen = () => {
    connected.value = true;
    connecting.value = false;
  };

  socket.onmessage = (event) => {
    const payload = JSON.parse(event.data);
    handleSocketPayload(payload);
  };

  socket.onerror = () => {
    connected.value = false;
    connecting.value = false;
  };

  socket.onclose = () => {
    connected.value = false;
    connecting.value = false;
  };
}

async function handleSocketPayload(payload) {
  if (payload.type === "status") {
    health.value = {
      ...(health.value || {}),
      status: payload.status,
      llm: payload.llm,
      tools: payload.tools,
    };
  }

  if (payload.type === "typing") {
    typing.value = payload.active;
  }

  if (payload.type === "chunk") {
    streamText.value += payload.content;
    updateStreamingMessage(streamText.value);
  }

  if (payload.type === "done") {
    finalizeStreamingMessage(
      payload.message?.content || streamText.value,
      payload.message?.tool_used,
      payload.message?.tool_success ?? null,
      payload.message?.tool_output ?? null,
    );
    if (payload.message?.tool_used) {
      await refreshBackendState();
    }
  }

  if (payload.type === "error") {
    finalizeStreamingMessage(payload.message || "No pude completar la respuesta.");
  }
}

function pushMessage(role, content, extra = {}) {
  const message = {
    id: crypto.randomUUID(),
    role,
    content,
    time: new Date().toISOString(),
    ...extra,
  };
  messages.value.push(message);
  return message;
}

function createStreamingMessage() {
  const item = pushMessage("assistant", "", { streaming: true });
  streamId.value = item.id;
  streamText.value = "";
}

function updateStreamingMessage(content) {
  const item = messages.value.find((message) => message.id === streamId.value);
  if (item) item.content = content;
}

function finalizeStreamingMessage(content, toolUsed = null, toolSuccess = null, toolOutput = null) {
  const item = messages.value.find((message) => message.id === streamId.value);
  if (item) {
    item.content = content;
    item.streaming = false;
    item.toolUsed = toolUsed;
    item.toolSuccess = toolSuccess;
    item.toolOutput = toolOutput;
  } else {
    pushMessage("assistant", content, { toolUsed, toolSuccess, toolOutput });
  }
  sending.value = false;
  typing.value = false;
  streamId.value = null;
  streamText.value = "";
}

async function sendMessage() {
  const text = input.value.trim();
  if (!text || sending.value) return;

  pushMessage("user", text);
  input.value = "";
  sending.value = true;
  createStreamingMessage();

  if (connected.value && ws.value?.readyState === WebSocket.OPEN) {
    ws.value.send(JSON.stringify({ message: text }));
    return;
  }

  await sendWithRest(text);
}

async function sendWithRest(text) {
  try {
    typing.value = true;
    const response = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text }),
    });
    if (!response.ok) {
      const detail = await response.json().catch(() => ({}));
      throw new Error(detail.detail || "Error de backend");
    }
    const data = await response.json();
    await animateRestResponse(data.response, data.tool_used, data.success ?? null, data.response && data.tool_used ? data.response : null);
  } catch (error) {
    finalizeStreamingMessage(error.message || "Backend no disponible.");
  } finally {
    typing.value = false;
  }
}

async function animateRestResponse(text, toolUsed, toolSuccess = null, toolOutput = null) {
  streamText.value = "";
  for (const part of text.match(/.{1,18}(\s|$)/g) || [text]) {
    streamText.value += part;
    updateStreamingMessage(streamText.value);
    await new Promise((resolve) => setTimeout(resolve, 22));
  }
  finalizeStreamingMessage(text, toolUsed, toolSuccess, toolOutput);
}

function setupSpeechRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    micState.value = "unsupported";
    return;
  }

  const rec = new SpeechRecognition();
  rec.lang = "es-CO";
  rec.interimResults = true;
  rec.continuous = false;

  rec.onstart = () => {
    micState.value = "listening";
    micError.value = "";
  };
  rec.onresult = (event) => {
    const transcript = Array.from(event.results)
      .map((result) => result[0].transcript)
      .join("");
    input.value = transcript.trim();
  };
  rec.onerror = (event) => {
    micState.value = "error";
    micError.value = event.error || "No se pudo acceder al microfono.";
  };
  rec.onend = () => {
    if (micState.value === "listening") micState.value = "idle";
  };

  recognition.value = rec;
}

function toggleMic() {
  if (!recognition.value) return;
  if (micState.value === "listening") {
    recognition.value.stop();
    micState.value = "idle";
    return;
  }
  recognition.value.start();
}

function clearHistory() {
  messages.value = [welcomeMessage()];
}

function scrollToBottom() {
  if (chatScroll.value) {
    chatScroll.value.scrollTop = chatScroll.value.scrollHeight;
  }
}

function formatTime(value) {
  return new Intl.DateTimeFormat("es-CO", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}
</script>

<template>
  <main class="shell">
    <section class="orbital">
      <div class="scanline"></div>
      <div class="hud-ring ring-one"></div>
      <div class="hud-ring ring-two"></div>
      <div class="core-pulse">
        <Sparkles :size="34" />
      </div>
    </section>

    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">
          <Bot :size="28" />
        </div>
        <div>
          <h1>JARVIS</h1>
          <p>Virtual assistant interface</p>
        </div>
      </div>

      <div class="status-grid">
        <article class="metric">
          <Wifi v-if="connected" :size="18" />
          <WifiOff v-else :size="18" />
          <span>{{ connectionLabel }}</span>
        </article>
        <article class="metric">
          <BrainCircuit :size="18" />
          <span>{{ health?.llm || "sin LLM" }}</span>
        </article>
        <article class="metric">
          <Radar :size="18" />
          <span>{{ tools.length || health?.tools || 0 }} tools</span>
        </article>
        <article class="metric">
          <Activity :size="18" />
          <span>{{ health?.status || "cargando" }}</span>
        </article>
      </div>

      <div class="panel-switch">
        <button :class="{ active: panel === 'chat' }" @click="panel = 'chat'" title="Chat">
          <Bot :size="18" />
        </button>
        <button :class="{ active: panel === 'history' }" @click="panel = 'history'" title="Historial">
          <History :size="18" />
        </button>
      </div>

      <div class="tools-list">
        <div class="section-title">Herramientas</div>
        <div v-for="tool in tools.slice(0, 8)" :key="tool.name" class="tool-item">
          <span>{{ tool.name }}</span>
          <small>{{ tool.description }}</small>
        </div>
      </div>
    </aside>

    <section class="workspace">
      <header class="topbar">
        <div>
          <span class="eyebrow">Fase 8</span>
          <h2>Chat neural</h2>
        </div>
        <div class="top-actions">
          <button class="icon-button" @click="refreshBackendState" title="Actualizar estado">
            <RefreshCw :size="18" />
          </button>
          <button class="icon-button" @click="connectWebSocket" title="Reconectar WebSocket">
            <PlugZap :size="18" />
          </button>
          <button class="icon-button danger" @click="clearHistory" title="Limpiar historial">
            <Trash2 :size="18" />
          </button>
        </div>
      </header>

      <div v-if="panel === 'chat'" ref="chatScroll" class="chat-window">
        <article
          v-for="message in messages"
          :key="message.id"
          class="message"
          :class="[message.role, { streaming: message.streaming }]"
        >
          <div class="avatar">
            <Bot v-if="message.role === 'assistant'" :size="18" />
            <span v-else>U</span>
          </div>
          <div class="bubble">
            <div class="meta">
              <span>{{ message.role === "assistant" ? "JARVIS" : "Usuario" }}</span>
              <time>{{ formatTime(message.time) }}</time>
            </div>
            <p>{{ message.content }}</p>
            <div v-if="message.toolUsed" class="tool-badge" :class="{ 'tool-ok': message.toolSuccess, 'tool-fail': message.toolSuccess === false }">
              <span>{{ message.toolSuccess ? '✦' : '✕' }} {{ message.toolUsed }}</span>
              <span v-if="message.toolOutput" class="tool-output">{{ message.toolOutput.slice(0, 100) }}</span>
            </div>
          </div>
        </article>

        <div v-if="typing" class="typing">
          <LoaderCircle :size="18" />
          <span>Procesando senal...</span>
        </div>
      </div>

      <div v-else class="history-panel">
        <article class="history-card">
          <span>{{ userCount }}</span>
          <p>Mensajes enviados</p>
        </article>
        <article class="history-card">
          <span>{{ assistantCount }}</span>
          <p>Respuestas recibidas</p>
        </article>
        <article v-for="message in messages.slice().reverse()" :key="message.id" class="history-row">
          <strong>{{ message.role === "assistant" ? "JARVIS" : "Usuario" }}</strong>
          <span>{{ message.content }}</span>
        </article>
      </div>

      <footer class="composer">
        <div class="mic-state" :class="micState">
          <span class="dot"></span>
          {{ micLabel }}
          <small v-if="micError">{{ micError }}</small>
        </div>
        <div class="input-row">
          <button class="mic-button" :class="{ active: micState === 'listening' }" @click="toggleMic" title="Microfono">
            <MicOff v-if="micState === 'unsupported'" :size="20" />
            <Mic v-else :size="20" />
          </button>
          <textarea
            v-model="input"
            rows="1"
            placeholder="Escribe o dicta una orden para Jarvis..."
            @keydown.enter.exact.prevent="sendMessage"
          ></textarea>
          <button class="send-button" :disabled="!canSend" @click="sendMessage" title="Enviar">
            <Send :size="20" />
          </button>
        </div>
      </footer>
    </section>
  </main>
</template>
import axios from "axios";

const BASE_URL = "http://localhost:8000";

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.code === "ECONNREFUSED" || error.code === "ERR_NETWORK") {
      return Promise.reject(new Error("Backend offline — start the Python server first"));
    }
    return Promise.reject(error);
  }
);

export const jarvisApi = {
  // Health
  health: () => api.get("/api/health"),

  // Chat
  chat: (message) => api.post("/api/chat", { message }),
  getHistory: () => api.get("/api/chat/history"),
  clearHistory: () => api.delete("/api/chat/history"),

  // Voice
  voiceStart: () => api.post("/api/voice/start"),
  voiceStop: () => api.post("/api/voice/stop"),
  voiceSpeak: (text) => api.post("/api/voice/speak", { text }),
  voiceStatus: () => api.get("/api/voice/status"),

  // Commands
  executeCommand: (command, confirmed = false) =>
    api.post("/api/command/execute", { command, confirmed }),
  checkCommand: (command) =>
    api.post("/api/command/check", { command }),

  // Files
  searchFiles: (query, fileType = null, maxResults = 20) =>
    api.get("/api/files/search", { params: { query, file_type: fileType, max_results: maxResults } }),
  globFiles: (pattern, directory = null) =>
    api.get("/api/files/glob", { params: { pattern, directory } }),
  fileInfo: (path) =>
    api.get("/api/files/info", { params: { path } }),

  // System
  systemStatus: () => api.get("/api/system/status"),
  systemProcesses: (n = 10) => api.get("/api/system/processes", { params: { n } }),
  systemNetwork: () => api.get("/api/system/network"),
};

export function createWebSocket(onMessage, onOpen, onClose) {
  const ws = new WebSocket("ws://localhost:8000/ws");

  ws.onopen = () => {
    console.log("WebSocket connected");
    onOpen?.();
    setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "ping" }));
      }
    }, 15000);
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onMessage?.(data);
    } catch (e) {
      console.error("WS parse error:", e);
    }
  };

  ws.onclose = () => {
    console.log("WebSocket disconnected");
    onClose?.();
  };

  ws.onerror = (err) => {
    console.error("WebSocket error:", err);
  };

  return ws;
}

export default jarvisApi;

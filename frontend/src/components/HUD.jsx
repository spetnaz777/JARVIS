import React, { useState, useEffect, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { jarvisApi } from "../utils/api";
import Visualizer from "./Visualizer";
import StatusIndicator from "./StatusIndicator";
import TranscriptDisplay from "./TranscriptDisplay";
import ConfirmDialog from "./ConfirmDialog";

let ipcRenderer = null;
try {
  const electron = window.require ? window.require("electron") : null;
  if (electron) ipcRenderer = electron.ipcRenderer;
} catch (e) {}

function sendIPC(channel, ...args) {
  if (ipcRenderer) ipcRenderer.send(channel, ...args);
}

let msgId = 0;
function nextId() {
  return ++msgId;
}

export default function HUD() {
  const [state, setState] = useState("idle");
  const [backendOnline, setBackendOnline] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isThinking, setIsThinking] = useState(false);
  const [pendingConfirm, setPendingConfirm] = useState(null);
  const [vizBars, setVizBars] = useState(Array(12).fill(0));
  const [vizLevel, setVizLevel] = useState(0);
  const [systemStatus, setSystemStatus] = useState(null);
  const [showSystem, setShowSystem] = useState(false);
  const [minimized, setMinimized] = useState(false);

  const inputRef = useRef(null);
  const pollingRef = useRef(null);
  const vizPollRef = useRef(null);
  const rememberedCommands = useRef(new Set());

  // Backend health check
  const checkBackend = useCallback(async () => {
    try {
      await jarvisApi.health();
      setBackendOnline(true);
    } catch {
      setBackendOnline(false);
      setState("offline");
    }
  }, []);

  useEffect(() => {
    checkBackend();
    const interval = setInterval(checkBackend, 5000);
    return () => clearInterval(interval);
  }, [checkBackend]);

  // System status polling
  useEffect(() => {
    if (!backendOnline || !showSystem) return;
    const fetch = async () => {
      try {
        const res = await jarvisApi.systemStatus();
        setSystemStatus(res.data);
      } catch {}
    };
    fetch();
    const interval = setInterval(fetch, 3000);
    return () => clearInterval(interval);
  }, [backendOnline, showSystem]);

  // Visualizer polling during recording/speaking
  useEffect(() => {
    if (state !== "listening" && state !== "speaking") {
      setVizBars(Array(12).fill(0));
      setVizLevel(0);
      return;
    }
    vizPollRef.current = setInterval(async () => {
      try {
        const res = await jarvisApi.voiceStatus();
        const viz = res.data.visualizer;
        if (viz) {
          setVizBars(viz.bars || []);
          setVizLevel(viz.level || 0);
        }
      } catch {}
    }, 80);
    return () => clearInterval(vizPollRef.current);
  }, [state]);

  // IPC hotkey listener
  useEffect(() => {
    if (!ipcRenderer) return;
    const handler = () => {
      if (state === "idle") startVoice();
      else if (state === "listening") stopVoice();
    };
    ipcRenderer.on("hotkey-activate", handler);
    return () => ipcRenderer.removeListener("hotkey-activate", handler);
  }, [state]);

  // Keyboard: Ctrl+Shift+Space in window
  useEffect(() => {
    const handler = (e) => {
      if (e.ctrlKey && e.shiftKey && e.code === "Space") {
        e.preventDefault();
        if (state === "idle") startVoice();
        else if (state === "listening") stopVoice();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [state]);

  const addMessage = (role, content, extra = {}) => {
    setMessages((prev) => [
      ...prev,
      { id: nextId(), role, content, timestamp: Date.now(), ...extra },
    ]);
  };

  const processResponse = async (responseText) => {
    // Detect CMD: prefix
    const cmdMatch = responseText.match(/CMD:\s*(.+?)(?:\n|$)/);
    if (cmdMatch) {
      const command = cmdMatch[1].trim();
      await handleCommand(command, responseText);
      return;
    }
    addMessage("assistant", responseText);
  };

  const handleCommand = async (command, fullResponse) => {
    if (rememberedCommands.current.has(command)) {
      const result = await executeConfirmed(command);
      addMessage("assistant", fullResponse, { command_result: result });
      return;
    }

    try {
      const res = await jarvisApi.executeCommand(command, false);
      const data = res.data;

      if (data.blocked) {
        setPendingConfirm({
          command,
          fullResponse,
          safety: data.safety,
        });
      } else {
        addMessage("assistant", fullResponse, { command_result: data });
      }
    } catch (e) {
      addMessage("assistant", fullResponse, {
        command_result: { success: false, stdout: "", stderr: e.message, return_code: -1 },
      });
    }
  };

  const executeConfirmed = async (command) => {
    try {
      const res = await jarvisApi.executeCommand(command, true);
      return res.data;
    } catch (e) {
      return { success: false, stdout: "", stderr: e.message, return_code: -1 };
    }
  };

  const handleConfirmAllow = async (remember) => {
    if (!pendingConfirm) return;
    const { command, fullResponse } = pendingConfirm;
    if (remember) rememberedCommands.current.add(command);
    setPendingConfirm(null);

    const result = await executeConfirmed(command);
    addMessage("assistant", fullResponse, { command_result: result });
    if (backendOnline && state !== "listening") {
      await jarvisApi.voiceSpeak(result.success ? "Command executed successfully." : "Command failed.");
    }
  };

  const handleConfirmDeny = () => {
    if (!pendingConfirm) return;
    addMessage("assistant", "Command denied by user.");
    setPendingConfirm(null);
  };

  const sendTextMessage = async (text) => {
    if (!text.trim() || !backendOnline) return;
    const trimmed = text.trim();
    addMessage("user", trimmed);
    setInput("");
    setState("thinking");
    setIsThinking(true);

    try {
      const res = await jarvisApi.chat(trimmed);
      const responseText = res.data.response;
      setState("speaking");
      await processResponse(responseText);
      await jarvisApi.voiceSpeak(responseText.replace(/CMD:.*$/gm, "").trim().slice(0, 300));
    } catch (e) {
      addMessage("assistant", `Error: ${e.message}`);
    } finally {
      setState("idle");
      setIsThinking(false);
    }
  };

  const startVoice = async () => {
    if (!backendOnline) return;
    try {
      await jarvisApi.voiceStart();
      setState("listening");
    } catch (e) {
      addMessage("assistant", `Voice start failed: ${e.message}`);
    }
  };

  const stopVoice = async () => {
    if (state !== "listening") return;
    setState("thinking");
    setIsThinking(true);

    try {
      const res = await jarvisApi.voiceStop();
      const { transcript, response, status } = res.data;

      if (status === "no_audio" || status === "no_transcript") {
        addMessage("assistant", "I didn't catch that. Please try again.");
        setState("idle");
        setIsThinking(false);
        return;
      }

      if (transcript) addMessage("user", transcript);
      if (response) {
        setState("speaking");
        await processResponse(response);
      }
    } catch (e) {
      addMessage("assistant", `Voice error: ${e.message}`);
    } finally {
      setState("idle");
      setIsThinking(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendTextMessage(input);
    }
  };

  if (minimized) {
    return (
      <motion.div
        className="fixed bottom-4 right-4 w-16 h-16 rounded-full glass cursor-pointer flex items-center justify-center no-drag"
        style={{ border: "1px solid rgba(0, 217, 255, 0.4)" }}
        onClick={() => setMinimized(false)}
        whileHover={{ scale: 1.1 }}
      >
        <Visualizer state={backendOnline ? state : "offline"} bars={vizBars} level={vizLevel} />
      </motion.div>
    );
  }

  return (
    <>
      <ConfirmDialog
        pending={pendingConfirm}
        onAllow={handleConfirmAllow}
        onDeny={handleConfirmDeny}
      />

      <div
        className="h-screen flex flex-col glass-dark hud-frame overflow-hidden"
        style={{ borderRadius: 12, border: "1px solid rgba(0, 217, 255, 0.15)" }}
      >
        {/* Title Bar */}
        <div
          className="drag-region flex items-center justify-between px-4 py-2 border-b"
          style={{ borderColor: "rgba(0, 217, 255, 0.1)", minHeight: 40 }}
        >
          <div className="flex items-center gap-2 no-drag">
            <span className="text-xs font-bold tracking-widest glow-text">JARVIS</span>
            <span className="text-xs" style={{ color: "#3a5a7a" }}>v1.0</span>
          </div>

          <StatusIndicator state={state} backendOnline={backendOnline} />

          <div className="flex items-center gap-1 no-drag">
            <button
              onClick={() => setShowSystem(!showSystem)}
              className="glow-btn w-6 h-6 rounded flex items-center justify-center text-xs"
              title="System Status"
            >
              ◈
            </button>
            <button
              onClick={() => setMinimized(true)}
              className="glow-btn w-6 h-6 rounded flex items-center justify-center text-xs"
              title="Minimize"
            >
              −
            </button>
            <button
              onClick={() => sendIPC("close-window")}
              className="w-6 h-6 rounded flex items-center justify-center text-xs"
              style={{
                background: "rgba(255, 68, 68, 0.1)",
                border: "1px solid rgba(255, 68, 68, 0.3)",
                color: "#ff6b6b",
                cursor: "pointer",
              }}
              title="Close"
            >
              ×
            </button>
          </div>
        </div>

        {/* System Status Panel */}
        <AnimatePresence>
          {showSystem && systemStatus && (
            <motion.div
              className="px-4 py-2 border-b text-xs"
              style={{ borderColor: "rgba(0, 217, 255, 0.1)", background: "rgba(0, 0, 0, 0.2)" }}
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
            >
              <div className="grid grid-cols-3 gap-2">
                <div>
                  <span style={{ color: "#6b9ab8" }}>CPU </span>
                  <span style={{ color: systemStatus.cpu.percent > 80 ? "#ff6b6b" : "#00d9ff" }}>
                    {systemStatus.cpu.percent}%
                  </span>
                </div>
                <div>
                  <span style={{ color: "#6b9ab8" }}>MEM </span>
                  <span style={{ color: systemStatus.memory.percent > 85 ? "#ff6b6b" : "#00d9ff" }}>
                    {systemStatus.memory.percent}%
                  </span>
                </div>
                <div>
                  <span style={{ color: "#6b9ab8" }}>DSK </span>
                  <span style={{ color: systemStatus.disk.percent > 90 ? "#ff6b6b" : "#00d9ff" }}>
                    {systemStatus.disk.percent}%
                  </span>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Visualizer */}
        <div className="flex flex-col items-center py-4">
          <Visualizer
            state={backendOnline ? state : "offline"}
            bars={vizBars}
            level={vizLevel}
          />
          <div className="mt-2 text-center">
            <p className="text-xs" style={{ color: "#3a5a7a" }}>
              {state === "idle" ? "Ctrl+Shift+Space to activate" : ""}
              {state === "listening" ? "Listening... press Ctrl+Shift+Space to stop" : ""}
              {state === "thinking" ? "Processing..." : ""}
              {state === "speaking" ? "Speaking..." : ""}
            </p>
          </div>
        </div>

        {/* Transcript */}
        <div className="flex-1 overflow-hidden" style={{ minHeight: 0 }}>
          <TranscriptDisplay messages={messages} isThinking={isThinking} />
        </div>

        {/* Input Area */}
        <div
          className="border-t p-3"
          style={{ borderColor: "rgba(0, 217, 255, 0.1)" }}
        >
          <div className="flex gap-2 items-center">
            <button
              onClick={state === "listening" ? stopVoice : startVoice}
              disabled={!backendOnline}
              className="no-drag w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0"
              style={{
                background: state === "listening"
                  ? "rgba(0, 255, 136, 0.2)"
                  : "rgba(0, 217, 255, 0.1)",
                border: state === "listening"
                  ? "1px solid rgba(0, 255, 136, 0.5)"
                  : "1px solid rgba(0, 217, 255, 0.3)",
                color: state === "listening" ? "#00ff88" : "#00d9ff",
                cursor: backendOnline ? "pointer" : "not-allowed",
                opacity: backendOnline ? 1 : 0.4,
                fontSize: 14,
              }}
              title={state === "listening" ? "Stop recording" : "Start voice input"}
            >
              {state === "listening" ? "■" : "🎤"}
            </button>

            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={backendOnline ? "Message JARVIS..." : "Backend offline..."}
              disabled={!backendOnline || isThinking}
              className="flex-1 px-3 py-1.5 rounded jarvis-input text-xs no-drag"
              style={{ minWidth: 0, height: 32 }}
            />

            <button
              onClick={() => sendTextMessage(input)}
              disabled={!input.trim() || !backendOnline || isThinking}
              className="no-drag w-8 h-8 rounded flex items-center justify-center flex-shrink-0 glow-btn"
              style={{
                cursor: input.trim() && backendOnline && !isThinking ? "pointer" : "not-allowed",
                opacity: input.trim() && backendOnline && !isThinking ? 1 : 0.4,
                fontSize: 12,
              }}
              title="Send"
            >
              ▶
            </button>
          </div>

          <div className="mt-1.5 flex justify-between items-center">
            <button
              onClick={() => {
                setMessages([]);
                jarvisApi.clearHistory().catch(() => {});
              }}
              className="text-xs no-drag"
              style={{ color: "#3a5a7a", cursor: "pointer", background: "none", border: "none" }}
            >
              Clear history
            </button>
            <span className="text-xs" style={{ color: "#3a5a7a" }}>
              {messages.length} messages
            </span>
          </div>
        </div>
      </div>
    </>
  );
}

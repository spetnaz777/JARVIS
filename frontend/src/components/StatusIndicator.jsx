import React from "react";
import { motion } from "framer-motion";

const STATE_CONFIG = {
  idle: { label: "STANDBY", color: "#00d9ff", dot: "#00d9ff", pulse: false },
  listening: { label: "LISTENING", color: "#00ff88", dot: "#00ff88", pulse: true },
  thinking: { label: "PROCESSING", color: "#aa64ff", dot: "#aa64ff", pulse: true },
  speaking: { label: "SPEAKING", color: "#00d9ff", dot: "#00d9ff", pulse: true },
  offline: { label: "OFFLINE", color: "#ff4444", dot: "#ff4444", pulse: false },
};

export default function StatusIndicator({ state = "idle", backendOnline = true }) {
  const effectiveState = backendOnline ? state : "offline";
  const config = STATE_CONFIG[effectiveState] || STATE_CONFIG.idle;

  return (
    <div className="flex items-center gap-2">
      <div className="relative flex items-center justify-center w-3 h-3">
        {config.pulse && (
          <motion.div
            className="absolute rounded-full"
            style={{ backgroundColor: config.dot, width: 12, height: 12 }}
            animate={{ scale: [1, 2], opacity: [0.6, 0] }}
            transition={{ duration: 1.2, repeat: Infinity, ease: "easeOut" }}
          />
        )}
        <div
          className="w-2 h-2 rounded-full"
          style={{
            backgroundColor: config.dot,
            boxShadow: `0 0 6px ${config.dot}`,
          }}
        />
      </div>

      <span
        className="text-xs font-semibold tracking-widest"
        style={{ color: config.color }}
      >
        {config.label}
      </span>
    </div>
  );
}

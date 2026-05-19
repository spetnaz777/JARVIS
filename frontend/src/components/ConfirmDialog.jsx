import React, { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";

const TIMEOUT_SECONDS = 10;

const RISK_CONFIG = {
  CRITICAL: {
    label: "CRITICAL RISK",
    color: "#ff4444",
    bgColor: "rgba(255, 68, 68, 0.1)",
    borderColor: "rgba(255, 68, 68, 0.4)",
    icon: "⚠",
  },
  ELEVATED: {
    label: "ELEVATED RISK",
    color: "#ffaa00",
    bgColor: "rgba(255, 170, 0, 0.1)",
    borderColor: "rgba(255, 170, 0, 0.4)",
    icon: "⚡",
  },
  STANDARD: {
    label: "STANDARD",
    color: "#00d9ff",
    bgColor: "rgba(0, 217, 255, 0.1)",
    borderColor: "rgba(0, 217, 255, 0.3)",
    icon: "✓",
  },
};

export default function ConfirmDialog({ pending, onAllow, onDeny }) {
  const [timeLeft, setTimeLeft] = useState(TIMEOUT_SECONDS);
  const [remember, setRemember] = useState(false);

  const handleDeny = useCallback(() => {
    onDeny?.();
  }, [onDeny]);

  const handleAllow = useCallback(() => {
    onAllow?.(remember);
  }, [onAllow, remember]);

  useEffect(() => {
    if (!pending) return;
    setTimeLeft(TIMEOUT_SECONDS);

    const interval = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev <= 1) {
          clearInterval(interval);
          handleDeny();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [pending, handleDeny]);

  useEffect(() => {
    if (!pending) return;

    const handler = (e) => {
      if (e.key === "Enter") handleAllow();
      if (e.key === "Escape") handleDeny();
    };

    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [pending, handleAllow, handleDeny]);

  const riskLevel = pending?.safety?.risk_level || "STANDARD";
  const riskConfig = RISK_CONFIG[riskLevel] || RISK_CONFIG.STANDARD;
  const progress = (timeLeft / TIMEOUT_SECONDS) * 100;

  return (
    <AnimatePresence>
      {pending && (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          {/* Backdrop */}
          <div
            className="absolute inset-0"
            style={{ background: "rgba(5, 14, 26, 0.85)", backdropFilter: "blur(8px)" }}
            onClick={handleDeny}
          />

          {/* Dialog */}
          <motion.div
            className="relative w-full max-w-sm mx-4 rounded-lg glass hud-frame no-drag"
            style={{ border: `1px solid ${riskConfig.borderColor}`, boxShadow: `0 0 30px ${riskConfig.color}30` }}
            initial={{ scale: 0.9, y: 10 }}
            animate={{ scale: 1, y: 0 }}
            exit={{ scale: 0.9, y: 10 }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Risk badge */}
            <div className="p-4 border-b" style={{ borderColor: riskConfig.borderColor }}>
              <div className="flex items-center gap-2 mb-1">
                <span style={{ color: riskConfig.color, fontSize: 18 }}>{riskConfig.icon}</span>
                <span
                  className="text-xs font-bold tracking-widest"
                  style={{ color: riskConfig.color }}
                >
                  {riskConfig.label}
                </span>
              </div>
              <p className="text-xs" style={{ color: "#6b9ab8" }}>
                Command requires your authorization
              </p>
            </div>

            {/* Command preview */}
            <div className="p-4 border-b" style={{ borderColor: "rgba(0, 217, 255, 0.1)" }}>
              <p className="text-xs mb-1" style={{ color: "#6b9ab8" }}>COMMAND</p>
              <div
                className="p-2 rounded text-xs font-mono overflow-x-auto"
                style={{
                  background: "rgba(0, 0, 0, 0.4)",
                  border: "1px solid rgba(0, 217, 255, 0.1)",
                  color: "#e0f7ff",
                  maxHeight: 80,
                  wordBreak: "break-all",
                }}
              >
                {pending.command}
              </div>
            </div>

            {/* Explanation */}
            {pending.safety?.reason && (
              <div className="px-4 pt-3">
                <p className="text-xs" style={{ color: riskConfig.color, opacity: 0.9 }}>
                  {pending.safety.reason}
                </p>
              </div>
            )}

            {/* Remember checkbox */}
            <div className="px-4 pt-3 pb-1 flex items-center gap-2">
              <input
                type="checkbox"
                id="remember"
                checked={remember}
                onChange={(e) => setRemember(e.target.checked)}
                className="no-drag"
                style={{ accentColor: "#00d9ff" }}
              />
              <label htmlFor="remember" className="text-xs cursor-pointer no-drag" style={{ color: "#6b9ab8" }}>
                Remember for this session
              </label>
            </div>

            {/* Timer bar */}
            <div className="mx-4 mt-2 h-1 rounded-full overflow-hidden" style={{ background: "rgba(255,255,255,0.05)" }}>
              <motion.div
                className="h-full rounded-full"
                style={{ background: riskConfig.color }}
                initial={{ width: "100%" }}
                animate={{ width: `${progress}%` }}
                transition={{ duration: 0.3 }}
              />
            </div>

            {/* Buttons */}
            <div className="p-4 flex gap-3">
              <button
                onClick={handleDeny}
                className="flex-1 py-2 rounded text-xs font-bold tracking-wider no-drag"
                style={{
                  background: "rgba(255, 68, 68, 0.1)",
                  border: "1px solid rgba(255, 68, 68, 0.4)",
                  color: "#ff6b6b",
                  cursor: "pointer",
                  transition: "all 0.2s",
                }}
                onMouseEnter={(e) => { e.target.style.background = "rgba(255, 68, 68, 0.25)"; }}
                onMouseLeave={(e) => { e.target.style.background = "rgba(255, 68, 68, 0.1)"; }}
              >
                DENY [{timeLeft}s]
              </button>

              <button
                onClick={handleAllow}
                className="flex-1 py-2 rounded text-xs font-bold tracking-wider no-drag"
                style={{
                  background: "rgba(0, 255, 136, 0.1)",
                  border: "1px solid rgba(0, 255, 136, 0.4)",
                  color: "#00ff88",
                  cursor: "pointer",
                  transition: "all 0.2s",
                }}
                onMouseEnter={(e) => { e.target.style.background = "rgba(0, 255, 136, 0.25)"; }}
                onMouseLeave={(e) => { e.target.style.background = "rgba(0, 255, 136, 0.1)"; }}
              >
                ALLOW [Enter]
              </button>
            </div>

            <p className="text-center text-xs pb-3" style={{ color: "#6b9ab8" }}>
              Press <kbd style={{ color: "#00d9ff" }}>Esc</kbd> to deny, <kbd style={{ color: "#00ff88" }}>Enter</kbd> to allow
            </p>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

import React, { useEffect, useRef } from "react";
import { motion } from "framer-motion";

const NUM_BARS = 12;
const RADIUS = 52;
const BAR_WIDTH = 4;
const BAR_MIN_HEIGHT = 6;
const BAR_MAX_HEIGHT = 28;

function polarToXY(angleDeg, radius) {
  const rad = ((angleDeg - 90) * Math.PI) / 180;
  return {
    x: 64 + radius * Math.cos(rad),
    y: 64 + radius * Math.sin(rad),
  };
}

function getBarTransform(index, total, radius) {
  const angle = (index / total) * 360;
  const rad = ((angle - 90) * Math.PI) / 180;
  const cx = 64 + radius * Math.cos(rad);
  const cy = 64 + radius * Math.sin(rad);
  return { cx, cy, angle };
}

const STATE_COLORS = {
  idle: "#00d9ff",
  listening: "#00ff88",
  thinking: "#aa64ff",
  speaking: "#00d9ff",
  offline: "#ff4444",
};

export default function Visualizer({ state = "idle", bars = [], level = 0 }) {
  const canvasRef = useRef(null);
  const animFrameRef = useRef(null);
  const barsRef = useRef(Array(NUM_BARS).fill(BAR_MIN_HEIGHT));
  const timeRef = useRef(0);

  const color = STATE_COLORS[state] || STATE_COLORS.idle;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    function draw() {
      timeRef.current += 0.03;
      const t = timeRef.current;

      ctx.clearRect(0, 0, 128, 128);

      // Outer ring
      ctx.beginPath();
      ctx.arc(64, 64, 58, 0, Math.PI * 2);
      ctx.strokeStyle = `${color}33`;
      ctx.lineWidth = 1;
      ctx.stroke();

      // Inner ring
      ctx.beginPath();
      ctx.arc(64, 64, 44, 0, Math.PI * 2);
      ctx.strokeStyle = `${color}22`;
      ctx.lineWidth = 1;
      ctx.stroke();

      // Core circle
      const coreGlow = 0.4 + level * 0.6;
      const gradient = ctx.createRadialGradient(64, 64, 0, 64, 64, 30);
      gradient.addColorStop(0, `${color}${Math.round(coreGlow * 80).toString(16).padStart(2, "0")}`);
      gradient.addColorStop(0.6, `${color}22`);
      gradient.addColorStop(1, "transparent");
      ctx.beginPath();
      ctx.arc(64, 64, 30, 0, Math.PI * 2);
      ctx.fillStyle = gradient;
      ctx.fill();

      // Bars
      for (let i = 0; i < NUM_BARS; i++) {
        const angle = (i / NUM_BARS) * 360;
        const rad = ((angle - 90) * Math.PI) / 180;

        let targetH;
        if (state === "idle") {
          targetH = BAR_MIN_HEIGHT + 3 * Math.abs(Math.sin(t * 0.8 + i * 0.6));
        } else if (state === "listening") {
          const barLevel = bars[i] || 0;
          targetH = BAR_MIN_HEIGHT + (BAR_MAX_HEIGHT - BAR_MIN_HEIGHT) * barLevel;
        } else if (state === "thinking") {
          targetH = BAR_MIN_HEIGHT + 12 * Math.abs(Math.sin(t * 2 + (i / NUM_BARS) * Math.PI * 2));
        } else if (state === "speaking") {
          const barLevel = bars[i] || level;
          targetH = BAR_MIN_HEIGHT + (BAR_MAX_HEIGHT - BAR_MIN_HEIGHT) * (barLevel * 0.7 + 0.3 * Math.abs(Math.sin(t * 3 + i)));
        } else {
          targetH = BAR_MIN_HEIGHT;
        }

        barsRef.current[i] = barsRef.current[i] * 0.7 + targetH * 0.3;
        const h = barsRef.current[i];

        const innerR = RADIUS - h / 2;
        const outerR = RADIUS + h / 2;

        const x1 = 64 + innerR * Math.cos(rad);
        const y1 = 64 + innerR * Math.sin(rad);
        const x2 = 64 + outerR * Math.cos(rad);
        const y2 = 64 + outerR * Math.sin(rad);

        const alpha = 0.6 + (h / BAR_MAX_HEIGHT) * 0.4;
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.strokeStyle = `${color}${Math.round(alpha * 255).toString(16).padStart(2, "0")}`;
        ctx.lineWidth = BAR_WIDTH;
        ctx.lineCap = "round";
        ctx.stroke();
      }

      // Center dot
      ctx.beginPath();
      ctx.arc(64, 64, 4, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.shadowColor = color;
      ctx.shadowBlur = 12;
      ctx.fill();
      ctx.shadowBlur = 0;

      animFrameRef.current = requestAnimationFrame(draw);
    }

    animFrameRef.current = requestAnimationFrame(draw);
    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    };
  }, [state, bars, level, color]);

  return (
    <div className="relative flex items-center justify-center">
      {/* Ripple rings for active states */}
      {(state === "listening" || state === "speaking") && (
        <>
          <motion.div
            className="absolute rounded-full border"
            style={{ borderColor: `${color}40`, width: 128, height: 128 }}
            animate={{ scale: [1, 1.4], opacity: [0.6, 0] }}
            transition={{ duration: 1.5, repeat: Infinity, ease: "easeOut" }}
          />
          <motion.div
            className="absolute rounded-full border"
            style={{ borderColor: `${color}30`, width: 128, height: 128 }}
            animate={{ scale: [1, 1.7], opacity: [0.4, 0] }}
            transition={{ duration: 1.5, repeat: Infinity, ease: "easeOut", delay: 0.4 }}
          />
        </>
      )}

      {/* Thinking rotation ring */}
      {state === "thinking" && (
        <motion.div
          className="absolute rounded-full border-2"
          style={{ borderColor: `${color}50`, borderTopColor: color, width: 136, height: 136 }}
          animate={{ rotate: 360 }}
          transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }}
        />
      )}

      <canvas
        ref={canvasRef}
        width={128}
        height={128}
        className="relative z-10"
        style={{ filter: `drop-shadow(0 0 8px ${color}80)` }}
      />
    </div>
  );
}

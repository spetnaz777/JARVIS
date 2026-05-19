import React, { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";

function CodeBlock({ text }) {
  const lines = text.split("\n");
  return (
    <pre
      className="text-xs p-2 rounded my-1 overflow-x-auto"
      style={{
        background: "rgba(0, 0, 0, 0.5)",
        border: "1px solid rgba(0, 217, 255, 0.15)",
        color: "#e0f7ff",
        fontFamily: "monospace",
        whiteSpace: "pre-wrap",
        wordBreak: "break-all",
      }}
    >
      {lines.join("\n")}
    </pre>
  );
}

function MessageContent({ text }) {
  if (!text) return null;

  const parts = text.split(/(```[\s\S]*?```|`[^`]+`)/g);

  return (
    <div>
      {parts.map((part, i) => {
        if (part.startsWith("```") && part.endsWith("```")) {
          const code = part.slice(3, -3).replace(/^\w+\n/, "");
          return <CodeBlock key={i} text={code} />;
        }
        if (part.startsWith("`") && part.endsWith("`")) {
          return (
            <code
              key={i}
              className="px-1 rounded text-xs"
              style={{
                background: "rgba(0, 217, 255, 0.1)",
                color: "#00d9ff",
                fontFamily: "monospace",
              }}
            >
              {part.slice(1, -1)}
            </code>
          );
        }
        return (
          <span key={i} style={{ whiteSpace: "pre-wrap" }}>
            {part}
          </span>
        );
      })}
    </div>
  );
}

function Message({ msg }) {
  const isUser = msg.role === "user";

  return (
    <motion.div
      className={`mb-3 ${isUser ? "ml-4" : "mr-2"}`}
      initial={{ opacity: 0, x: isUser ? 10 : -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.2 }}
    >
      <div className="flex items-center gap-2 mb-1">
        <span
          className="text-xs font-bold tracking-widest"
          style={{ color: isUser ? "#00d9ff" : "#aa64ff" }}
        >
          {isUser ? "YOU" : "JARVIS"}
        </span>
        {msg.timestamp && (
          <span className="text-xs" style={{ color: "#3a5a7a" }}>
            {new Date(msg.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          </span>
        )}
      </div>

      <div
        className={`px-3 py-2 rounded text-xs leading-relaxed ${isUser ? "msg-user" : "msg-assistant"}`}
      >
        <MessageContent text={msg.content} />
      </div>

      {msg.command_result && (
        <div
          className="mt-1 px-2 py-1 rounded text-xs"
          style={{
            background: msg.command_result.success
              ? "rgba(0, 255, 136, 0.05)"
              : "rgba(255, 68, 68, 0.05)",
            border: `1px solid ${msg.command_result.success ? "rgba(0, 255, 136, 0.2)" : "rgba(255, 68, 68, 0.2)"}`,
          }}
        >
          <p
            className="font-bold text-xs mb-1"
            style={{ color: msg.command_result.success ? "#00ff88" : "#ff6b6b" }}
          >
            {msg.command_result.success ? "✓ EXECUTED" : "✗ FAILED"} (rc={msg.command_result.return_code})
          </p>
          {msg.command_result.stdout && (
            <pre className="text-xs overflow-x-auto" style={{ color: "#e0f7ff", whiteSpace: "pre-wrap" }}>
              {msg.command_result.stdout.slice(0, 500)}
              {msg.command_result.stdout.length > 500 && "\n... [truncated]"}
            </pre>
          )}
          {msg.command_result.stderr && (
            <pre className="text-xs overflow-x-auto" style={{ color: "#ff8080", whiteSpace: "pre-wrap" }}>
              {msg.command_result.stderr.slice(0, 200)}
            </pre>
          )}
        </div>
      )}
    </motion.div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 px-3 py-2 mb-2 rounded msg-assistant w-fit">
      {[0, 1, 2].map((i) => (
        <motion.div
          key={i}
          className="w-1.5 h-1.5 rounded-full"
          style={{ background: "#aa64ff" }}
          animate={{ scale: [1, 1.4, 1], opacity: [0.5, 1, 0.5] }}
          transition={{ duration: 0.8, repeat: Infinity, delay: i * 0.2 }}
        />
      ))}
    </div>
  );
}

export default function TranscriptDisplay({ messages = [], isThinking = false }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isThinking]);

  if (messages.length === 0 && !isThinking) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center" style={{ color: "#3a5a7a" }}>
          <p className="text-xs tracking-widest mb-1">JARVIS ONLINE</p>
          <p className="text-xs">Press Ctrl+Shift+Space or type below</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-3 py-2">
      <AnimatePresence initial={false}>
        {messages.map((msg) => (
          <Message key={msg.id} msg={msg} />
        ))}
      </AnimatePresence>

      {isThinking && <TypingIndicator />}

      <div ref={bottomRef} />
    </div>
  );
}

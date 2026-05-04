"use client";

import { useState, useCallback } from "react";
import VoiceRoom from "@/components/VoiceRoom";
import PDFUploader from "@/components/PDFUploader";
import StatusBar from "@/components/StatusBar";

export type AppState = "idle" | "connecting" | "connected" | "error";

export default function Home() {
  const [appState, setAppState] = useState<AppState>("idle");
  const [token, setToken] = useState<string | null>(null);
  const [serverUrl, setServerUrl] = useState<string | null>(null);
  const [statusMsg, setStatusMsg] = useState("Upload a PDF to get started");
  const [pdfReady, setPdfReady] = useState(false);

  const startSession = useCallback(async () => {
    setAppState("connecting");
    setStatusMsg("Connecting to voice agent...");
    try {
      const res = await fetch("/api/connection-details");
      if (!res.ok) throw new Error("Failed to get connection details");
      const { token, serverUrl } = await res.json();
      setToken(token);
      setServerUrl(serverUrl);
      setAppState("connected");
      setStatusMsg("Connected — speak to ask questions about your document");
    } catch (e) {
      setAppState("error");
      setStatusMsg("Connection failed. Check your .env and try again.");
    }
  }, []);

  const handlePdfLoaded = useCallback((filename: string) => {
    setPdfReady(true);
    setStatusMsg(`"${filename}" loaded — click Start Session to begin`);
  }, []);

  return (
    <main className="min-h-screen bg-gray-950 text-white flex flex-col items-center justify-center p-6 gap-8">
      {/* Header */}
      <div className="text-center">
        <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-400 to-violet-400 bg-clip-text text-transparent">
          Voice RAG Assistant
        </h1>
        <p className="text-gray-400 mt-2 text-sm">
          Upload a PDF · Start a session · Ask anything by voice
        </p>
      </div>

      {/* Status */}
      <StatusBar message={statusMsg} state={appState} />

      {/* Upload */}
      <PDFUploader
        onPdfLoaded={handlePdfLoaded}
        disabled={appState === "connected"}
        token={token}
        serverUrl={serverUrl}
      />

      {/* Voice Room */}
      {appState === "connected" && token && serverUrl ? (
        <VoiceRoom token={token} serverUrl={serverUrl} />
      ) : (
        <button
          onClick={startSession}
          disabled={!pdfReady || appState === "connecting"}
          className="px-8 py-3 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-40
                     disabled:cursor-not-allowed font-semibold transition-all duration-200
                     shadow-lg shadow-blue-900/40"
        >
          {appState === "connecting" ? "Connecting..." : "Start Voice Session"}
        </button>
      )}

      <p className="text-xs text-gray-600 text-center max-w-sm">
        Built with LiveKit · OpenAI GPT-4o-mini · Deepgram STT · Redis Vector Search
      </p>
    </main>
  );
}

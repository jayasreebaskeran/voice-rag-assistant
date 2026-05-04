"use client";

import { useCallback, useRef, useState } from "react";
import { RoomEvent } from "livekit-client";

interface PDFUploaderProps {
  onPdfLoaded: (filename: string) => void;
  disabled: boolean;
  token: string | null;
  serverUrl: string | null;
}

const MAX_FILE_SIZE_MB = 10;

export default function PDFUploader({
  onPdfLoaded,
  disabled,
  token,
  serverUrl,
}: PDFUploaderProps) {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filename, setFilename] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const validateFile = (file: File): string | null => {
    if (file.type !== "application/pdf") return "Only PDF files are supported.";
    if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024)
      return `File exceeds ${MAX_FILE_SIZE_MB}MB limit.`;
    return null;
  };

  const processFile = useCallback(
    async (file: File) => {
      const validationError = validateFile(file);
      if (validationError) {
        setError(validationError);
        return;
      }

      setError(null);
      setUploading(true);
      setFilename(file.name);

      try {
        // Read as base64
        const base64 = await fileToBase64(file);

        // If already connected to room, send via LiveKit data channel
        if (token && serverUrl) {
          await sendPdfToAgent(base64, file.name, serverUrl, token);
        }
        // Always notify parent so button unlocks
        onPdfLoaded(file.name);
      } catch (e) {
        setError("Upload failed. Please try again.");
        console.error("PDF upload error:", e);
      } finally {
        setUploading(false);
      }
    },
    [token, serverUrl, onPdfLoaded]
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) processFile(file);
    },
    [processFile]
  );

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      onClick={() => !disabled && inputRef.current?.click()}
      className={`
        w-full max-w-lg border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer
        transition-all duration-200
        ${dragging ? "border-blue-400 bg-blue-950/30" : "border-gray-700 hover:border-gray-500 bg-gray-900/40"}
        ${disabled ? "opacity-50 cursor-not-allowed pointer-events-none" : ""}
      `}
    >
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) processFile(file);
        }}
      />

      {uploading ? (
        <p className="text-blue-400 animate-pulse">Processing PDF...</p>
      ) : filename ? (
        <div className="space-y-1">
          <p className="text-green-400 font-medium">✓ {filename}</p>
          <p className="text-gray-500 text-xs">Click or drop to replace</p>
        </div>
      ) : (
        <div className="space-y-2">
          <p className="text-4xl">📄</p>
          <p className="text-gray-300 font-medium">Drop your PDF here</p>
          <p className="text-gray-500 text-sm">or click to browse · max {MAX_FILE_SIZE_MB}MB</p>
        </div>
      )}

      {error && (
        <p className="mt-3 text-red-400 text-sm">{error}</p>
      )}
    </div>
  );
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      resolve(result.split(",")[1]); // strip data:application/pdf;base64,
    };
    reader.onerror = () => reject(new Error("File read failed"));
    reader.readAsDataURL(file);
  });
}

async function sendPdfToAgent(
  base64: string,
  filename: string,
  serverUrl: string,
  token: string
) {
  // Send via fetch to our API route which forwards to LiveKit room
  await fetch("/api/send-pdf", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ base64, filename }),
  });
}

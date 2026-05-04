"use client";

import { useEffect, useState } from "react";
import {
  LiveKitRoom,
  useVoiceAssistant,
  BarVisualizer,
  VoiceAssistantControlBar,
  RoomAudioRenderer,
} from "@livekit/components-react";
import "@livekit/components-styles";

interface VoiceRoomProps {
  token: string;
  serverUrl: string;
}

function AssistantUI() {
  const { state, audioTrack } = useVoiceAssistant();

  const stateLabel: Record<string, string> = {
    disconnected: "Disconnected",
    connecting: "Connecting...",
    initializing: "Initializing...",
    listening: "🎙 Listening",
    thinking: "🧠 Thinking",
    speaking: "🔊 Speaking",
  };

  return (
    <div className="flex flex-col items-center gap-6 w-full max-w-lg">
      {/* State indicator */}
      <div className="text-sm font-medium text-blue-300 tracking-wide">
        {stateLabel[state] ?? state}
      </div>

      {/* Audio visualizer */}
      <div className="w-full h-24 rounded-2xl bg-gray-900 border border-gray-800 overflow-hidden flex items-center px-4">
        <BarVisualizer
          state={state}
          trackRef={audioTrack}
          barCount={40}
          options={{ minHeight: 4 }}
          style={{ width: "100%", height: "100%" }}
        />
      </div>

      {/* Mic controls */}
      <VoiceAssistantControlBar />

      <RoomAudioRenderer />
    </div>
  );
}

export default function VoiceRoom({ token, serverUrl }: VoiceRoomProps) {
  return (
    <LiveKitRoom
      token={token}
      serverUrl={serverUrl}
      connect={true}
      audio={true}
      video={false}
      className="w-full flex justify-center"
    >
      <AssistantUI />
    </LiveKitRoom>
  );
}

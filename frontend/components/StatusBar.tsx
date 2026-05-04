"use client";

import { AppState } from "@/app/page";

const stateColors: Record<AppState, string> = {
  idle: "bg-gray-800 text-gray-400",
  connecting: "bg-yellow-900/40 text-yellow-300",
  connected: "bg-green-900/40 text-green-300",
  error: "bg-red-900/40 text-red-300",
};

interface StatusBarProps {
  message: string;
  state: AppState;
}

export default function StatusBar({ message, state }: StatusBarProps) {
  return (
    <div className={`px-5 py-2.5 rounded-xl text-sm font-medium transition-all ${stateColors[state]}`}>
      {message}
    </div>
  );
}

import { AccessToken } from "livekit-server-sdk";
import { NextResponse } from "next/server";
import { randomUUID } from "crypto";

export async function GET() {
  const apiKey = process.env.LIVEKIT_API_KEY;
  const apiSecret = process.env.LIVEKIT_API_SECRET;
  const serverUrl = process.env.NEXT_PUBLIC_LIVEKIT_URL;

  if (!apiKey || !apiSecret || !serverUrl) {
    return NextResponse.json(
      { error: "LiveKit credentials not configured in .env.local" },
      { status: 500 }
    );
  }

  const roomName = `voice-rag-${randomUUID().slice(0, 8)}`;
  const participantIdentity = `user-${randomUUID().slice(0, 6)}`;

  const at = new AccessToken(apiKey, apiSecret, {
    identity: participantIdentity,
    ttl: "1h",
  });

  at.addGrant({
    room: roomName,
    roomJoin: true,
    canPublish: true,
    canSubscribe: true,
    canPublishData: true,
  });

  const token = await at.toJwt();

  return NextResponse.json({ token, serverUrl, roomName });
}

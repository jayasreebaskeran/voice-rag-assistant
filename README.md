# 🎙️ Realtime Voice-to-Voice Agentic RAG Assistant

> **Talk to your documents.** Upload a PDF, ask questions by voice, get accurate spoken answers — powered by a multi-agent pipeline with semantic retrieval and built-in failure recovery.

![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=flat&logo=python&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-14-000000?style=flat&logo=nextdotjs&logoColor=white)
![LiveKit](https://img.shields.io/badge/LiveKit-Agents-00BFFF?style=flat)
![Redis](https://img.shields.io/badge/Redis-Vector_Search-DC382D?style=flat&logo=redis&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o--mini-412991?style=flat&logo=openai&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=flat)

---

## What it does

You upload a PDF document. The system indexes it semantically into Redis. You then start a voice session — speak naturally, and the AI agent retrieves the most relevant document sections, feeds them to an LLM, and speaks back a grounded, accurate answer — all in under a second of latency.

**No hallucination by default** — the agent is instructed to answer only from retrieved context, and explicitly says so when it doesn't know.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      FRONTEND (Next.js)                 │
│  PDF Upload → base64 → LiveKit data channel             │
│  Mic audio → LiveKit Room → AI Agent                    │
└──────────────────────┬──────────────────────────────────┘
                       │ LiveKit WebRTC
┌──────────────────────▼──────────────────────────────────┐
│                   AI AGENT (Python)                     │
│                                                         │
│   Voice Input                                           │
│   Deepgram STT ──► Query Text                           │
│                        │                               │
│                        ▼                               │
│              RAG Retriever                              │
│         ┌─────────────────────┐                        │
│         │  Redis Vector Store │ ◄── PDF Indexing        │
│         │  (KNN cosine search)│     (on upload)        │
│         └─────────┬───────────┘                        │
│                   │ top-k chunks                       │
│                   ▼                                     │
│         OpenAI GPT-4o-mini                              │
│         (grounded on context)                           │
│                   │                                     │
│                   ▼                                     │
│         OpenAI TTS ──► Voice Response                   │
└─────────────────────────────────────────────────────────┘
```

---

## Features

| Feature | Details |
|---|---|
| **Real-time STT** | Deepgram Nova-2, sub-200ms transcription |
| **RAG retrieval** | Redis vector search with cosine similarity |
| **LLM** | GPT-4o-mini with retrieved context injection |
| **TTS** | OpenAI Nova voice for natural-sounding speech |
| **Failure recovery** | Redis fallback to in-memory store; empty PDF detection; context overflow trimming |
| **PDF chunking** | 500-char overlapping chunks to avoid answer fragmentation |
| **Voice Activity Detection** | Silero VAD prevents false triggers |
| **Frontend** | Next.js 14 with drag-and-drop upload and live state visualization |

---

## Failure Modes — and How They're Handled

This is the part most demos skip. Here's what breaks and how the system recovers:

| Failure | Recovery |
|---|---|
| Redis unavailable | Automatically falls back to in-memory cosine similarity store |
| Empty / scanned PDF | Agent speaks an error, session continues |
| LLM hallucination risk | RAG context injected as system prompt; agent instructed to say "I don't know" |
| Context window overflow | Sliding window message trimming in VoicePipelineAgent |
| Embedding batch failure | Zero vector fallback; affected chunks won't rank but system keeps running |
| STT empty transcript | Skipped silently; no downstream failure |

---

## Project Structure

```
voice-rag-assistant/
├── agent/
│   ├── agent.py              # LiveKit worker entrypoint, pipeline assembly
│   ├── requirements.txt
│   ├── .env.example
│   └── rag/
│       ├── document_store.py # PDF parsing + overlapping chunking
│       ├── retriever.py      # Embedding + cosine retrieval (Redis + fallback)
│       └── redis_store.py    # RediSearch KNN vector store
│
└── frontend/
    ├── app/
    │   ├── page.tsx           # Main UI — upload + session management
    │   └── api/
    │       └── connection-details/route.ts  # LiveKit token generation
    └── components/
        ├── VoiceRoom.tsx      # LiveKit room + BarVisualizer
        ├── PDFUploader.tsx    # Drag-and-drop with validation
        └── StatusBar.tsx      # Session state display
```

---

## Getting Started

### Prerequisites

- Python 3.9+
- Node.js 18+
- Redis (local via Docker, or Redis Cloud)
- Accounts: [LiveKit Cloud](https://livekit.io), [OpenAI](https://platform.openai.com), [Deepgram](https://deepgram.com)

### 1. Clone the repo

```bash
git clone https://github.com/jayasreebaskeran/voice-rag-assistant.git
cd voice-rag-assistant
```

### 2. Start Redis (easiest via Docker)

```bash
docker run -d -p 6379:6379 redis/redis-stack:latest
```

### 3. Set up the agent

```bash
cd agent
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env with your API keys
```

### 4. Set up the frontend

```bash
cd ../frontend
npm install

cp .env.local.example .env.local
# Edit .env.local with your LiveKit credentials
```

### 5. Run

In one terminal (agent):
```bash
cd agent
python agent.py dev
```

In another terminal (frontend):
```bash
cd frontend
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

---

## How to Use

1. **Upload a PDF** — drag and drop onto the upload area (max 10MB)
2. **Click "Start Voice Session"** — agent connects and greets you
3. **Ask questions by voice** — e.g. *"What is the main conclusion of this paper?"*
4. **Agent responds** — grounded in your document, spoken back in real-time

---

## Tech Stack

**Agent (Python)**
- [LiveKit Agents](https://docs.livekit.io/agents/) — real-time AI agent framework
- [Deepgram](https://deepgram.com/) — Nova-2 speech-to-text
- [OpenAI](https://platform.openai.com/) — GPT-4o-mini (LLM) + text-embedding-3-small + TTS
- [Redis](https://redis.io/) — vector storage and retrieval (RediSearch)
- [PyMuPDF](https://pymupdf.readthedocs.io/) — PDF text extraction
- [Silero VAD](https://github.com/snakers4/silero-vad) — voice activity detection

**Frontend (TypeScript)**
- [Next.js 14](https://nextjs.org/) — App Router
- [LiveKit Components React](https://docs.livekit.io/components/) — `BarVisualizer`, `VoiceAssistantControlBar`
- [Tailwind CSS](https://tailwindcss.com/) — styling

---

## Design Decisions

**Why overlapping chunks?**
A 500-char chunk with 80-char overlap ensures that answers sitting at chunk boundaries aren't split. Without overlap, the RAG system frequently misses answers that straddle two chunks.

**Why Redis over a dedicated vector DB?**
Redis serves dual purpose: vector search + session caching. For a real-time voice system, minimizing infrastructure is critical for latency. Redis KNN search at demo scale (hundreds of chunks) is sub-millisecond.

**Why explicit fallback to in-memory?**
Production systems fail. The in-memory fallback means a Redis outage degrades gracefully instead of crashing the session. The fallback is logged and visible — no silent failures.

---

## License

MIT — see [LICENSE](LICENSE)

---

*Built by [Jayasree V B](https://github.com/jayasreebaskeran) · [LinkedIn](https://linkedin.com/in/jayasree-v-b)*

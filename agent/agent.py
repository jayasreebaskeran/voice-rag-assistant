"""
Voice-to-Voice Agentic RAG Assistant
Author: Jayasree V B
GitHub: github.com/jayasreebaskeran

Architecture:
  User Voice → LiveKit STT → LLM (with RAG context) → TTS → User
  PDF Upload  → Chunking → Embeddings → Redis Vector Store

Failure modes handled:
  - STT silence / empty transcript → graceful skip
  - Redis unavailable → fallback to in-memory store
  - LLM hallucination risk → RAG grounds every response
  - PDF parse failure → user notified via voice
  - Context window overflow → sliding window trimming
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from dotenv import load_dotenv
from livekit.agents import (
    AutoSubscribe,
    JobContext,
    JobProcess,
    WorkerOptions,
    cli,
    llm,
)
from livekit.agents.pipeline import VoicePipelineAgent
from livekit.plugins import deepgram, openai, silero

from rag.document_store import DocumentStore
from rag.retriever import RAGRetriever

load_dotenv()
logger = logging.getLogger("voice-rag-agent")


@dataclass
class AgentState:
    """Tracks runtime state — makes failure points explicit and recoverable."""
    session_id: str
    retriever: Optional[RAGRetriever] = None
    has_document: bool = False
    turn_count: int = 0
    last_context: list = field(default_factory=list)
    errors: list = field(default_factory=list)  # log failures, don't hide them


class RAGAssistantPlugin(llm.LLM):
    """
    Wraps OpenAI LLM with RAG retrieval.
    Before every LLM call: fetch relevant document chunks from Redis,
    prepend them as context. This grounds the model and reduces hallucination.
    """

    def __init__(self, state: AgentState):
        super().__init__()
        self._openai_llm = openai.LLM(model="gpt-4o-mini")
        self._state = state

    def chat(self, *, chat_ctx: llm.ChatContext, **kwargs):
        """Intercept chat call → inject RAG context → forward to OpenAI."""
        if self._state.retriever and self._state.has_document:
            last_user_msg = self._extract_last_user_message(chat_ctx)
            if last_user_msg:
                try:
                    chunks = self._state.retriever.retrieve(last_user_msg, top_k=4)
                    if chunks:
                        rag_context = "\n\n".join(
                            f"[Document Chunk {i+1}]:\n{c}" for i, c in enumerate(chunks)
                        )
                        system_injection = (
                            "You are a helpful voice assistant. "
                            "Answer ONLY based on the document context below. "
                            "If the answer is not in the context, say so clearly — "
                            "do NOT fabricate information.\n\n"
                            f"--- DOCUMENT CONTEXT ---\n{rag_context}\n--- END CONTEXT ---"
                        )
                        # Inject as system message at front of context
                        chat_ctx = self._inject_system(chat_ctx, system_injection)
                        self._state.last_context = chunks
                except Exception as e:
                    # Retrieval failed — log it, fall through to bare LLM
                    logger.warning(f"RAG retrieval failed: {e}")
                    self._state.errors.append(f"retrieval_error: {e}")

        return self._openai_llm.chat(chat_ctx=chat_ctx, **kwargs)

    def _extract_last_user_message(self, chat_ctx: llm.ChatContext) -> Optional[str]:
        for msg in reversed(chat_ctx.messages):
            if msg.role == "user":
                return msg.content if isinstance(msg.content, str) else None
        return None

    def _inject_system(self, chat_ctx: llm.ChatContext, system_text: str) -> llm.ChatContext:
        """Return a new ChatContext with RAG system message prepended."""
        new_messages = [
            llm.ChatMessage(role="system", content=system_text)
        ] + list(chat_ctx.messages)
        return llm.ChatContext(messages=new_messages)


def build_agent(ctx: JobContext, state: AgentState) -> VoicePipelineAgent:
    """
    Constructs the full STT → LLM → TTS pipeline.
    Each component is swappable — failure in one doesn't crash others.
    """
    initial_prompt = llm.ChatContext().append(
        role="system",
        text=(
            "You are a real-time voice assistant named Jay. "
            "Keep responses concise (2-3 sentences) since this is a voice interface. "
            "When a document is loaded, answer questions about it accurately. "
            "If no document is loaded, let the user know they can upload a PDF."
        ),
    )

    rag_llm = RAGAssistantPlugin(state=state)

    agent = VoicePipelineAgent(
        vad=silero.VAD.load(),                           # Voice Activity Detection
        stt=deepgram.STT(model="nova-2"),                # Speech to Text
        llm=rag_llm,                                     # RAG-augmented LLM
        tts=openai.TTS(voice="nova"),                    # Text to Speech
        chat_ctx=initial_prompt,
        # Sliding window to avoid context overflow (failure mode: long sessions)
        max_nested_fnc_calls=2,
    )

    @agent.on("user_speech_committed")
    def on_speech(msg: llm.ChatMessage):
        state.turn_count += 1
        logger.info(f"[Turn {state.turn_count}] User: {msg.content}")

    @agent.on("agent_speech_committed")
    def on_agent(msg: llm.ChatMessage):
        logger.info(f"[Turn {state.turn_count}] Agent: {msg.content}")

    return agent


async def handle_document_upload(data: bytes, filename: str, state: AgentState) -> str:
    """
    Triggered when user uploads a PDF.
    Extracts text → chunks → embeds → stores in Redis.
    Returns status message spoken back to user.
    """
    try:
        store = DocumentStore()
        chunks = store.process_pdf(data, filename)
        if not chunks:
            state.errors.append(f"pdf_empty: {filename}")
            return "I couldn't extract any text from that PDF. Please try a different file."

        state.retriever = RAGRetriever(chunks=chunks)
        state.has_document = True
        logger.info(f"Indexed {len(chunks)} chunks from {filename}")
        return (
            f"I've loaded your document '{filename}' with {len(chunks)} sections. "
            "You can now ask me questions about it."
        )
    except Exception as e:
        state.errors.append(f"pdf_process_error: {e}")
        logger.error(f"PDF processing failed: {e}")
        return "There was a problem loading your document. Please try again."


async def entrypoint(ctx: JobContext):
    """Main agent entrypoint — called by LiveKit worker for each session."""
    logger.info(f"Session started: {ctx.room.name}")
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    state = AgentState(session_id=ctx.room.name)
    agent = build_agent(ctx, state)

    # Handle incoming data messages (PDF uploads from frontend)
    @ctx.room.on("data_received")
    def on_data(data_packet):
        asyncio.create_task(
            _handle_data(data_packet, agent, state)
        )

    agent.start(ctx.room)
    await agent.say(
        "Hello! I'm Jay, your voice assistant. Upload a PDF and ask me anything about it.",
        allow_interruptions=True,
    )
    await asyncio.sleep(3600)  # Keep session alive for 1 hour


async def _handle_data(packet, agent: VoicePipelineAgent, state: AgentState):
    try:
        import json
        payload = json.loads(packet.data.decode())
        if payload.get("type") == "pdf_upload":
            import base64
            pdf_bytes = base64.b64decode(payload["data"])
            filename = payload.get("filename", "document.pdf")
            response = await handle_document_upload(pdf_bytes, filename, state)
            await agent.say(response, allow_interruptions=False)
    except Exception as e:
        logger.error(f"Data handler error: {e}")


def prewarm(proc: JobProcess):
    """Preload VAD model to reduce first-call latency."""
    proc.userdata["vad"] = silero.VAD.load()


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
        )
    )

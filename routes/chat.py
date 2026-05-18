"""Blueprint reserved for chat and future GenAI workflows."""

import importlib
import os
from pathlib import Path

from dotenv import load_dotenv

# Load project-local environment variables for direct module imports as well.
load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")

try:
    from openai import OpenAI
    from openai.error import APIError
except Exception:
    OpenAI = None  # type: ignore
    APIError = Exception  # type: ignore

try:
    import google.generativeai as genai
except Exception:
    genai = None
from flask import Blueprint, jsonify, render_template, request, session

from utils import build_system_instruction
from vector_store import VectorStoreManager


chat_bp = Blueprint("chat", __name__)
v_store = VectorStoreManager()
CHAT_HISTORY_SESSION_KEY = "chat_history"
CHAT_HISTORY_STORAGE_LIMIT = 20
CHAT_HISTORY_WINDOW = 5

# Configure the OpenAI client (kept as fallback) and the Gemini client
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if OPENAI_API_KEY and OpenAI is not None:
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
    except Exception:
        client = None
else:
    client = None

# Configure Google Generative AI (Gemini) client using environment variable
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
genai_client = None
if GEMINI_API_KEY and genai is not None:
    try:
        # prefer configure if available
        if hasattr(genai, "configure"):
            genai.configure(api_key=GEMINI_API_KEY)
            genai_client = genai
        elif hasattr(genai, "Client"):
            genai_client = genai.Client(api_key=GEMINI_API_KEY)
        else:
            genai_client = genai
    except Exception:
        genai_client = None


def _get_gemini_module():
    """Load Gemini SDK lazily so runtime env/interpreter changes are reflected."""
    global genai
    if genai is not None:
        return genai
    try:
        genai = importlib.import_module("google.generativeai")
    except Exception:
        return None
    return genai


def _normalize_model_name(model_name: str) -> str:
    if model_name.startswith("models/"):
        return model_name.split("/", 1)[1]
    return model_name


def _resolve_gemini_model(gemini_mod):
    """Choose an available generateContent-capable model for the current API key."""
    preferred_models = [
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-flash-latest",
        "gemini-2.0-flash-lite",
        "gemini-pro-latest",
    ]

    available_models = []
    if hasattr(gemini_mod, "list_models"):
        try:
            for model in gemini_mod.list_models():
                methods = getattr(model, "supported_generation_methods", []) or []
                if any(method.lower() == "generatecontent" for method in methods):
                    available_models.append(_normalize_model_name(getattr(model, "name", "")))
        except Exception:
            available_models = []

    available_models = [m for m in available_models if m]

    for preferred in preferred_models:
        if preferred in available_models:
            return preferred, available_models

    if available_models:
        return available_models[0], available_models

    return "gemini-2.0-flash", available_models


def _normalize_chat_message(message):
    """Return a session-safe Gemini message dict or None if malformed."""
    if not isinstance(message, dict):
        return None

    role = (message.get("role") or "").strip()
    parts = message.get("parts") or []

    if isinstance(parts, str):
        parts = [parts]

    cleaned_parts = [str(part).strip() for part in parts if str(part).strip()]
    if role not in {"user", "model"} or not cleaned_parts:
        return None

    return {"role": role, "parts": cleaned_parts}


def _load_chat_history():
    """Load and sanitize the session chat history."""
    raw_history = session.get(CHAT_HISTORY_SESSION_KEY, [])
    return [message for message in (_normalize_chat_message(item) for item in raw_history) if message]


def _store_chat_history(history):
    """Persist a bounded chat history back into the Flask session."""
    session[CHAT_HISTORY_SESSION_KEY] = history[-CHAT_HISTORY_STORAGE_LIMIT:]
    session.modified = True


def _append_chat_message(role, text):
    """Append a single message to session history and keep the store bounded."""
    history = _load_chat_history()
    history.append({"role": role, "parts": [text]})
    _store_chat_history(history)


def _recent_chat_history(history=None, limit=CHAT_HISTORY_WINDOW):
    """Return the latest messages to send to Gemini.

    When history is omitted, the current Flask session store is used.
    """
    source_history = _load_chat_history() if history is None else history
    return source_history[-limit:]


@chat_bp.route("/")
def chat():
    active_corpus = session.get("active_corpus", [])
    openai_available = bool(os.getenv("OPENAI_API_KEY") and OpenAI is not None)
    gemini_available = bool(os.getenv("GEMINI_API_KEY") and _get_gemini_module() is not None)
    return render_template(
        "chat.html",
        active_corpus=active_corpus,
        openai_available=openai_available,
        gemini_available=gemini_available,
    )


@chat_bp.route("/query", methods=["POST"])
def query():
    """Handle JSON-based user queries using Gemini.

    Expects JSON body with keys: 'question', 'tone', 'audience', 'task'.
    Returns JSON with model response plus source trace metadata.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({
            "error": "Invalid JSON payload.",
            "debug": "Expected a JSON object body with question, tone, and audience keys."
        }), 400

    required_keys = ["question", "tone", "audience"]
    missing_keys = [key for key in required_keys if key not in data]
    if missing_keys:
        return jsonify({
            "error": "Incomplete JSON payload.",
            "debug": f"Missing required keys: {', '.join(missing_keys)}.",
            "received_keys": sorted(list(data.keys())),
        }), 400

    user_question = (data.get("question") or "").strip()
    tone = (data.get("tone") or "professional").strip()
    audience = (data.get("audience") or "general").strip()
    task = (data.get("task") or "explain").strip()

    if not user_question:
        return jsonify({
            "error": "Question cannot be empty.",
            "debug": "The question key was present but its value was blank or whitespace."
        }), 400

    if not user_question:
        return jsonify({"error": "Question cannot be empty."}), 400

    # Initialize a fresh VectorStoreManager and get active corpus
    vs = VectorStoreManager()
    active_corpus = session.get("active_corpus", [])
    if not active_corpus:
        return jsonify({"error": "No documents selected. Please select files to query."}), 400

    # Query the top 5 context chunks strictly within the active corpus and capture IDs for traceability
    context_chunks = []
    if vs.collection is not None:
        if len(active_corpus) == 1:
            where_filter = {"filename": active_corpus[0]}
        else:
            where_filter = {"filename": {"$in": active_corpus}}

        try:
            raw_results = vs.collection.query(
                query_texts=[user_question],
                n_results=5,
                where=where_filter,
                include=["documents", "metadatas", "distances"],
            )

            documents = (raw_results.get("documents") or [[]])[0]
            metadatas = (raw_results.get("metadatas") or [[]])[0]
            distances = (raw_results.get("distances") or [[]])[0]
            ids = (raw_results.get("ids") or [[]])[0]

            for idx, doc in enumerate(documents):
                metadata = metadatas[idx] if idx < len(metadatas) else {}
                context_chunks.append(
                    {
                        "document": doc,
                        "filename": (metadata or {}).get("filename"),
                        "distance": distances[idx] if idx < len(distances) else None,
                        "chunk_id": ids[idx] if idx < len(ids) else None,
                    }
                )
        except Exception:
            context_chunks = vs.query_context(
                active_files=active_corpus,
                query_text=user_question,
                n_results=5,
            )
    else:
        context_chunks = vs.query_context(
            active_files=active_corpus,
            query_text=user_question,
            n_results=5,
        )

    # Build source metadata for UI/client-side explainability.
    source_filenames = []
    source_chunk_ids = []
    source_chunks = []
    for chunk in context_chunks:
        filename = chunk.get("filename")
        chunk_id = chunk.get("chunk_id")

        if filename and filename not in source_filenames:
            source_filenames.append(filename)

        if chunk_id and chunk_id not in source_chunk_ids:
            source_chunk_ids.append(chunk_id)

        if filename or chunk_id:
            source_chunks.append({"filename": filename, "chunk_id": chunk_id})

    if not context_chunks:
        context_text = "(No relevant context found in the selected documents.)"
    else:
        context_text = "\n\n".join([f"[{c['filename']}]\n{c['document']}" for c in context_chunks])

    # Configure the official google.generativeai SDK from environment
    gemini_key = os.environ.get("GEMINI_API_KEY")
    gemini_mod = _get_gemini_module()
    if not gemini_key or gemini_mod is None:
        return jsonify({"error": "GEMINI_API_KEY not set or google.generativeai not installed."}), 500

    try:
        # Configure SDK (some versions use genai.configure)
        if hasattr(gemini_mod, "configure"):
            gemini_mod.configure(api_key=gemini_key)
    except Exception:
        # continue; some SDK variants may not need explicit configure
        pass

    # Build grounded prompts
    system_prompt = build_system_instruction(tone, audience, task)

    user_prompt = f"Context from documents:\n{context_text}\n\nUser question: {user_question}\n\nPlease answer the question based on the context above."

    recent_history = _recent_chat_history()
    gemini_contents = recent_history + [{"role": "user", "parts": [user_prompt]}]

    # Resolve a compatible model for the current key/API version
    model_name, available_models = _resolve_gemini_model(gemini_mod)

    # Call Gemini model
    ai_output = None
    try:
        # Official google-generativeai path
        if hasattr(gemini_mod, "GenerativeModel"):
            try:
                model = gemini_mod.GenerativeModel(model_name, system_instruction=system_prompt)
            except TypeError:
                model = gemini_mod.GenerativeModel(model_name)
            resp = model.generate_content(gemini_contents)
            ai_output = getattr(resp, "text", None)
            if not ai_output and getattr(resp, "candidates", None):
                parts = []
                for cand in resp.candidates:
                    content = getattr(cand, "content", None)
                    cand_parts = getattr(content, "parts", None) if content else None
                    if cand_parts:
                        for part in cand_parts:
                            part_text = getattr(part, "text", None)
                            if part_text:
                                parts.append(part_text)
                if parts:
                    ai_output = "\n".join(parts)

        # Compatibility path used by some newer SDK variants
        elif hasattr(gemini_mod, "generate"):
            resp = gemini_mod.generate(model=model_name, input=gemini_contents)
            ai_output = getattr(resp, "output_text", None) or getattr(resp, "text", None)
            if not ai_output and getattr(resp, "candidates", None):
                ai_output = getattr(resp.candidates[0], "text", None)

        # Legacy fallback: genai.chat.create
        elif hasattr(gemini_mod, "chat") and hasattr(gemini_mod.chat, "create"):
            messages = [{"role": "system", "content": system_prompt}]
            for message in recent_history:
                messages.append({"role": message["role"], "content": "\n".join(message["parts"])})
            messages.append({"role": "user", "content": user_prompt})
            resp = gemini_mod.chat.create(model=model_name, messages=messages)
            ai_output = getattr(resp, "output", None) or getattr(resp, "content", None)
            if isinstance(ai_output, list):
                ai_output = "\n".join([getattr(x, "content", x) for x in ai_output])

        else:
            return jsonify({"error": "google.generativeai SDK does not expose a compatible generation method."}), 500

    except Exception as e:
        available_hint = ", ".join(available_models[:5]) if available_models else "none detected"
        return jsonify({"error": f"Gemini generation failed: {e}. Selected model: {model_name}. Available generateContent models: {available_hint}"}), 500

    if not ai_output:
        ai_output = "No response generated."

    _append_chat_message("user", user_prompt)
    _append_chat_message("model", ai_output)

    return jsonify(
        {
            "response": ai_output,
            "sources": source_filenames,
            "source_chunk_ids": source_chunk_ids,
            "source_chunks": source_chunks,
        }
    )
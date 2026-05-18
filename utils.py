import magic

ALLOWED_EXTENSIONS = {"txt", "md", "pdf", "py", "js"}

ALLOWED_MIMES = {
    "text/plain": {"txt"},
    "text/markdown": {"md"},
    "application/pdf": {"pdf"},
    "text/x-python": {"py"},
    "application/javascript": {"js"},
    "text/javascript": {"js"},
}


def count_tokens(text: str) -> int:
    """Estimate token count using a standard character-length heuristic.

    This uses ~4 characters per token, a common rough estimate for English text.
    It is fast and model-agnostic, intended for pre-checks in RAG pipelines.
    """
    if not text:
        return 0

    # Round up so partial token-sized fragments count toward the estimate.
    return (len(text) + 3) // 4


def build_system_instruction(tone: str, audience: str, task: str) -> str:
    """Build a structured markdown system instruction for Gemini prompts.

    The returned string is intentionally concise, human-readable, and easy to
    pass into a model configuration field or prepend to a request payload.
    """
    tone_value = (tone or "").strip() or "professional"
    audience_value = (audience or "").strip() or "general"
    task_value = (task or "").strip() or "answer the user clearly"

    return (
        "# Persona\n"
        "You are a helpful, grounded AI assistant for a retrieval-augmented chat system.\n\n"
        "# Prompt Steering\n"
        f"- Tone: {tone_value}\n"
        f"- Audience: {audience_value}\n"
        f"- Task: {task_value}\n\n"
        "# Response Rules\n"
        "- Use the provided document context as the primary source of truth.\n"
        "- Be accurate, concise, and directly responsive to the user request.\n"
        "- If the context is insufficient, say so plainly and avoid inventing details.\n"
        "- Prefer clear Markdown formatting when it improves readability."
    )


def allowed_file(filename: str) -> bool:
    """Check if filename has allowed extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def validate_file_content(file_obj, filename: str) -> tuple[bool, str | None]:
    """Validate file content using magic numbers."""
    file_obj.seek(0)
    file_bytes = file_obj.read(512)
    file_obj.seek(0)

    try:
        mime = magic.from_buffer(file_bytes, mime=True)
    except Exception:
        return False, "Could not determine file type"

    if "." not in filename:
        return False, "Invalid filename"

    ext = filename.rsplit(".", 1)[1].lower()

    if mime not in ALLOWED_MIMES:
        return False, f"File type {mime} not allowed"

    if ext not in ALLOWED_MIMES[mime]:
        return False, f"Extension .{ext} does not match actual file type {mime}"

    return True, None

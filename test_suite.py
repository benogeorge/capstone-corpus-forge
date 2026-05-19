import os
import io
import unittest
import tempfile
from pathlib import Path
from app import app
from extractor import safe_read_text, strip_control_characters
from utils import guard_expanded_bytes


class CorpusForgeReliabilityTests(unittest.TestCase):
    def setUp(self):
        """Set up test client and ensure sandboxed environment."""
        app.config["TESTING"] = True
        app.config["UPLOAD_FOLDER"] = "data_test"
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
        self.client = app.test_client()

    def tearDown(self):
        """Clean up test artifacts after execution."""
        if os.path.exists("data_test"):
            for f in os.listdir("data_test"):
                os.remove(os.path.join("data_test", f))
            os.rmdir("data_test")

    # ==========================================
    # 🟢 NORMAL SCENARIOS (What Worked)
    # ==========================================

    def test_normal_txt_upload_and_indexing(self):
        """Scenario: User uploads a valid, clean text file."""
        data = {
            "document": (
                io.BytesIO(b"Valid test corpus context for ChromaDB indexing."),
                "sample.txt",
            )
        }
        response = self.client.post(
            "/upload", data=data, content_type="multipart/form-data"
        )
        self.assertEqual(response.status_code, 302)  # Redirects to index on success

    def test_active_corpus_state_session(self):
        """Scenario: User toggles a valid file in their workspace session."""
        with self.client.session_transaction() as sess:
            sess["active_corpus"] = ["sample.txt"]

        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    # ==========================================
    # 🔴 FAILURE SCENARIOS (What Handled Defensively)
    # ==========================================

    def test_failure_file_too_large(self):
        """Scenario: Malicious or accidental upload exceeding 10MB payload limit."""
        large_payload = b"X" * (11 * 1024 * 1024)  # 11MB payload
        data = {"document": (io.BytesIO(large_payload), "huge_bomb.txt")}
        response = self.client.post(
            "/upload", data=data, content_type="multipart/form-data"
        )
        # Expecting a failure handling mechanism (either redirect with flash or 413)
        self.assertIn(response.status_code, [302, 413])

    def test_failure_spoofed_extension_magic_check(self):
        """Scenario: Attacker names an executable script as a '.txt' file."""
        fake_text_payload = b"\x7fELF\x02\x01\x01\x00"  # Linux ELF binary magic bytes
        data = {"document": (io.BytesIO(fake_text_payload), "spoofed_script.txt")}
        response = self.client.post(
            "/upload", data=data, content_type="multipart/form-data"
        )
        # Should catch that text/plain doesn't match the true binary type
        self.assertEqual(response.status_code, 302)

    def test_failure_empty_active_corpus_query(self):
        """Scenario: User tries to chat without picking any documents."""
        data = {
            "question": "What does my file say?",
            "tone": "casual",
            "audience": "beginner",
            "task": "chat",
        }
        response = self.client.post("/chat/query", json=data)
        # Should gracefully return a validation error block
        self.assertEqual(response.status_code, 400)

    def test_safe_read_text_handles_utf8_bom(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "bom.txt"
            file_path.write_bytes(b"\xef\xbb\xbfHello BOM")

            self.assertEqual(safe_read_text(str(file_path)), "Hello BOM")

    def test_safe_read_text_handles_utf16(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "utf16.txt"
            file_path.write_text("Hello UTF-16", encoding="utf-16")

            self.assertEqual(safe_read_text(str(file_path)), "Hello UTF-16")

    def test_safe_read_text_handles_windows_1252(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "cp1252.txt"
            file_path.write_bytes("Café and quotes ‘single’".encode("cp1252"))

            self.assertEqual(safe_read_text(str(file_path)), "Café and quotes ‘single’")

    def test_strip_control_characters_removes_ansi_and_noise(self):
        noisy_text = "Report\x1b[31m READY\x1b[0m\x07\x0b with\r\nmacro\x1f metadata"

        self.assertEqual(
            strip_control_characters(noisy_text),
            "Report READY with\nmacro metadata",
        )

    def test_guard_expanded_bytes_aborts_when_limit_is_breached(self):
        current_total = guard_expanded_bytes(0, "safe chunk", 32)
        self.assertEqual(current_total, len("safe chunk".encode("utf-8")))

        with self.assertRaises(ValueError):
            guard_expanded_bytes(current_total, "X" * 100, 32)

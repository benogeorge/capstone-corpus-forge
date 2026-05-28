import logging
import os
import re
import time
from pathlib import Path

# Disable ChromaDB telemetry to avoid Python 3.14 + protobuf incompatibility
os.environ["ANONYMIZED_TELEMETRY"] = "False"

try:
    import chromadb
    from chromadb.config import Settings
    from chromadb.utils import embedding_functions
except (ImportError, TypeError) as e:
    # Python 3.14+ has protobuf incompatibility with ChromaDB
    # This is a known issue; use Python 3.11 or 3.12 for production
    print(f"Warning: ChromaDB import failed: {e}")
    print("ChromaDB vector storage will not be available.")
    print("Please use Python 3.11 or 3.12 for full functionality.")
    chromadb = None
    Settings = None
    embedding_functions = None


def setup_vector_logger() -> logging.Logger:
    """Create an isolated file logger for vector-store audit events."""

    logger = logging.getLogger("corpus_forge.vector_store")
    if logger.handlers:
        return logger

    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(logs_dir / "vector_store.log", encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        )
    )

    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.propagate = False
    return logger


vector_logger = setup_vector_logger()


class VectorStoreManager:
    def __init__(
        self,
        db_path: str = "chroma_db",
        collection_name: str = "corpus_forge_collection",
        workspace_scope: str | None = None,
    ):
        """Initializes a persistent local ChromaDB client and collection."""
        if chromadb is None:
            self.client = None
            self.collection = None
            self.embedding_function = None
            return

        # Ensure the storage directory exists
        os.makedirs(db_path, exist_ok=True)

        # Initialize persistent client on your local machine
        # Explicitly disable anonymized telemetry to avoid posthog API mismatch noise.
        client_settings = Settings(anonymized_telemetry=False) if Settings else None
        self.client = chromadb.PersistentClient(path=db_path, settings=client_settings)

        # Allow each workspace or tenant to get its own isolated collection.
        resolved_collection_name = self._build_scoped_collection_name(
            collection_name=collection_name,
            workspace_scope=workspace_scope,
        )

        # Use ChromeDB's default embedding function (all-MiniLM-L6-v2)
        self.embedding_function = embedding_functions.DefaultEmbeddingFunction()

        # Get or create the collection
        self.collection = self.client.get_or_create_collection(
            name=resolved_collection_name, embedding_function=self.embedding_function
        )

    @staticmethod
    def _build_scoped_collection_name(
        collection_name: str, workspace_scope: str | None = None
    ) -> str:
        """Build a stable, isolated collection name for a workspace or tenant."""
        scope_source = workspace_scope or os.environ.get("CORPUS_FORGE_WORKSPACE")
        if not scope_source:
            return collection_name

        safe_scope = re.sub(r"[^a-zA-Z0-9_-]+", "_", scope_source.strip()).strip("_")
        if not safe_scope:
            return collection_name

        return f"{collection_name}__{safe_scope}"

    def add_document(
        self, filename: str, text: str, chunk_size: int = 1000, chunk_overlap: int = 200
    ):
        """
        Splits a document's extracted text into overlapping chunks and stores them.
        Fulfills Layer 2 Challenge A: Fixed-size overlapping chunking strategy.
        """
        if self.collection is None:
            # ChromaDB unavailable; silently skip
            vector_logger.warning("add_document skipped for %s because collection is unavailable", filename)
            return

        if not text.strip():
            vector_logger.info("add_document skipped for %s because extracted text is empty", filename)
            return

        # First, remove any existing chunks for this specific file to prevent duplicates
        self.collection.delete(where={"filename": filename})

        chunks = []
        metadata_list = []
        ids = []

        # Perform the fixed-size sliding window chunking
        start = 0
        chunk_idx = 0
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]

            chunks.append(chunk)
            metadata_list.append({"filename": filename})
            ids.append(f"{filename}_chunk_{chunk_idx}")

            # Slide the window forward by chunk_size minus the overlap
            start += chunk_size - chunk_overlap
            chunk_idx += 1

        # Add the batch of chunks directly to ChromaDB
        if chunks:
            start_time = time.perf_counter()
            self.collection.add(documents=chunks, metadatas=metadata_list, ids=ids)
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            vector_logger.info(
                "add_document filename=%s chunks=%d chunk_size=%d chunk_overlap=%d latency_ms=%.2f",
                filename,
                len(chunks),
                chunk_size,
                chunk_overlap,
                elapsed_ms,
            )

    def delete_document_chunks(self, filename: str) -> None:
        """Delete all chunks associated with a document filename.

        Args:
            filename: Name of the document to delete.
        """
        if self.collection is None:
            # ChromaDB unavailable; silently skip
            vector_logger.warning("delete_document skipped for %s because collection is unavailable", filename)
            return

        try:
            start_time = time.perf_counter()
            self.collection.delete(where={"filename": filename})
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            vector_logger.info(
                "delete_document filename=%s latency_ms=%.2f",
                filename,
                elapsed_ms,
            )
        except Exception as e:
            print(f"Error deleting document {filename} from vector store: {e}")
            vector_logger.exception("delete_document failed for %s", filename)

    def query_context(
        self, active_files: list[str], query_text: str, n_results: int = 5
    ) -> list[dict]:
        """
        Queries ChromaDB for relevant text chunks, filtered strictly by active files.
        Returns a list of dictionaries with document, filename, and distance.

        Args:
            active_files: List of filenames to search within.
            query_text: The query string.
            n_results: Maximum number of results to return.

        Returns:
            List of dicts with keys 'document', 'filename', 'distance'.
        """
        if self.collection is None:
            # ChromaDB unavailable; return empty results
            vector_logger.warning("query_context skipped because collection is unavailable")
            return []

        if not active_files or not query_text.strip():
            vector_logger.info(
                "query_context skipped because active_files=%d query_empty=%s",
                len(active_files) if active_files else 0,
                not query_text.strip(),
            )
            return []

        # Enforce strict metadata filtering so we only search files in the active corpus
        if len(active_files) == 1:
            where_filter = {"filename": active_files[0]}
        else:
            where_filter = {"filename": {"$in": active_files}}

        try:
            start_time = time.perf_counter()
            results = self.collection.query(
                query_texts=[query_text], n_results=n_results, where=where_filter
            )
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            # Build structured results
            formatted_results = []
            if results and "documents" in results and results["documents"]:
                for doc, metadata, distance in zip(
                    results["documents"][0],
                    results["metadatas"][0],
                    results["distances"][0],
                ):
                    formatted_results.append(
                        {
                            "document": doc,
                            "filename": metadata.get("filename"),
                            "distance": distance,
                        }
                    )

            vector_logger.info(
                "query_context active_files=%d results=%d n_results=%d latency_ms=%.2f",
                len(active_files),
                len(formatted_results),
                n_results,
                elapsed_ms,
            )

            return formatted_results

        except Exception as e:
            print(f"Error querying ChromaDB vector space: {e}")
            vector_logger.exception("query_context failed for active_files=%d", len(active_files))
            return []

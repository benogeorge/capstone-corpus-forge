# Project Report

## Team Members

- Beno GEORGE, BENO.GEORGE@EPITA.FR, benogeorge
- Redowan Ahmed SAMEER, redowan-ahmed.sameer@epita.fr, SameerAhmed772
- Demod Singh Tamang, Demod-singh.tamang@epita.fr, demod-s-tmg

## Project Idea

Our project is called Corpus Forge. It is a small local Retrieval-Augmented Generation application. The idea is simple: a user uploads documents or code files, selects which files should be active, and then asks questions about that selected corpus.

We used the capstone kick-off PDFs from the `data/` folder as our project brief and reference material. They helped us stay focused on the course goal: build something real, use AI during development, and explain clearly what we learned from the process.

## Initial Design

At the beginning, we planned a simple Flask application with one upload page and one chat page. The first version was closer to a single-file app, but that became hard to manage as the project grew.

The main design choices were:

- Flask for the backend because it is lightweight and easy to understand.
- Flask Blueprints to split ingestion routes and chat routes.
- ChromaDB for local vector storage.
- Google Gemini for answering questions from retrieved context.
- A `data/` folder as the local upload workspace.
- Separate HTML, CSS, and JavaScript files for the frontend.

The app works in this order:

1. The user uploads a supported file.
2. The backend validates and extracts text from the file.
3. The text is cleaned and split into overlapping chunks.
4. The chunks are saved in ChromaDB.
5. The user selects active files.
6. The chat route retrieves only from the active corpus and sends grounded context to Gemini.

## Engineering Decisions

### Safer File Uploads

We did not want to trust only the file extension. A file can be named `.txt` even if the content is not really text. So we added validation around file type, file size, and empty files. This made the ingestion route safer and easier to test.

### Blueprints Instead of One Big App File

The first structure was too crowded. Moving ingestion logic into `routes/ingestion.py` and chat logic into `routes/chat.py` made the project cleaner. It also made it easier for the team to work on different parts without constantly touching the same file.

### Local Vector Store

We used ChromaDB because it lets the app keep embeddings locally. This matched the idea of a local workspace and avoided needing an external vector database service.

### Active Corpus Filtering

The app does not query every uploaded file every time. It only searches files selected in `session['active_corpus']`. This made the answers more relevant and reduced the chance of mixing unrelated documents.

### Defensive Chat Behavior

We added checks for empty questions, missing JSON fields, empty active corpus, and weak retrieved context. The goal was to avoid giving fake answers when the app did not have enough information.

## Who Did What

### Redowan Ahmed SAMEER

Redowan did a large part of the early application build. Based on the Git history, his work included:

- setting up the initial Flask server and upload route
- adding secure file validation and size limits
- moving shared validation logic into `utils.py`
- helping split the app into routes and templates
- connecting ingestion to vector indexing
- building and modularizing the chat UI with HTML, CSS, and JavaScript
- adding reliability tests for normal uploads and defensive failure cases
- writing early README and report documentation

This work formed the base application that the rest of the team built on.

### Demod Singh Tamang

Demod focused mainly on the AI behavior, prompting, and retrieval safety side. Based on the Git history, his work included:

- implementing the dynamic system instruction builder
- adding grounding guardrails to reduce hallucination
- working through chat memory and session behavior
- exploring streaming versus normal JSON responses
- adding validation around empty active corpus queries
- improving PDF text-cleaning ideas
- reviewing prompt injection risks
- adding retry and rate-limit handling patterns
- keeping deleted files and vector chunks synchronized
- adding workspace-level vector collection isolation

This work made the AI side safer and closer to the course expectations around responsible AI-assisted software development.

### Beno GEORGE

Beno focused on final integration, cleanup, reporting, and repository consistency. Based on the Git history, his work included:

- reviewing and finalizing the project report
- adding the final team member details
- fixing the missing `re` import in `vector_store.py`
- syncing and pushing final commits to the shared `demod-s-tmg/capstone-corpus-forge` repository
- checking the final state of the project and keeping the submission files consistent

This work helped bring the project into a cleaner final submission state.

## AI Collaboration

AI tools were used throughout the project, but we did not treat AI output as final code automatically. We used AI mostly as a helper for explanations, design choices, debugging ideas, and first drafts.

Examples of how we used AI:

- asking why file extension checks are not enough
- asking how Flask Blueprints help with structure
- asking how RAG chunking and vector stores work
- asking how to prevent hallucinations when context is weak
- asking how to test normal and failure cases
- using AI to improve report wording and documentation

AI helped us move faster, but we still had to check the code, run tests, inspect errors, and adjust suggestions to fit our actual repo.

## Failures and Iterations

The project did not work perfectly on the first try.

Some things that failed or needed redesign:

- The app became too crowded when too much logic stayed inside `app.py`.
- File validation needed to be stronger than just checking names.
- Splitting routes created import problems until shared helpers were moved out.
- Chat requests needed better validation for missing fields and empty active corpus.
- Vector chunks needed to be deleted when the source file was deleted.
- ChromaDB and dependency behavior sometimes caused noisy warnings during local testing.

Each problem helped us make the project more stable. The biggest improvement was moving from a quick prototype toward a more structured app.

## When AI Was Wrong or Incomplete

AI suggestions were useful, but not always correct.

Sometimes the advice was too general. For example, an answer might explain Flask structure correctly, but the code still needed changes to match our exact files and route names. Sometimes AI also suggested code that looked good but did not cover edge cases like empty corpora, missing JSON fields, or unsafe file paths.

We handled this by:

- reading the generated code before using it
- checking imports and route names against the actual project
- running tests when possible
- keeping changes small enough to review
- rejecting suggestions that did not fit the repo

This was one of the most important lessons of the project. AI can help a lot, but the developer still has to verify the final result.

## Testing and Validation

We added a test suite covering the main reliability cases:

- uploading a normal text file
- keeping active corpus state in the session
- rejecting oversized files
- handling spoofed file content
- rejecting chat queries with no active corpus
- reading different text encodings safely
- removing control characters before chunking
- stopping extraction when expanded text becomes too large

These tests gave us more confidence that the app handled both normal use and some failure cases.

## Lessons Learned

We learned that a working AI app is not only about calling an LLM API. The hard parts are around the edges: validating files, cleaning text, chunking content, keeping state consistent, and making sure the model only answers from available context.

We also learned that team work is easier when the architecture is split well. Once ingestion, chat, vector storage, utilities, and frontend files were separated, the project became much easier to understand.

The final lesson is about AI-assisted development. AI was very helpful for learning and speed, but it was not a replacement for testing, reading errors, and making our own engineering decisions.

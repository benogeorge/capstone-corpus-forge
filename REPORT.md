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

### Frontend Structure

The frontend was kept simple and readable. The corpus management page is in `templates/index.html`, and the chat page is in `templates/chat.html`. The chat styling is separated into `static/css/chat.css`, and the browser behavior is handled in `static/js/chat.js`.

The HTML files define the actual pages the user sees. The CSS file gives the chat workspace a cleaner interface, with panels, message bubbles, buttons, and responsive spacing. The JavaScript file handles form submission, sends chat requests to the Flask backend, shows user and assistant messages, escapes unsafe text before displaying it, manages loading states, and gives the user a retry button if a request times out.

## Who Did What

### Redowan Ahmed SAMEER

Redowan worked mainly on the first working version of the application, the ingestion flow, the frontend structure, and the testing base. His work helped turn the project from an idea into a usable Flask application.

- setting up the initial Flask server and upload route
- adding secure file validation and size limits
- separating shared validation helpers into `utils.py`
- helping move the project from one large file into routes and templates
- connecting uploaded files to the vector indexing flow
- building the main HTML pages for corpus management and chat
- organizing the chat frontend with CSS and JavaScript files
- adding reliability tests for normal uploads and failure cases
- preparing early README and project documentation

This work gave the team a strong base: users could upload files, manage a corpus, open the chat page, and test important behavior.

### Demod Singh Tamang

Demod worked mainly on the AI behavior, prompt design, retrieval safety, and session logic. His work helped make the chat side more reliable and more aligned with the course focus on AI-assisted software development.

- implementing the dynamic system instruction builder
- adding grounding guardrails to reduce hallucination
- improving chat memory and session behavior
- comparing streaming responses with normal JSON responses
- validating empty active corpus queries before vector search
- improving PDF extraction and text-cleaning ideas
- reviewing prompt injection risks and defensive patterns
- exploring retry and rate-limit handling for API calls
- keeping deleted files and vector chunks synchronized
- adding workspace-level vector collection isolation

This work made the AI features safer: the app became better at refusing weak context, keeping user sessions separate, and avoiding stale vector data.

### Beno GEORGE

Beno worked on code reliability, extraction safety, frontend behavior, vector logging, final integration, and submission cleanup. His work helped make the app more defensive and made sure the final version was pushed to the correct shared repository.

- improving `extractor.py` with safer text reading for UTF-8 BOM, UTF-16, Windows-1252, and fallback encodings
- cleaning control characters and ANSI escape sequences before chunking and embeddings
- adding expanded-byte protection for compressed or unusual documents
- adding regression tests for encodings, control cleanup, and expanded-byte limits
- improving `static/js/chat.js` with safe rendering for retrieved text
- adding frontend timeout, loading, and retry behavior for stuck requests
- adding vector-store audit logging for add, delete, and query operations
- fixing scoped vector collection naming and final import issues
- rewriting and finalizing the report, journal details, and shared GitHub submission state

This work improved the app's reliability: extraction became safer, the chat UI handled failures better, and the final version was kept consistent in `demod-s-tmg/capstone-corpus-forge`.

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

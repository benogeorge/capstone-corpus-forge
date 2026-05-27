# Project Report

## Team Members

- Name, EPITA email, GitHub username
- Name, EPITA email, GitHub username

## Initial Design

The project started as a local Retrieval-Augmented Generation workspace for ingesting files, building embeddings, and querying them through a chat interface. We chose Flask because it is simple to structure, easy to extend, and fits a small team project well.

Our first assumptions were:
- documents would be small enough to process locally
- users would work inside a single sandboxed corpus
- vector search should stay persistent across sessions
- the UI should stay lightweight and easy to debug

The main technical choices were:
- Flask blueprints for separation of concerns
- a local vector store for persistence
- chunked text extraction to preserve retrieval quality
- explicit validation and path checks for uploaded and deleted files

## Engineering Decisions

### Flask Blueprints

We split the application into `routes/ingestion.py` and `routes/chat.py` instead of keeping everything inside `app.py`. The alternative was a monolithic app file, but that became hard to maintain and risky to merge. Blueprints made the code easier to read, test, and extend.

### File Validation

We preferred content-based validation over extension-only checks. The alternative was trusting file names, but that would allow unsafe uploads to slip through. Using real file inspection reduced that risk.

### Path Safety

For deletion and file access, we used absolute-path validation and directory boundary checks. A simpler relative-path approach would have been shorter, but it would have been much easier to exploit with traversal inputs.

### Vector Storage

We used persistent local storage rather than an in-memory index. That choice made the corpus reusable across restarts and kept the project closer to a real deployment workflow.

## Who Did What?

The original split was:
- one person focused on ingestion and file safety
- one person focused on the chat and retrieval flow
- one person focused on the frontend and presentation layer

As the project evolved, responsibilities overlapped more. Some work moved into shared debugging and integration, especially around chunking, persistence, and request handling.

## AI Collaboration

We used AI tools in three main ways:
- to review security-sensitive code paths before implementation
- to explain architectural tradeoffs and framework patterns
- to help us refine the report structure and wording

AI influenced the project most during refactoring and defensive programming. It pushed us toward cleaner module boundaries and stronger validation logic. It also helped us learn by explaining why certain patterns were safer than the first draft ideas we had.

We evaluated AI suggestions by checking them against the repo behavior, running the app or tests where possible, and comparing the output with our intended design. When AI gave a suggestion that did not fit our codebase, we either adjusted it or discarded it.

## Failures and Iterations

Some of the biggest issues came from early integration:
- filename validation was too weak until we switched to content-based checks
- route logic was too tightly coupled before we split the app into blueprints
- path handling needed redesign once we tested deletion and traversal edge cases
- chunking and retrieval behavior needed tuning so the chat stayed relevant

These failures were useful because they showed where the architecture was too optimistic and where the system needed stronger defensive boundaries.

## When AI Failed or Was Wrong

AI suggestions were not always correct on the first try. Some advice was:
- too generic for our exact Flask structure
- incomplete about security boundaries
- overly confident about file handling assumptions
- not aligned with the way the repo was organized

We caught these issues by reading the generated code carefully, checking whether the imports and routes matched our app structure, and validating behavior with tests or manual runs. When something looked fragile, we rewrote it instead of forcing it in.

## Lessons Learned

This project improved both our technical and teamwork skills:
- we learned how to structure a small Flask app in a maintainable way
- we practiced defensive thinking around uploads, paths, and local persistence
- we got better at turning rough AI output into something reliable
- we saw that good architecture makes later debugging much easier

The biggest lesson was that AI is most useful as a collaborator, not an authority. It can speed up design and explanation, but we still had to verify every important decision ourselves.

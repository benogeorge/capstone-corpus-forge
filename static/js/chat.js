document.addEventListener("DOMContentLoaded", () => {
    const endpoint = document.body.dataset.chatEndpoint || "/chat/query";
    const requestTimeoutSeconds = 15;
    const promptCountEl = document.getElementById('promptCount');
    const tokenUsageEl = document.getElementById('tokenUsage');
    const chatForm = document.getElementById("chatForm");
    const chatLog = document.getElementById("chatLog");
    const questionInput = document.getElementById("questionInput");
    const sendButton = document.getElementById("sendButton");
    const errorContainer = document.getElementById("errorContainer");
    const audienceSelect = document.getElementById("audience");
    const toneSelect = document.getElementById("tone");
    const taskSelect = document.getElementById("task");

    if (!chatForm || !chatLog || !questionInput || !sendButton || !errorContainer) {
        return;
    }

    const initialButtonText = sendButton.textContent;
    let activeRequestTimers = [];
    let lastSubmission = null;

    function escapeHtml(unsafeString) {
        return String(unsafeString)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/\"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function clearActiveRequestTimers() {
        while (activeRequestTimers.length > 0) {
            const timerId = activeRequestTimers.pop();
            clearTimeout(timerId);
            clearInterval(timerId);
        }
    }

    function clearWelcomeCard() {
        const welcomeCard = chatLog.querySelector(".welcome-card");
        if (welcomeCard) {
            welcomeCard.remove();
        }
    }

    function smoothScrollToBottom() {
        chatLog.scrollTo({
            top: chatLog.scrollHeight,
            behavior: "smooth",
        });
    }

    function setError(message, retryHandler = null) {
        errorContainer.replaceChildren();

        if (!message) {
            return;
        }

        const messageNode = document.createElement("span");
        messageNode.textContent = message;
        errorContainer.appendChild(messageNode);

        if (retryHandler) {
            const retryButton = document.createElement("button");
            retryButton.type = "button";
            retryButton.className = "retry-button";
            retryButton.textContent = "Retry";
            retryButton.addEventListener("click", retryHandler);
            errorContainer.appendChild(retryButton);
        }
    }

    function clearError() {
        errorContainer.replaceChildren();
    }

    function appendMessage(role, message, extraClass = "") {
        clearWelcomeCard();

        const messageNode = document.createElement("article");
        messageNode.className = `message ${role} ${extraClass}`.trim();
        messageNode.textContent = message;

        chatLog.appendChild(messageNode);
        smoothScrollToBottom();
        return messageNode;
    }

    function setLoadingState(isLoading) {
        sendButton.disabled = isLoading;
        sendButton.textContent = isLoading ? "Sending..." : initialButtonText;
        questionInput.readOnly = isLoading;
    }

    async function parseResponse(response) {
        const contentType = response.headers.get("content-type") || "";

        if (contentType.includes("application/json")) {
            return response.json();
        }

        const text = await response.text();
        return { error: text || "Unexpected response from server." };
    }

    function createElementFromHTML(htmlString) {
        const div = document.createElement('div');
        div.innerHTML = htmlString.trim();
        return div.firstChild;
    }

    function appendHTMLMessage(role, node) {
        clearWelcomeCard();
        const wrapper = document.createElement('article');
        wrapper.className = `message ${role}`;
        wrapper.appendChild(node);
        chatLog.appendChild(wrapper);
        smoothScrollToBottom();
        return wrapper;
    }

    function parseFlashcardsText(text) {
        const lines = text.split(/\r?\n/).map(l => l.trim()).filter(Boolean);
        const cards = [];
        for (const line of lines) {
            // Try 'Q: ... | A: ...' or 'Q: ... | Answer: ...' or '... | A: ...'
            const sep = line.indexOf('|');
            if (sep > -1) {
                const qpart = line.slice(0, sep).replace(/^\d+\)\s*/, '').replace(/^Q:\s*/i, '').trim();
                const apart = line.slice(sep+1).replace(/^A:\s*/i, '').replace(/^Answer:\s*/i, '').trim();
                if (qpart) cards.push({q: qpart, a: apart});
                continue;
            }
            // Otherwise if line looks like 'Question - Answer'
            const dash = line.indexOf(' - ');
            if (dash > -1) {
                cards.push({q: line.slice(0, dash).trim(), a: line.slice(dash+3).trim()});
                continue;
            }
        }
        return cards;
    }

    function renderFlashcards(cards) {
        const container = document.createElement('div');
        container.className = 'flashcards-grid';
        for (const card of cards) {
            const el = document.createElement('div');
            el.className = 'flashcard';
            const q = document.createElement('div'); q.className = 'q'; q.textContent = card.q;
            const a = document.createElement('div'); a.className = 'a'; a.textContent = card.a;
            const btn = document.createElement('button'); btn.className = 'reveal'; btn.textContent = 'Reveal Answer';
            btn.addEventListener('click', () => { a.style.display = a.style.display === 'none' ? 'block' : 'none'; btn.textContent = a.style.display === 'none' ? 'Reveal Answer' : 'Hide Answer'; });
            el.appendChild(q); el.appendChild(a); el.appendChild(btn);
            container.appendChild(el);
        }
        return container;
    }

    function parseQuizText(text) {
        const items = [];
        // Split by numbered questions
        const parts = text.split(/(?=^\s*\d+\))/m);
        for (const part of parts) {
            const p = part.trim();
            if (!p) continue;
            // Extract the leading '1)'
            const m = p.match(/^\s*(\d+)\)\s*(.*?)$/s);
            let body = p;
            if (m) body = p.replace(/^\s*\d+\)\s*/, '');
            // Try to split question and answer marker '| Answer:'
            const answerMatch = body.match(/\|\s*Answer:\s*([A-Da-d])/);
            let correct = answerMatch ? answerMatch[1].toUpperCase() : null;
            let questionText = body;
            if (answerMatch) questionText = body.slice(0, answerMatch.index).trim();
            // Parse options A) B) C) D)
            const optionMatches = [...questionText.matchAll(/([A-Da-d])\)\s*([^A-Da-d\)]+)/g)];
            const options = [];
            if (optionMatches.length >= 2) {
                for (const om of optionMatches) {
                    options.push({key: om[1].toUpperCase(), text: om[2].trim()});
                }
                // Remove options from questionText
                questionText = questionText.split(/A\)\s*/)[0].trim();
            } else {
                // Try split by 'A)'
                const qparts = questionText.split(/\sA\)\s/);
                if (qparts.length > 1) {
                    questionText = qparts[0].trim();
                    const optText = 'A) ' + qparts.slice(1).join('A) ');
                    const lines = optText.split(/\s(?=[A-Da-d]\) )/g);
                    for (const ln of lines) {
                        const mo = ln.match(/([A-Da-d])\)\s*(.*)/);
                        if (mo) options.push({key: mo[1].toUpperCase(), text: mo[2].trim()});
                    }
                }
            }
            items.push({question: questionText, options, correct});
        }
        return items;
    }

    function renderQuiz(items) {
        const container = document.createElement('div');
        container.className = 'quiz';
        items.forEach((it, idx) => {
            const qbox = document.createElement('div'); qbox.className = 'question';
            const qtitle = document.createElement('div'); qtitle.textContent = `${idx+1}) ${it.question}`;
            qbox.appendChild(qtitle);
            const opts = document.createElement('div'); opts.className = 'options';
            it.options.forEach(opt => {
                const label = document.createElement('label');
                const radio = document.createElement('input'); radio.type = 'radio'; radio.name = `quiz_${idx}`; radio.value = opt.key;
                label.appendChild(radio);
                label.appendChild(document.createTextNode(` ${opt.key}) ${opt.text}`));
                opts.appendChild(label);
            });
            qbox.appendChild(opts);
            const btn = document.createElement('button'); btn.className = 'check'; btn.textContent = 'Check';
            btn.addEventListener('click', () => {
                const selected = qbox.querySelector('input[type="radio"]:checked');
                if (!selected) return;
                const chosen = selected.value;
                if (it.correct && chosen === it.correct) {
                    qbox.classList.remove('incorrect'); qbox.classList.add('correct');
                } else {
                    qbox.classList.remove('correct'); qbox.classList.add('incorrect');
                }
                // reveal correct answer text
                if (it.correct) {
                    const correctOpt = it.options.find(o => o.key === it.correct);
                    const reveal = document.createElement('div'); reveal.style.marginTop='8px'; reveal.style.color='var(--text-secondary)'; reveal.textContent = `Answer: ${it.correct}) ${correctOpt ? correctOpt.text : ''}`;
                    // prevent duplicate reveals
                    if (!qbox.querySelector('.reveal-answer')) {
                        reveal.className = 'reveal-answer'; qbox.appendChild(reveal);
                    }
                }
            });
            qbox.appendChild(btn);
            container.appendChild(qbox);
        });
        return container;
    }

    async function fetchStats() {
        try {
            const res = await fetch(endpoint.replace('/query', '/stats'), { method: 'GET', headers: { 'Accept': 'application/json' } });
            if (!res.ok) return;
            const data = await res.json();
            if (promptCountEl && typeof data.prompt_count !== 'undefined') {
                promptCountEl.textContent = data.prompt_count;
            }
            if (tokenUsageEl && typeof data.token_usage_estimate !== 'undefined') {
                tokenUsageEl.textContent = data.token_usage_estimate;
            }
        } catch (e) {
            // silent fail for polling
        }
    }

    function buildSubmission(question) {
        return {
            question,
            payload: {
                question,
                audience: audienceSelect ? audienceSelect.value : "general",
                tone: toneSelect ? toneSelect.value : "professional",
                task: taskSelect ? taskSelect.value : "explain",
            },
        };
    }

    async function submitPrompt(submission = null, shouldAppendUserMessage = true) {
        const activeSubmission = submission || buildSubmission(questionInput.value.trim());
        const question = activeSubmission.question.trim();
        if (!question) {
            setError("Please enter a prompt before submitting.");
            return;
        }

        lastSubmission = activeSubmission;
        clearError();
        if (shouldAppendUserMessage) {
            appendMessage("user", question);
            questionInput.value = "";
        }
        setLoadingState(true);

        const loadingNode = appendMessage(
            "assistant",
            `Thinking... ${requestTimeoutSeconds}s remaining before timeout.`,
            "loading"
        );
        const abortController = new AbortController();
        let requestTimedOut = false;
        let secondsRemaining = requestTimeoutSeconds;

        const retryLastSubmission = () => {
            if (!lastSubmission) {
                return;
            }

            submitPrompt(lastSubmission, false);
        };

        const updateCountdown = () => {
            loadingNode.textContent = `Thinking... ${secondsRemaining}s remaining before timeout.`;
        };

        updateCountdown();

        const countdownTimer = window.setInterval(() => {
            secondsRemaining -= 1;

            if (secondsRemaining > 0) {
                updateCountdown();
            }
        }, 1000);

        const timeoutTimer = window.setTimeout(() => {
            requestTimedOut = true;
            abortController.abort();
        }, requestTimeoutSeconds * 1000);

        activeRequestTimers.push(countdownTimer, timeoutTimer);

        try {
            const response = await fetch(endpoint, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                body: JSON.stringify(activeSubmission.payload),
                signal: abortController.signal,
            });

            const data = await parseResponse(response);
            loadingNode.remove();
            clearActiveRequestTimers();

            if (!response.ok) {
                const errorMessage = data.error || "Request failed. Please try again.";
                setError(errorMessage, retryLastSubmission);
                appendMessage("assistant", `Error: ${errorMessage}`);
                return;
            }

            const answer = data.response || "No response generated.";
            appendMessage("assistant", answer);
            // update usage stats after successful response
            fetchStats();
        } catch (error) {
            clearActiveRequestTimers();
            loadingNode.remove();
            if (requestTimedOut || error.name === "AbortError") {
                const timeoutMessage = "Request timed out after 15 seconds. The backend may be unavailable or overloaded.";
                setError(timeoutMessage, retryLastSubmission);
                appendMessage("assistant", `Error: ${timeoutMessage}`);
                return;
            }

            const message = "Network error while contacting /chat/query.";
            setError(message, retryLastSubmission);
            appendMessage("assistant", `Error: ${message}`);
        } finally {
            clearActiveRequestTimers();
            setLoadingState(false);
            questionInput.focus();
        }
    }

    async function callFlashcards() {
        const question = questionInput.value.trim() || "Create study flashcards";
        clearError();
        appendMessage("user", `Generate flashcards: ${question}`);
        setLoadingState(true);
        try {
            const response = await fetch(endpoint.replace('/query', '/generate/flashcards'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
                body: JSON.stringify({ question, tone: toneSelect.value, audience: audienceSelect.value }),
            });
            const data = await parseResponse(response);
            if (!response.ok) {
                setError(data.error || 'Flashcard generation failed.');
                appendMessage('assistant', `Error: ${data.error || 'Flashcard generation failed.'}`);
            } else {
                const text = data.response || '';
                const cards = parseFlashcardsText(text);
                if (cards.length) {
                    const node = renderFlashcards(cards);
                    appendHTMLMessage('assistant', node);
                } else {
                    appendMessage('assistant', text || 'No flashcards generated.');
                }
                fetchStats();
            }
        } catch (e) {
            setError('Network error while generating flashcards.');
            appendMessage('assistant', 'Error: Network error while generating flashcards.');
        } finally {
            setLoadingState(false);
        }
    }

    async function callQuiz() {
        const question = questionInput.value.trim() || "Create a short quiz";
        const numQuestions = parseInt(document.getElementById('quizCount').value || '5', 10);
        clearError();
        appendMessage("user", `Generate quiz (${numQuestions} Qs): ${question}`);
        setLoadingState(true);
        try {
            const response = await fetch(endpoint.replace('/query', '/generate/quiz'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
                body: JSON.stringify({ question, num_questions: numQuestions }),
            });
            const data = await parseResponse(response);
            if (!response.ok) {
                setError(data.error || 'Quiz generation failed.');
                appendMessage('assistant', `Error: ${data.error || 'Quiz generation failed.'}`);
            } else {
                const text = data.response || '';
                const items = parseQuizText(text);
                if (items.length) {
                    const node = renderQuiz(items);
                    appendHTMLMessage('assistant', node);
                } else {
                    appendMessage('assistant', text || 'No quiz generated.');
                }
                fetchStats();
            }
        } catch (e) {
            setError('Network error while generating quiz.');
            appendMessage('assistant', 'Error: Network error while generating quiz.');
        } finally {
            setLoadingState(false);
        }
    }

    chatForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        await submitPrompt();
    });

    questionInput.addEventListener("keydown", async (event) => {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            await submitPrompt();
        }
    });

    questionInput.focus();

    const flashcardButton = document.getElementById('flashcardButton');
    const quizButton = document.getElementById('quizButton');
    if (flashcardButton) {
        flashcardButton.addEventListener('click', async (e) => {
            e.preventDefault();
            await callFlashcards();
        });
    }
    if (quizButton) {
        quizButton.addEventListener('click', async (e) => {
            e.preventDefault();
            await callQuiz();
        });
    }

    // Initial stats fetch and periodic polling for real-time updates
    fetchStats();
    setInterval(fetchStats, 5000);
});

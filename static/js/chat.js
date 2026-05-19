document.addEventListener("DOMContentLoaded", () => {
    const endpoint = document.body.dataset.chatEndpoint || "/chat/query";
    const requestTimeoutSeconds = 15;
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
});

(function () {
    "use strict";

    var POLL_MS = 1000;
    var PLAYER_KEY = "fw_player_id";
    var MAX_GUESSES = 6;
    var KEYBOARD_ROWS = [
        ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p"],
        ["a", "s", "d", "f", "g", "h", "j", "k", "l"],
        ["Enter", "z", "x", "c", "v", "b", "n", "m", "Backspace"],
    ];

    var pollTimer = null;
    var hasJoined = false;
    var lastState = null;
    var validGuesses = null;
    var gridBuilt = false;
    var keyboardBuilt = false;
    var currentGuess = "";
    var isSubmitting = false;
    var isSavingName = false;
    var isClaiming = false;
    var isConfirming = false;
    var nameDirty = false;
    var pendingName = null;
    var secretDirty = false;
    var secretShowVisible = false;
    var setterWatchShowVisible = false;

    var statusEl = document.getElementById("fwStatusMessage");
    var shareLinkInput = document.getElementById("fwShareLink");
    var shareRow = document.getElementById("fwShareRow");
    var copyBtn = document.getElementById("fwCopyBtn");
    var spectatorBadge = document.getElementById("fwSpectatorBadge");
    var nameRow = document.getElementById("fwNameRow");
    var nameInput = document.getElementById("fwNameInput");
    var nameSaveBtn = document.getElementById("fwNameSaveBtn");
    var roleBadge = document.getElementById("fwRoleBadge");
    var rolePanel = document.getElementById("fwRolePanel");
    var claimSetterBtn = document.getElementById("fwClaimSetterBtn");
    var secretPanel = document.getElementById("fwSecretPanel");
    var secretInput = document.getElementById("fwSecretInput");
    var secretShowBtn = document.getElementById("fwSecretShowBtn");
    var confirmBtn = document.getElementById("fwConfirmBtn");
    var setterWatchPanel = document.getElementById("fwSetterWatchPanel");
    var setterWordValue = document.getElementById("fwSetterWordValue");
    var setterWordShowBtn = document.getElementById("fwSetterWordShowBtn");
    var waitingPanel = document.getElementById("fwWaitingPanel");
    var waitingMessage = document.getElementById("fwWaitingMessage");
    var gamePanel = document.getElementById("fwGamePanel");
    var gridEl = document.getElementById("fwGrid");
    var keyboardEl = document.getElementById("fwKeyboard");
    var toastEl = document.getElementById("fwToast");
    var rematchBtn = document.getElementById("fwRematchBtn");

    shareLinkInput.value = window.location.href;

    function getPlayerId() {
        var id = null;
        try {
            id = localStorage.getItem(PLAYER_KEY);
        } catch (err) {
            /* ignore */
        }
        if (!id || !/^[a-f0-9]{32}$/.test(id)) {
            id = Array.from(crypto.getRandomValues(new Uint8Array(16)))
                .map(function (b) {
                    return b.toString(16).padStart(2, "0");
                })
                .join("");
            try {
                localStorage.setItem(PLAYER_KEY, id);
            } catch (err) {
                /* ignore */
            }
        }
        return id;
    }

    function apiUrl(path) {
        return "/friend-wordle-online/room/" + encodeURIComponent(FW_ROOM_CODE) + path;
    }

    function apiRequest(method, path, body) {
        var headers = {
            Accept: "application/json",
            "X-FW-Player-Id": getPlayerId(),
        };
        var options = { method: method, headers: headers, credentials: "same-origin" };
        if (method !== "GET") {
            headers["X-CSRFToken"] = FW_CSRF_TOKEN;
        }
        if (body !== undefined) {
            headers["Content-Type"] = "application/json";
            options.body = JSON.stringify(body);
        }
        return fetch(apiUrl(path), options).then(function (response) {
            return response
                .json()
                .catch(function () { return {}; })
                .then(function (data) {
                    if (!response.ok) {
                        throw new Error(data.error || "Something went wrong.");
                    }
                    return data;
                });
        });
    }

    function seatName(state, seat) {
        if (state.names && state.names[seat]) {
            return state.names[seat];
        }
        return "Player " + seat;
    }

    function setterSeat(state) {
        if (state.roles.X === "setter") {
            return "X";
        }
        if (state.roles.O === "setter") {
            return "O";
        }
        return null;
    }

    function guesserSeat(state) {
        if (state.roles.X === "guesser") {
            return "X";
        }
        if (state.roles.O === "guesser") {
            return "O";
        }
        return null;
    }

    function showToast(message) {
        if (!message) {
            toastEl.hidden = true;
            toastEl.textContent = "";
            return;
        }
        toastEl.textContent = message;
        toastEl.hidden = false;
    }

    function isSpectator(state) {
        return !state.your_seat;
    }

    function spectatorStatusText(state) {
        if (state.status === "waiting") {
            return "Waiting for players to join\u2026";
        }
        if (state.status === "choosing_roles") {
            return "Players are deciding who picks the word\u2026";
        }
        if (state.status === "setting_word") {
            return seatName(state, setterSeat(state)) + " is choosing a secret word\u2026";
        }
        if (state.status === "guessing") {
            return seatName(state, guesserSeat(state)) + " is guessing\u2026";
        }
        if (state.status === "won") {
            return (
                seatName(state, guesserSeat(state)) +
                " guessed it in " +
                state.guesses.length +
                "!"
            );
        }
        if (state.status === "lost") {
            var word = (state.secret || "?????").toUpperCase();
            return "Out of guesses. The word was " + word + ".";
        }
        return "";
    }

    function statusText(state) {
        if (isSpectator(state)) {
            return spectatorStatusText(state);
        }
        if (state.status === "waiting") {
            return "Waiting for a friend to join\u2026 share the link above.";
        }
        if (state.status === "choosing_roles") {
            return "Want to pick the word? Tap the button below. Otherwise you\u2019ll guess.";
        }
        if (state.status === "setting_word") {
            if (state.your_role === "setter") {
                return "Enter your secret word, then confirm to start.";
            }
            return seatName(state, setterSeat(state)) + " is choosing a secret word\u2026";
        }
        if (state.status === "guessing") {
            if (state.your_role === "guesser") {
                return "Your turn \u2014 guess the secret word!";
            }
            if (state.your_role === "setter") {
                return "Watch " + seatName(state, guesserSeat(state)) + "\u2019s guesses below.";
            }
        }
        if (state.status === "won") {
            if (state.your_role === "guesser") {
                return "You got it in " + state.guesses.length + "!";
            }
            if (state.your_role === "setter") {
                return seatName(state, guesserSeat(state)) + " guessed your word!";
            }
        }
        if (state.status === "lost") {
            var revealed = (state.secret || "?????").toUpperCase();
            if (state.your_role === "guesser") {
                return "Out of guesses. The word was " + revealed + ".";
            }
            if (state.your_role === "setter") {
                return (
                    seatName(state, guesserSeat(state)) +
                    " ran out of guesses. The word was " +
                    revealed +
                    "."
                );
            }
        }
        return "";
    }

    function roleBadgeText(state) {
        if (isSpectator(state) || state.status === "choosing_roles" || state.status === "waiting") {
            return null;
        }
        if (state.your_role === "setter") {
            return "You\u2019re the setter";
        }
        if (state.your_role === "guesser") {
            return "You\u2019re the guesser";
        }
        return null;
    }

    function shouldShowGamePanel(state) {
        return (
            state.status === "guessing" ||
            state.status === "won" ||
            state.status === "lost"
        );
    }

    function shouldShowWaitingPanel(state) {
        if (state.status !== "setting_word") {
            return false;
        }
        return isSpectator(state) || state.your_role === "guesser";
    }

    function shouldShowKeyboard(state) {
        return state.status === "guessing" && state.your_role === "guesser";
    }

    function buildGridOnce() {
        if (gridBuilt) {
            return;
        }
        gridEl.innerHTML = "";
        for (var row = 0; row < MAX_GUESSES; row++) {
            var rowEl = document.createElement("div");
            rowEl.className = "fw-row";
            rowEl.dataset.row = String(row);
            for (var col = 0; col < 5; col++) {
                var cell = document.createElement("div");
                cell.className = "fw-cell";
                cell.dataset.col = String(col);
                rowEl.appendChild(cell);
            }
            gridEl.appendChild(rowEl);
        }
        gridBuilt = true;
    }

    function buildKeyboardOnce() {
        if (keyboardBuilt) {
            return;
        }
        keyboardEl.innerHTML = "";
        KEYBOARD_ROWS.forEach(function (row) {
            var rowEl = document.createElement("div");
            rowEl.className = "fw-keyboard-row";
            row.forEach(function (key) {
                var btn = document.createElement("button");
                btn.type = "button";
                btn.className = "fw-key";
                btn.dataset.key = key;
                if (key === "Enter" || key === "Backspace") {
                    btn.classList.add("fw-key-wide");
                }
                btn.textContent =
                    key === "Enter" ? "Enter" : key === "Backspace" ? "\u232B" : key.toUpperCase();
                btn.addEventListener("click", function () {
                    handleKeyPress(key);
                });
                rowEl.appendChild(btn);
            });
            keyboardEl.appendChild(rowEl);
        });
        keyboardBuilt = true;
    }

    function canTypeGuess(state) {
        return (
            state &&
            state.status === "guessing" &&
            state.your_role === "guesser" &&
            state.guesses.length < MAX_GUESSES
        );
    }

    function isTypingInFormField() {
        var active = document.activeElement;
        if (!active) {
            return false;
        }
        var tag = active.tagName;
        if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") {
            return true;
        }
        return active.isContentEditable;
    }

    function shouldCaptureGameKeys() {
        if (!canTypeGuess(lastState) || isSubmitting) {
            return false;
        }
        if (gamePanel.hidden) {
            return false;
        }
        if (isTypingInFormField()) {
            return false;
        }
        return true;
    }

    function renderGrid(state) {
        buildGridOnce();
        var guesses = state.guesses || [];
        var rows = gridEl.querySelectorAll(".fw-row");

        rows.forEach(function (rowEl, rowIdx) {
            var cells = rowEl.querySelectorAll(".fw-cell");
            cells.forEach(function (cell) {
                cell.textContent = "";
                cell.classList.remove("fw-correct", "fw-present", "fw-absent", "fw-shake");
            });

            if (rowIdx < guesses.length) {
                var entry = guesses[rowIdx];
                var word = entry.word || "";
                var feedback = entry.feedback || [];
                for (var i = 0; i < 5; i++) {
                    cells[i].textContent = (word[i] || "").toUpperCase();
                    if (feedback[i]) {
                        cells[i].classList.add("fw-" + feedback[i]);
                    }
                }
            } else if (rowIdx === guesses.length && canTypeGuess(state)) {
                for (var j = 0; j < currentGuess.length; j++) {
                    cells[j].textContent = currentGuess[j].toUpperCase();
                }
            }
        });
    }

    function updateKeyboardFeedback(state) {
        var letterStatus = {};
        var order = { correct: 3, present: 2, absent: 1 };
        (state.guesses || []).forEach(function (entry) {
            var word = entry.word || "";
            var feedback = entry.feedback || [];
            for (var i = 0; i < 5; i++) {
                var letter = word[i];
                var status = feedback[i];
                if (!letter || !status) {
                    continue;
                }
                if (!letterStatus[letter] || order[status] > order[letterStatus[letter]]) {
                    letterStatus[letter] = status;
                }
            }
        });

        keyboardEl.querySelectorAll(".fw-key[data-key]").forEach(function (btn) {
            var key = btn.dataset.key;
            if (key === "Enter" || key === "Backspace") {
                return;
            }
            btn.classList.remove("fw-correct", "fw-present", "fw-absent");
            if (letterStatus[key]) {
                btn.classList.add("fw-" + letterStatus[key]);
            }
        });
    }

    function handleKeyPress(key) {
        if (!shouldCaptureGameKeys()) {
            return;
        }
        showToast("");

        if (key === "Enter") {
            submitGuess();
            return;
        }
        if (key === "Backspace") {
            currentGuess = currentGuess.slice(0, -1);
            renderGrid(lastState);
            return;
        }
        if (currentGuess.length < 5 && /^[a-z]$/.test(key)) {
            currentGuess += key;
            renderGrid(lastState);
        }
    }

    function shakeCurrentRow() {
        var rowIdx = lastState ? lastState.guesses.length : 0;
        var rowEl = gridEl.querySelector('.fw-row[data-row="' + rowIdx + '"]');
        if (rowEl) {
            rowEl.querySelectorAll(".fw-cell").forEach(function (cell) {
                cell.classList.add("fw-shake");
            });
        }
    }

    function submitGuess() {
        if (!canTypeGuess(lastState) || isSubmitting) {
            return;
        }
        if (currentGuess.length !== 5) {
            return;
        }
        if (validGuesses && !validGuesses.has(currentGuess)) {
            showToast("Not in word list");
            shakeCurrentRow();
            return;
        }

        isSubmitting = true;
        var word = currentGuess;
        apiRequest("POST", "/guess", { word: word })
            .then(function (state) {
                currentGuess = "";
                render(state);
            })
            .catch(function (err) {
                if (err.message === "Not in word list.") {
                    showToast("Not in word list");
                    shakeCurrentRow();
                } else {
                    showToast(err.message);
                }
            })
            .then(function () {
                isSubmitting = false;
            });
    }

    function render(state) {
        lastState = state;
        statusEl.textContent = statusText(state);

        var isPlayer = !!state.your_seat;
        var isFinished = state.status === "won" || state.status === "lost";

        spectatorBadge.hidden = isPlayer;
        shareRow.hidden = !isPlayer;
        nameRow.hidden = !isPlayer;
        rematchBtn.hidden = !(isPlayer && isFinished);

        var badge = roleBadgeText(state);
        if (badge) {
            roleBadge.textContent = badge;
            roleBadge.hidden = false;
        } else {
            roleBadge.hidden = true;
        }

        if (isPlayer && !nameDirty && document.activeElement !== nameInput) {
            nameInput.value = state.your_name || "";
        }

        rolePanel.hidden = !(isPlayer && state.status === "choosing_roles");
        claimSetterBtn.disabled = isClaiming;

        var showSecretPanel =
            isPlayer && state.status === "setting_word" && state.your_role === "setter";
        secretPanel.hidden = !showSecretPanel;

        if (showSecretPanel) {
            if (!secretDirty && document.activeElement !== secretInput && state.secret) {
                secretInput.value = state.secret;
            }
            confirmBtn.disabled = isConfirming || secretInput.value.trim().length !== 5;
        }

        var showSetterWatch =
            isPlayer &&
            state.your_role === "setter" &&
            (state.status === "guessing" || isFinished);
        setterWatchPanel.hidden = !showSetterWatch;
        if (showSetterWatch && state.secret) {
            if (setterWatchShowVisible) {
                setterWordValue.textContent = state.secret.toUpperCase();
            } else {
                setterWordValue.textContent = "\u2022\u2022\u2022\u2022\u2022";
            }
            setterWordShowBtn.textContent = setterWatchShowVisible ? "Hide" : "Show";
        }

        var showWaiting = shouldShowWaitingPanel(state);
        waitingPanel.hidden = !showWaiting;
        if (showWaiting) {
            waitingMessage.textContent =
                seatName(state, setterSeat(state)) + " is picking a secret word\u2026";
        }

        var showGame = shouldShowGamePanel(state);
        gamePanel.hidden = !showGame;

        if (showGame) {
            buildGridOnce();
            renderGrid(state);

            var showKeyboard = shouldShowKeyboard(state);
            keyboardEl.hidden = !showKeyboard;
            if (showKeyboard) {
                buildKeyboardOnce();
                updateKeyboardFeedback(state);
                keyboardEl.querySelectorAll(".fw-key").forEach(function (btn) {
                    btn.disabled = false;
                });
                gamePanel.classList.remove("fw-readonly");
            } else {
                gamePanel.classList.add("fw-readonly");
            }
        } else {
            keyboardEl.hidden = true;
            currentGuess = "";
        }

        if (!shouldShowKeyboard(state)) {
            currentGuess = "";
            showToast("");
        }

        if (state.status === "choosing_roles" || state.status === "waiting") {
            currentGuess = "";
        }
        if (isFinished) {
            currentGuess = "";
        }
    }

    function loadGuesses() {
        return fetch("/friend-wordle-online/api/guesses")
            .then(function (response) {
                return response.json();
            })
            .then(function (words) {
                validGuesses = new Set(words);
            })
            .catch(function () {
                validGuesses = null;
            });
    }

    function poll() {
        apiRequest("GET", "/state").then(render).catch(function () {
            statusEl.textContent = "Connection issue \u2014 retrying\u2026";
        });
    }

    function flushPending(state) {
        var chain = Promise.resolve(state);
        if (pendingName !== null) {
            var name = pendingName;
            pendingName = null;
            chain = chain.then(function () {
                return apiRequest("POST", "/name", { name: name });
            });
        }
        return chain.then(render);
    }

    function joinThenStart() {
        Promise.all([loadGuesses(), apiRequest("POST", "/join")])
            .then(function (results) {
                hasJoined = true;
                return flushPending(results[1]);
            })
            .then(function () {
                startPolling();
            })
            .catch(function (err) {
                statusEl.textContent = err.message || "Could not join this room.";
            });
    }

    function saveName() {
        if (isSavingName) {
            return;
        }
        nameDirty = true;
        if (!hasJoined) {
            pendingName = nameInput.value;
            return;
        }
        isSavingName = true;
        nameSaveBtn.disabled = true;
        apiRequest("POST", "/name", { name: nameInput.value })
            .then(function (state) {
                nameDirty = false;
                render(state);
            })
            .catch(function (err) {
                showToast(err.message);
            })
            .then(function () {
                isSavingName = false;
                nameSaveBtn.disabled = false;
            });
    }

    claimSetterBtn.addEventListener("click", function () {
        if (isClaiming) {
            return;
        }
        isClaiming = true;
        apiRequest("POST", "/claim-setter")
            .then(render)
            .catch(function (err) {
                showToast(err.message);
            })
            .then(function () {
                isClaiming = false;
            });
    });

    secretInput.addEventListener("input", function () {
        secretDirty = true;
        secretInput.value = secretInput.value.replace(/[^a-zA-Z]/g, "").slice(0, 5);
        confirmBtn.disabled = secretInput.value.length !== 5 || isConfirming;
    });

    secretShowBtn.addEventListener("click", function () {
        secretShowVisible = !secretShowVisible;
        secretInput.classList.toggle("fw-secret-masked", !secretShowVisible);
        secretShowBtn.textContent = secretShowVisible ? "Hide" : "Show";
    });

    setterWordShowBtn.addEventListener("click", function () {
        setterWatchShowVisible = !setterWatchShowVisible;
        if (lastState) {
            render(lastState);
        }
    });

    confirmBtn.addEventListener("click", function () {
        if (isConfirming) {
            return;
        }
        var word = secretInput.value.trim();
        if (word.length !== 5) {
            showToast("Enter exactly 5 letters.");
            return;
        }
        isConfirming = true;
        confirmBtn.disabled = true;
        apiRequest("POST", "/secret", { word: word })
            .then(function () {
                return apiRequest("POST", "/confirm");
            })
            .then(function (state) {
                secretDirty = false;
                render(state);
            })
            .catch(function (err) {
                showToast(err.message);
            })
            .then(function () {
                isConfirming = false;
                confirmBtn.disabled = secretInput.value.trim().length !== 5;
            });
    });

    copyBtn.addEventListener("click", function () {
        var restoreLabel = copyBtn.textContent;
        function showCopied() {
            copyBtn.textContent = "Copied!";
            setTimeout(function () {
                copyBtn.textContent = restoreLabel;
            }, 1500);
        }
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(shareLinkInput.value).then(showCopied);
        } else {
            shareLinkInput.select();
        }
    });

    nameSaveBtn.addEventListener("click", saveName);
    nameInput.addEventListener("keydown", function (event) {
        if (event.key === "Enter") {
            event.preventDefault();
            saveName();
        }
    });

    document.addEventListener("keydown", function (event) {
        if (!shouldCaptureGameKeys()) {
            return;
        }
        if (event.ctrlKey || event.metaKey || event.altKey) {
            return;
        }
        if (event.key === "Enter") {
            event.preventDefault();
            submitGuess();
            return;
        }
        if (event.key === "Backspace") {
            event.preventDefault();
            handleKeyPress("Backspace");
            return;
        }
        if (/^[a-zA-Z]$/.test(event.key)) {
            event.preventDefault();
            handleKeyPress(event.key.toLowerCase());
        }
    });

    rematchBtn.addEventListener("click", function () {
        rematchBtn.disabled = true;
        currentGuess = "";
        secretDirty = false;
        secretShowVisible = false;
        setterWatchShowVisible = false;
        secretInput.value = "";
        secretInput.classList.add("fw-secret-masked");
        secretShowBtn.textContent = "Show";
        apiRequest("POST", "/rematch")
            .then(render)
            .catch(function (err) {
                showToast(err.message);
            })
            .then(function () {
                rematchBtn.disabled = false;
            });
    });

    function startPolling() {
        if (pollTimer) {
            return;
        }
        poll();
        pollTimer = setInterval(poll, POLL_MS);
    }

    function stopPolling() {
        if (pollTimer) {
            clearInterval(pollTimer);
            pollTimer = null;
        }
    }

    document.addEventListener("visibilitychange", function () {
        if (document.hidden) {
            stopPolling();
        } else {
            startPolling();
        }
    });

    joinThenStart();
})();

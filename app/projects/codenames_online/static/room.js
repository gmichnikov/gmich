(function () {
    "use strict";

    var POLL_MS = 1000;
    var PLAYER_KEY = "cno_player_id";
    var GRID_SIZE = 25;

    var pollTimer = null;
    var lastState = null;
    var hasJoined = false;
    var isJoining = false;
    var isBusy = false;
    var setupDirty = false;
    var toastTimer = null;

    var statusEl = document.getElementById("cnoStatusMessage");
    var toastEl = document.getElementById("cnoToast");
    var shareRow = document.getElementById("cnoShareRow");
    var copyBtn = document.getElementById("cnoCopyBtn");
    var shareBtn = document.getElementById("cnoShareBtn");
    var roleBadge = document.getElementById("cnoRoleBadge");
    var joinPanel = document.getElementById("cnoJoinPanel");
    var joinBtn = document.getElementById("cnoJoinBtn");
    var lobbyPanel = document.getElementById("cnoLobbyPanel");
    var claimClueBtn = document.getElementById("cnoClaimClueBtn");
    var swapRolesBtn = document.getElementById("cnoSwapRolesBtn");
    var setupPanel = document.getElementById("cnoSetupPanel");
    var wordListSelect = document.getElementById("cnoWordListSelect");
    var nameRedInput = document.getElementById("cnoNameRed");
    var nameBlueInput = document.getElementById("cnoNameBlue");
    var excludeConfusingInput = document.getElementById("cnoExcludeConfusing");
    var previewBtn = document.getElementById("cnoPreviewBtn");
    var startBtn = document.getElementById("cnoStartBtn");
    var redealBtn = document.getElementById("cnoRedealBtn");
    var gridWrap = document.getElementById("cnoGridWrap");
    var gridEl = document.getElementById("cnoGrid");
    var playBar = document.getElementById("cnoPlayBar");
    var turnBanner = document.getElementById("cnoTurnBanner");
    var doneBtn = document.getElementById("cnoDoneBtn");
    var rematchBtn = document.getElementById("cnoRematchBtn");
    var wrapperEl = document.getElementById("cnoWrapper");
    var shareLinkInput = document.getElementById("cnoShareLink");

    shareLinkInput.value = window.location.href;
    if (navigator.share) {
        shareBtn.hidden = false;
    }

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
            } catch (err2) {
                /* ignore */
            }
        }
        return id;
    }

    function apiUrl(path) {
        return "/codenames-online/room/" + encodeURIComponent(CNO_ROOM_CODE) + path;
    }

    function apiRequest(method, path, body) {
        var headers = {
            Accept: "application/json",
            "X-CNO-Player-Id": getPlayerId(),
        };
        var options = { method: method, headers: headers, credentials: "same-origin" };
        if (method !== "GET") {
            headers["X-CSRFToken"] = CNO_CSRF_TOKEN;
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

    function showToast(message) {
        toastEl.textContent = message;
        toastEl.hidden = false;
        if (toastTimer) {
            clearTimeout(toastTimer);
        }
        toastTimer = setTimeout(function () {
            toastEl.hidden = true;
        }, 2500);
    }

    function bothSeatsFull(state) {
        return !!(state.seats && state.seats.X && state.seats.O);
    }

    function canTakeSeat(state) {
        return !state.your_seat && !bothSeatsFull(state);
    }

    function isClueGiver(state) {
        return state.your_phone_role === "clue_giver";
    }

    function isGuesser(state) {
        return state.your_phone_role === "guesser";
    }

    function rolesAssigned(state) {
        return !!(
            state.phone_roles &&
            state.phone_roles.X &&
            state.phone_roles.O
        );
    }

    function inPlayPhase(state) {
        return (
            state.status === "preview" ||
            state.status === "active" ||
            state.status === "won"
        );
    }

    function turnLabel(state) {
        if (!state.turn) {
            return "";
        }
        var name = state.turn_spymaster || state.turn;
        var color = state.turn === "red" ? "Red" : "Blue";
        return name + "'s turn (" + color + ")";
    }

    function populateWordLists(state) {
        if (!state.word_lists || !wordListSelect.options.length) {
            wordListSelect.innerHTML = "";
            (state.word_lists || []).forEach(function (entry) {
                var opt = document.createElement("option");
                opt.value = entry.id;
                opt.textContent = entry.name + " (" + entry.word_count + ")";
                wordListSelect.appendChild(opt);
            });
        }
        if (state.word_list_id) {
            wordListSelect.value = state.word_list_id;
        }
    }

    function syncSetupFields(state) {
        populateWordLists(state);
        if (!setupDirty) {
            if (state.name_red) {
                nameRedInput.value = state.name_red;
            }
            if (state.name_blue) {
                nameBlueInput.value = state.name_blue;
            }
            excludeConfusingInput.checked = state.exclude_confusing !== false;
        }
    }

    function saveSetup() {
        return apiRequest("POST", "/setup", {
            word_list_id: wordListSelect.value,
            name_red: nameRedInput.value.trim(),
            name_blue: nameBlueInput.value.trim(),
            exclude_confusing: excludeConfusingInput.checked,
        });
    }

    function tileClass(state, index) {
        var classes = ["cno-tile"];
        var revealed = state.revealed && state.revealed[index];
        if (revealed) {
            classes.push("cno-tile-revealed");
        }
        if (isClueGiver(state) && state.key) {
            classes.push("cno-tile-" + state.key[index]);
        } else if (state.tile_colors && state.tile_colors[index]) {
            classes.push("cno-tile-" + state.tile_colors[index]);
        } else {
            classes.push("cno-tile-hidden");
        }
        return classes.join(" ");
    }

    function renderGrid(state) {
        if (!state.words) {
            gridEl.innerHTML = "";
            return;
        }
        gridEl.innerHTML = "";
        state.words.forEach(function (word, index) {
            var tile = document.createElement("button");
            tile.type = "button";
            tile.className = tileClass(state, index);
            tile.textContent = word;
            tile.dataset.index = String(index);

            var revealed = state.revealed && state.revealed[index];
            if (isGuesser(state) && state.status === "active" && !revealed) {
                tile.addEventListener("click", function () {
                    if (isBusy) {
                        return;
                    }
                    isBusy = true;
                    apiRequest("POST", "/guess", { index: index })
                        .then(renderState)
                        .catch(function (err) {
                            showToast(err.message);
                        })
                        .finally(function () {
                            isBusy = false;
                        });
                });
            }

            if (state.can_boot && !revealed) {
                var boot = document.createElement("span");
                boot.className = "cno-boot-btn";
                boot.textContent = "Boot";
                boot.addEventListener("click", function (event) {
                    event.stopPropagation();
                    if (isBusy) {
                        return;
                    }
                    isBusy = true;
                    apiRequest("POST", "/boot_word", { index: index })
                        .then(renderState)
                        .catch(function (err) {
                            showToast(err.message);
                        })
                        .finally(function () {
                            isBusy = false;
                        });
                });
                tile.appendChild(boot);
            }

            gridEl.appendChild(tile);
        });
    }

    function setPlayBarButtons(state) {
        startBtn.hidden = true;
        redealBtn.hidden = true;
        doneBtn.hidden = true;
        rematchBtn.hidden = true;

        if (state.status === "preview" && isClueGiver(state)) {
            startBtn.hidden = false;
            redealBtn.hidden = false;
            return;
        }
        if (state.status === "active" && isGuesser(state)) {
            doneBtn.hidden = false;
            return;
        }
        if (state.status === "won" && isClueGiver(state)) {
            rematchBtn.hidden = false;
        }
    }

    function setPlayBar(state) {
        var showBar =
            state.status === "preview" ||
            state.status === "active" ||
            state.status === "won";
        playBar.hidden = !showBar;

        if (!showBar) {
            return;
        }

        setPlayBarButtons(state);

        wrapperEl.classList.remove("cno-turn-red", "cno-turn-blue");
        if (state.status === "active" && state.turn) {
            wrapperEl.classList.add(state.turn === "red" ? "cno-turn-red" : "cno-turn-blue");
        }

        if (state.status === "won") {
            var winnerName = state.winner_spymaster || state.winner;
            var winnerColor = state.winner === "red" ? "Red" : "Blue";
            turnBanner.textContent = winnerName + " wins (" + winnerColor + ")!";
            return;
        }

        if (state.status === "preview") {
            turnBanner.textContent = "Preview — check the board before starting";
            if (isClueGiver(state) && state.remaining) {
                turnBanner.textContent +=
                    " · " + state.remaining.red + " Red · " + state.remaining.blue + " Blue left";
            }
            return;
        }

        turnBanner.textContent = turnLabel(state);
        if (isClueGiver(state) && state.remaining) {
            turnBanner.textContent +=
                " · " + state.remaining.red + " Red · " + state.remaining.blue + " Blue left";
        }
    }

    function statusMessage(state) {
        if (!state.your_seat && canTakeSeat(state)) {
            return "Tap Join to connect this device to the room.";
        }
        if (!bothSeatsFull(state)) {
            return "Waiting for the second device… Share the link above.";
        }
        if (state.status === "waiting_roles") {
            return "Both phones connected — choose which is the clue-giver phone.";
        }
        if (state.status === "waiting_start") {
            if (isClueGiver(state)) {
                return "Enter spymaster names and deal a preview board.";
            }
            if (isGuesser(state)) {
                return "Waiting for the clue-giver phone to set up…";
            }
        }
        if (state.status === "preview") {
            if (isGuesser(state)) {
                return "Waiting to start…";
            }
            return "Review the board. Boot confusing words, then start the game.";
        }
        if (state.status === "active") {
            if (isGuesser(state)) {
                return "Tap words to guess. Tap Done when your team is finished.";
            }
            return "Give clues out loud. The guessers tap on their phone.";
        }
        return "";
    }

    function renderState(state) {
        lastState = state;

        var compact = inPlayPhase(state);
        wrapperEl.classList.toggle("cno-compact-play", compact);
        wrapperEl.classList.toggle("cno-status-active", state.status === "active");
        wrapperEl.classList.toggle("cno-status-won", state.status === "won");

        roleBadge.hidden = !state.your_phone_role || compact;
        if (state.your_phone_role === "clue_giver") {
            roleBadge.textContent = "Clue-giver phone";
        } else if (state.your_phone_role === "guesser") {
            roleBadge.textContent = "Guesser phone";
        }

        var showShare = !rolesAssigned(state) && !compact;
        shareRow.hidden = !showShare;

        joinPanel.hidden = !canTakeSeat(state);
        joinBtn.disabled = isJoining;

        var showClaimLobby =
            state.status === "waiting_roles" &&
            bothSeatsFull(state) &&
            !rolesAssigned(state);
        lobbyPanel.hidden = !showClaimLobby;
        claimClueBtn.hidden = !showClaimLobby || !state.your_seat;

        swapRolesBtn.hidden = !(
            isClueGiver(state) &&
            (state.status === "waiting_start" || state.status === "preview")
        );
        if (!swapRolesBtn.hidden) {
            lobbyPanel.hidden = false;
            lobbyPanel.classList.add("cno-lobby-swap-only");
        } else {
            lobbyPanel.classList.remove("cno-lobby-swap-only");
        }

        var showSetup =
            isClueGiver(state) &&
            (state.status === "waiting_start" || state.status === "won");
        setupPanel.hidden = !showSetup;
        if (showSetup) {
            syncSetupFields(state);
        }

        var showGrid =
            state.words &&
            (state.status === "preview" ||
                state.status === "active" ||
                state.status === "won") &&
            (isClueGiver(state) || state.status !== "preview");
        gridWrap.hidden = !showGrid;
        if (showGrid) {
            renderGrid(state);
        }

        var hideStatus =
            state.status === "active" ||
            (state.status === "preview" && isClueGiver(state)) ||
            state.status === "won";
        statusEl.hidden = hideStatus;
        if (!hideStatus) {
            statusEl.textContent = statusMessage(state);
        }

        setPlayBar(state);
    }

    function poll() {
        apiRequest("GET", "/state")
            .then(function (state) {
                if (state.your_seat) {
                    hasJoined = true;
                }
                renderState(state);
            })
            .catch(function (err) {
                statusEl.textContent = err.message;
            });
    }

    function startPolling() {
        poll();
        pollTimer = setInterval(poll, POLL_MS);
    }

    function stopPolling() {
        if (pollTimer) {
            clearInterval(pollTimer);
            pollTimer = null;
        }
    }

    joinBtn.addEventListener("click", function () {
        isJoining = true;
        apiRequest("POST", "/join")
            .then(function (state) {
                hasJoined = true;
                renderState(state);
            })
            .catch(function (err) {
                showToast(err.message);
            })
            .finally(function () {
                isJoining = false;
            });
    });

    claimClueBtn.addEventListener("click", function () {
        isBusy = true;
        apiRequest("POST", "/claim_role", { role: "clue_giver" })
            .then(renderState)
            .catch(function (err) {
                showToast(err.message);
            })
            .finally(function () {
                isBusy = false;
            });
    });

    swapRolesBtn.addEventListener("click", function () {
        isBusy = true;
        apiRequest("POST", "/claim_role", { swap: true })
            .then(renderState)
            .catch(function (err) {
                showToast(err.message);
            })
            .finally(function () {
                isBusy = false;
            });
    });

    [nameRedInput, nameBlueInput, wordListSelect, excludeConfusingInput].forEach(function (el) {
        el.addEventListener("input", function () {
            setupDirty = true;
        });
        el.addEventListener("change", function () {
            setupDirty = true;
        });
    });

    previewBtn.addEventListener("click", function () {
        isBusy = true;
        saveSetup()
            .then(function () {
                setupDirty = false;
                return apiRequest("POST", "/preview");
            })
            .then(renderState)
            .catch(function (err) {
                showToast(err.message);
            })
            .finally(function () {
                isBusy = false;
            });
    });

    startBtn.addEventListener("click", function () {
        isBusy = true;
        apiRequest("POST", "/start")
            .then(renderState)
            .catch(function (err) {
                showToast(err.message);
            })
            .finally(function () {
                isBusy = false;
            });
    });

    redealBtn.addEventListener("click", function () {
        isBusy = true;
        apiRequest("POST", "/preview")
            .then(renderState)
            .catch(function (err) {
                showToast(err.message);
            })
            .finally(function () {
                isBusy = false;
            });
    });

    doneBtn.addEventListener("click", function () {
        isBusy = true;
        apiRequest("POST", "/end_turn")
            .then(renderState)
            .catch(function (err) {
                showToast(err.message);
            })
            .finally(function () {
                isBusy = false;
            });
    });

    rematchBtn.addEventListener("click", function () {
        isBusy = true;
        apiRequest("POST", "/rematch")
            .then(function (state) {
                setupDirty = false;
                renderState(state);
            })
            .catch(function (err) {
                showToast(err.message);
            })
            .finally(function () {
                isBusy = false;
            });
    });

    copyBtn.addEventListener("click", function () {
        shareLinkInput.select();
        navigator.clipboard.writeText(shareLinkInput.value).then(function () {
            showToast("Link copied!");
        });
    });

    shareBtn.addEventListener("click", function () {
        navigator.share({ title: "Codenames", url: shareLinkInput.value }).catch(function () {
            /* ignore cancel */
        });
    });

    document.addEventListener("visibilitychange", function () {
        if (document.hidden) {
            stopPolling();
        } else {
            startPolling();
        }
    });

    startPolling();
})();

(function () {
    "use strict";

    var POLL_MS = 1000;
    var PLAYER_KEY = "mo_player_id";

    var pollTimer = null;
    var isMoving = false;
    var isSavingName = false;
    var isJoining = false;
    var nameDirty = false;
    var pendingName = null;
    var lastState = null;
    var lastVersion = null;

    var statusEl = document.getElementById("moStatusMessage");
    var shareLinkInput = document.getElementById("moShareLink");
    var shareRow = document.getElementById("moShareRow");
    var copyBtn = document.getElementById("moCopyBtn");
    var spectatorBadge = document.getElementById("moSpectatorBadge");
    var rematchBtn = document.getElementById("moRematchBtn");
    var nameRow = document.getElementById("moNameRow");
    var nameInput = document.getElementById("moNameInput");
    var nameSaveBtn = document.getElementById("moNameSaveBtn");
    var opponentLabel = document.getElementById("moOpponentLabel");
    var joinPanel = document.getElementById("moJoinPanel");
    var joinBtn = document.getElementById("moJoinBtn");

    var topPitsRow = document.getElementById("moTopPitsRow");
    var bottomPitsRow = document.getElementById("moBottomPitsRow");
    var leftStoreEl = document.getElementById("moLeftStore");
    var leftStoreCountEl = document.getElementById("moLeftStoreCount");
    var leftStoreLabelEl = document.getElementById("moLeftStoreLabel");
    var leftStorePebblesEl = document.getElementById("moLeftStorePebbles");

    var rightStoreEl = document.getElementById("moRightStore");
    var rightStoreCountEl = document.getElementById("moRightStoreCount");
    var rightStoreLabelEl = document.getElementById("moRightStoreLabel");
    var rightStorePebblesEl = document.getElementById("moRightStorePebbles");

    var topPlayerNameEl = document.getElementById("moTopPlayerName");
    var topIndicatorEl = document.getElementById("moTopIndicator");
    var bottomPlayerNameEl = document.getElementById("moBottomPlayerName");
    var bottomIndicatorEl = document.getElementById("moBottomIndicator");

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
        return "/mancala-online/room/" + encodeURIComponent(MO_ROOM_CODE) + path;
    }

    function bothSeatsFull(state) {
        return !!(state.seats && state.seats.X && state.seats.O);
    }

    function canTakeSeat(state) {
        return !state.your_seat && !bothSeatsFull(state);
    }

    function apiRequest(method, path, body) {
        var headers = {
            Accept: "application/json",
            "X-MO-Player-Id": getPlayerId(),
        };
        var options = { method: method, headers: headers, credentials: "same-origin" };
        if (method !== "GET") {
            headers["X-CSRFToken"] = MO_CSRF_TOKEN;
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

    var isAnimatingSow = false;

    function renderPebbles(container, count, animLast) {
        container.innerHTML = "";
        var displayCount = Math.min(count, 12);
        for (var i = 0; i < displayCount; i++) {
            var dot = document.createElement("span");
            dot.className = "mo-pebble";
            if (animLast && i === displayCount - 1) {
                dot.classList.add("mo-pebble-anim");
            }
            container.appendChild(dot);
        }
    }

    function getElementByPitIndex(pitIndex) {
        if (leftStoreEl.getAttribute("data-pit-idx") === String(pitIndex)) {
            return leftStoreEl;
        }
        if (rightStoreEl.getAttribute("data-pit-idx") === String(pitIndex)) {
            return rightStoreEl;
        }
        return document.querySelector('.mo-pit[data-pit-idx="' + pitIndex + '"]');
    }

    function animateSowing(lastMove, finalState, onComplete) {
        if (!lastMove || !lastMove.sown_steps || !lastMove.sown_steps.length) {
            onComplete();
            return;
        }

        var sourcePitEl = getElementByPitIndex(lastMove.pit_index);
        if (sourcePitEl) {
            sourcePitEl.classList.add("mo-source-pit");
            var sourceCountEl = sourcePitEl.querySelector(".mo-pit-count");
            if (sourceCountEl) sourceCountEl.textContent = "0";
            var sourcePebbles = sourcePitEl.querySelector(".mo-pit-pebbles");
            if (sourcePebbles) sourcePebbles.innerHTML = "";
        }

        var steps = lastMove.sown_steps;
        var stepDelay = 220; // ms per drop

        steps.forEach(function (pitIdx, i) {
            setTimeout(function () {
                var el = getElementByPitIndex(pitIdx);
                if (el) {
                    el.classList.remove("mo-sowing-target");
                    void el.offsetWidth; // trigger reflow for animation restart
                    el.classList.add("mo-sowing-target");

                    // Increment count display in real time
                    var countEl = el.querySelector(".mo-pit-count") || el.querySelector(".mo-store-count");
                    if (countEl) {
                        var curr = parseInt(countEl.textContent, 10) || 0;
                        countEl.textContent = curr + 1;
                    }

                    var pebblesEl = el.querySelector(".mo-pit-pebbles");
                    if (pebblesEl && countEl) {
                        var currentCount = parseInt(countEl.textContent, 10) || 0;
                        renderPebbles(pebblesEl, currentCount, true);
                    }
                }

                if (i === steps.length - 1) {
                    setTimeout(function () {
                        if (sourcePitEl) sourcePitEl.classList.remove("mo-source-pit");
                        document.querySelectorAll(".mo-sowing-target").forEach(function (e) {
                            e.classList.remove("mo-sowing-target");
                        });
                        onComplete();
                    }, 350);
                }
            }, (i + 1) * stepDelay);
        });
    }

    function updateBoardUI(state) {
        var view = state.view;
        if (!view) return;

        // Stores
        leftStoreCountEl.textContent = view.left_store.count;
        leftStoreLabelEl.textContent = view.top_label;
        leftStoreEl.setAttribute("data-pit-idx", view.left_store.index);
        renderPebbles(leftStorePebblesEl, view.left_store.count);

        rightStoreCountEl.textContent = view.right_store.count;
        rightStoreLabelEl.textContent = view.bottom_label;
        rightStoreEl.setAttribute("data-pit-idx", view.right_store.index);
        renderPebbles(rightStorePebblesEl, view.right_store.count);

        // Player Strips & Turn indicators
        topPlayerNameEl.textContent = view.top_label;
        bottomPlayerNameEl.textContent = view.bottom_label;

        if (state.turn === view.top_seat && state.status === "active") {
            topIndicatorEl.classList.add("mo-active");
        } else {
            topIndicatorEl.classList.remove("mo-active");
        }

        if (state.turn === view.bottom_seat && state.status === "active") {
            bottomIndicatorEl.classList.add("mo-active");
        } else {
            bottomIndicatorEl.classList.remove("mo-active");
        }

        // Top Pits (Opponent: read-only)
        topPitsRow.innerHTML = "";
        view.top_pits.forEach(function (pit) {
            var pitEl = document.createElement("div");
            pitEl.className = "mo-pit mo-pit-top";
            pitEl.setAttribute("data-pit-idx", pit.index);

            var countEl = document.createElement("div");
            countEl.className = "mo-pit-count";
            countEl.textContent = pit.count;
            pitEl.appendChild(countEl);

            var pebbleEl = document.createElement("div");
            pebbleEl.className = "mo-pit-pebbles";
            renderPebbles(pebbleEl, pit.count);
            pitEl.appendChild(pebbleEl);

            topPitsRow.appendChild(pitEl);
        });

        // Bottom Pits (Viewer: interactive if my turn and count > 0)
        bottomPitsRow.innerHTML = "";
        var canMove = view.is_my_turn && !isMoving;
        view.bottom_pits.forEach(function (pit) {
            var pitEl = document.createElement("div");
            pitEl.className = "mo-pit mo-pit-bottom";
            pitEl.setAttribute("data-pit-idx", pit.index);

            if (canMove && pit.count > 0) {
                pitEl.classList.add("mo-pit-interactive");
                pitEl.addEventListener("click", function () {
                    onPitClick(pit.index);
                });
            }

            var countEl = document.createElement("div");
            countEl.className = "mo-pit-count";
            countEl.textContent = pit.count;
            pitEl.appendChild(countEl);

            var pebbleEl = document.createElement("div");
            pebbleEl.className = "mo-pit-pebbles";
            renderPebbles(pebbleEl, pit.count);
            pitEl.appendChild(pebbleEl);

            bottomPitsRow.appendChild(pitEl);
        });
    }

    function onPitClick(pitIndex) {
        if (isMoving || isAnimatingSow) return;
        isMoving = true;
        isAnimatingSow = true;
        statusEl.textContent = "Sowing seeds…";

        apiRequest("POST", "/move", { pit_index: pitIndex })
            .then(function (newState) {
                isMoving = false;
                animateSowing(newState.last_move, newState, function () {
                    isAnimatingSow = false;
                    renderState(newState);
                });
            })
            .catch(function (err) {
                isMoving = false;
                isAnimatingSow = false;
                alert(err.message || "Failed to make move.");
                fetchState();
            });
    }

    function updateStatusMessage(state) {
        statusEl.classList.remove("mo-status-extra");

        if (state.status === "waiting") {
            if (state.your_seat) {
                statusEl.textContent = "Waiting for an opponent to join…";
            } else {
                statusEl.textContent = "Waiting for players to join…";
            }
            return;
        }

        if (state.status === "won") {
            var winnerSeat = state.winner;
            var winnerName = state.names[winnerSeat] || "Player " + winnerSeat;
            var scoreX = state.board[6];
            var scoreO = state.board[13];
            var finalScore = (state.your_seat === "O")
                ? (scoreO + " to " + scoreX)
                : (scoreX + " to " + scoreO);

            if (state.your_seat && winnerSeat === state.your_seat) {
                statusEl.textContent = "🏆 You win! (" + finalScore + ")";
            } else if (state.your_seat) {
                statusEl.textContent = winnerName + " wins! (" + finalScore + ")";
            } else {
                statusEl.textContent = "Game over — " + winnerName + " wins! (" + finalScore + ")";
            }
            return;
        }

        if (state.status === "draw") {
            statusEl.textContent = "Game ended in a tie (" + state.board[6] + " to " + state.board[13] + ")!";
            return;
        }

        // Active game
        var isExtraTurn = state.last_move && state.last_move.extra_turn && (state.last_move.seat === state.turn);
        var activeName = state.names[state.turn] || "Player " + state.turn;

        if (state.view.is_my_turn) {
            if (isExtraTurn) {
                statusEl.textContent = "🌟 Extra Turn! It's still your turn.";
                statusEl.classList.add("mo-status-extra");
            } else {
                statusEl.textContent = "Your turn — pick a pit to sow.";
            }
        } else {
            if (isExtraTurn) {
                statusEl.textContent = activeName + " scored an Extra Turn!";
                statusEl.classList.add("mo-status-extra");
            } else {
                statusEl.textContent = "Waiting for " + activeName + "…";
            }
        }
    }

    function renderState(state) {
        lastState = state;
        lastVersion = state.version;

        joinPanel.hidden = !canTakeSeat(state);
        joinBtn.disabled = isJoining;

        if (canTakeSeat(state)) {
            spectatorBadge.hidden = true;
            shareRow.hidden = true;
            nameRow.hidden = true;
            opponentLabel.hidden = true;
            rematchBtn.hidden = true;
            updateStatusMessage(state);
            updateBoardUI(state);
            return;
        }

        var isPlayer = !!state.your_seat;
        var isFinished = state.status === "won" || state.status === "draw";

        shareRow.hidden = !isPlayer;
        spectatorBadge.hidden = isPlayer || !bothSeatsFull(state);
        nameRow.hidden = !isPlayer;
        rematchBtn.hidden = !(isPlayer && isFinished);

        if (isPlayer && !nameDirty) {
            var currentName = state.your_name || "";
            if (nameInput.value !== currentName && !pendingName) {
                nameInput.value = currentName;
            }
        }

        if (state.your_seat) {
            var oppSeat = state.your_seat === "X" ? "O" : "X";
            if (state.seats[oppSeat]) {
                opponentLabel.textContent = "Opponent: " + (state.names[oppSeat] || "Player " + oppSeat);
                opponentLabel.hidden = false;
            } else {
                opponentLabel.hidden = true;
            }
        } else {
            opponentLabel.hidden = true;
        }

        updateStatusMessage(state);
        updateBoardUI(state);
    }

    function fetchState() {
        if (isAnimatingSow) return Promise.resolve();

        return apiRequest("GET", "/state")
            .then(function (state) {
                if (state.version !== lastVersion || !lastState) {
                    // If an opponent just moved, animate the sowing for the viewer
                    var wasOpponentMove = lastState &&
                        state.last_move &&
                        state.version === lastVersion + 1 &&
                        (!state.your_seat || state.last_move.seat !== state.your_seat);

                    if (wasOpponentMove) {
                        isAnimatingSow = true;
                        animateSowing(state.last_move, state, function () {
                            isAnimatingSow = false;
                            renderState(state);
                        });
                    } else {
                        renderState(state);
                    }
                }
            })
            .catch(function () {
                /* retry on next poll */
            });
    }

    function startPolling() {
        stopPolling();
        pollTimer = setInterval(function () {
            if (document.hidden) return;
            fetchState();
        }, POLL_MS);
    }

    function stopPolling() {
        if (pollTimer) {
            clearInterval(pollTimer);
            pollTimer = null;
        }
    }

    // Event handlers
    copyBtn.addEventListener("click", function () {
        shareLinkInput.select();
        shareLinkInput.setSelectionRange(0, 99999);
        navigator.clipboard.writeText(shareLinkInput.value).then(function () {
            var original = copyBtn.textContent;
            copyBtn.textContent = "Copied!";
            setTimeout(function () {
                copyBtn.textContent = original;
            }, 2000);
        });
    });

    nameInput.addEventListener("input", function () {
        nameDirty = true;
    });

    nameSaveBtn.addEventListener("click", function () {
        var newName = (nameInput.value || "").trim();
        if (isSavingName) return;
        isSavingName = true;
        nameSaveBtn.disabled = true;

        apiRequest("POST", "/name", { name: newName })
            .then(function (state) {
                isSavingName = false;
                nameSaveBtn.disabled = false;
                nameDirty = false;
                renderState(state);
            })
            .catch(function (err) {
                isSavingName = false;
                nameSaveBtn.disabled = false;
                alert(err.message || "Failed to update name.");
            });
    });

    joinBtn.addEventListener("click", function () {
        if (isJoining) return;
        isJoining = true;
        joinBtn.disabled = true;

        apiRequest("POST", "/join", {})
            .then(function (state) {
                isJoining = false;
                joinBtn.disabled = false;
                renderState(state);
            })
            .catch(function (err) {
                isJoining = false;
                joinBtn.disabled = false;
                alert(err.message || "Could not join game.");
            });
    });

    rematchBtn.addEventListener("click", function () {
        rematchBtn.disabled = true;
        apiRequest("POST", "/rematch")
            .then(function (state) {
                rematchBtn.disabled = false;
                renderState(state);
            })
            .catch(function (err) {
                rematchBtn.disabled = false;
                alert(err.message || "Could not start rematch.");
            });
    });

    document.addEventListener("visibilitychange", function () {
        if (!document.hidden) {
            fetchState();
        }
    });

    function initRoom() {
        apiRequest("GET", "/state")
            .then(function (state) {
                renderState(state);
            })
            .catch(function (err) {
                statusEl.textContent = err.message || "Could not load this room.";
            })
            .then(startPolling);
    }

    initRoom();
})();

/**
 * Kids Words - vanilla JS game logic
 * All letters displayed uppercase; word lists stay lowercase for validation
 */

(function () {
  "use strict";

  const API = window.KIDS_WORDS_API || {};
  const STORAGE_KEY = "kids_words_game";
  const STATS_KEY = "kids_words_stats";
  let validGuesses = new Set();
  let answerSets = { grade2: [], grade4: [], adult: [] };
  let dataReady = false;
  let selectedDifficulty = null;
  let selectedWordCount = null;

  function byId(id) {
    return document.getElementById(id);
  }

  function all(sel, root) {
    return (root || document).querySelectorAll(sel);
  }

  function loadData() {
    const loadingEl = byId("kwLoading");
    const setupContentEl = byId("kwSetupContent");

    loadingEl.classList.remove("kw-hidden");
    setupContentEl.classList.add("kw-hidden");

    Promise.all([
      fetch(API.grade2).then(function (r) {
        if (!r.ok) throw new Error("Grade 2 words not found");
        return r.json();
      }),
      fetch(API.grade4).then(function (r) {
        if (!r.ok) throw new Error("Grade 4 words not found");
        return r.json();
      }),
      fetch(API.guesses).then(function (r) {
        if (!r.ok) return [];
        return r.json();
      }),
    ])
      .then(function ([grade2Data, grade4Data, guessesArr]) {
        validGuesses = new Set(
          Object.keys(grade2Data).concat(
            Object.keys(grade4Data),
            guessesArr.filter(Boolean)
          )
        );

        answerSets.grade2 = Object.keys(grade2Data).filter(
          (w) => grade2Data[w] === "yes"
        );
        answerSets.grade4 = Object.keys(grade4Data).filter(
          (w) => grade4Data[w] === "yes"
        );
        answerSets.adult = Object.keys(grade2Data);

        dataReady = true;
        loadingEl.classList.add("kw-hidden");
        setupContentEl.classList.remove("kw-hidden");
        updateStartButton();
        checkForSavedGame();
      })
      .catch(function (err) {
        console.error("Kids Words: failed to load data", err);
        if (loadingEl) loadingEl.textContent = "Failed to load word lists. Please refresh.";
      });
  }

  function updateStartButton() {
    const btn = byId("kwStartBtn");
    if (!btn) return;
    btn.disabled = !dataReady || !selectedDifficulty || !selectedWordCount;
  }

  function saveGameState() {
    try {
      const data = {
        difficulty: selectedDifficulty,
        wordCount: selectedWordCount,
        answers: gameState.answers,
        maxGuesses: gameState.maxGuesses,
        guesses: gameState.guesses,
        gridResults: gameState.gridResults,
        solved: gameState.solved,
        guessIndex: gameState.guessIndex,
      };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    } catch (e) {
      console.warn("Kids Words: could not save game state", e);
    }
  }

  function hasSavedGame() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return false;
      const data = JSON.parse(raw);
      return data.answers && data.answers.length > 0;
    } catch (e) {
      return false;
    }
  }

  function checkForSavedGame() {
    const section = byId("kwResumeSection");
    if (!section) return;
    if (hasSavedGame()) {
      section.classList.remove("kw-hidden");
    } else {
      section.classList.add("kw-hidden");
    }
  }

  function resumeGame() {
    if (!dataReady) return;
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const data = JSON.parse(raw);
      if (!data.answers || !data.answers.length) return;
      selectedDifficulty = data.difficulty;
      selectedWordCount = data.wordCount;
      selectDifficulty(selectedDifficulty);
      selectWordCount(selectedWordCount);
      gameState = {
        answers: data.answers,
        maxGuesses: data.maxGuesses,
        guessIndex: data.guessIndex,
        currentGuess: "",
        guesses: data.guesses || [],
        gridResults: data.gridResults || data.answers.map(function () { return []; }),
        solved: data.solved || data.answers.map(function () { return false; }),
        gameOver: false,
      };
      byId("kwSetup").classList.add("kw-hidden");
      byId("kwGame").classList.remove("kw-hidden");
      byId("kwWin").classList.add("kw-hidden");
      byId("kwLose").classList.add("kw-hidden");
      byId("kwToast").classList.add("kw-hidden");
      buildBoard(gameState.answers, gameState.maxGuesses);
      buildKeyboard();
      resumeGame._restoring = true;
      restoreBoardFromState();
      resumeGame._restoring = false;
      updateKeyboardFeedback();
      clearInputRow();
      byId("kwBoard") && byId("kwBoard").focus();
    } catch (e) {
      console.warn("Kids Words: could not restore game", e);
      localStorage.removeItem(STORAGE_KEY);
      checkForSavedGame();
    }
  }

  function restoreBoardFromState() {
    const grids = all(".kw-word-grid");
    const guesses = gameState.guesses;
    for (let g = 0; g < guesses.length; g++) {
      const guess = guesses[g];
      for (let w = 0; w < gameState.answers.length; w++) {
        const feedback = gameState.gridResults[w][g];
        if (!feedback) continue;
        /* skip if word was already solved at an earlier guess */
        let alreadySolved = false;
        for (let g0 = 0; g0 < g; g0++) {
          const fb = gameState.gridResults[w][g0];
          if (fb && fb.every(function (x) { return x === "correct"; })) {
            alreadySolved = true;
            break;
          }
        }
        if (alreadySolved) continue;
        const rowEl = grids[w].querySelectorAll(".kw-word-row")[g];
        const cells = rowEl.querySelectorAll(".kw-cell");
        for (let i = 0; i < 5; i++) {
          cells[i].textContent = guess[i].toUpperCase();
          cells[i].classList.remove("kw-cell-correct", "kw-cell-present", "kw-cell-absent");
          cells[i].classList.add("kw-cell-" + feedback[i]);
        }
      }
    }
    if (gameState.solved.every(Boolean)) {
      gameState.gameOver = true;
      showWin();
      return;
    }
    if (gameState.guessIndex >= gameState.maxGuesses) {
      gameState.gameOver = true;
      showLose();
    }
  }

  function getStats() {
    try {
      const raw = localStorage.getItem(STATS_KEY);
      if (!raw) return { grade2: { played: 0, won: 0 }, grade4: { played: 0, won: 0 }, adult: { played: 0, won: 0 } };
      const data = JSON.parse(raw);
      return {
        grade2: { played: data.grade2?.played || 0, won: data.grade2?.won || 0 },
        grade4: { played: data.grade4?.played || 0, won: data.grade4?.won || 0 },
        adult: { played: data.adult?.played || 0, won: data.adult?.won || 0 },
      };
    } catch (e) {
      return { grade2: { played: 0, won: 0 }, grade4: { played: 0, won: 0 }, adult: { played: 0, won: 0 } };
    }
  }

  function updateStats(won) {
    if (!selectedDifficulty) return;
    try {
      const stats = getStats();
      let d = stats[selectedDifficulty];
      if (!d) d = { played: 0, won: 0 };
      d.played = (d.played || 0) + 1;
      if (won) d.won = (d.won || 0) + 1;
      stats[selectedDifficulty] = d;
      localStorage.setItem(STATS_KEY, JSON.stringify(stats));
      renderStats();
    } catch (e) {
      console.warn("Kids Words: could not save stats", e);
    }
  }

  function renderStats() {
    const el = byId("kwStats");
    if (!el) return;
    const stats = getStats();
    const labels = { grade2: "Grade 2", grade4: "Grade 4", adult: "Adult" };
    const rows = [];
    for (const k in labels) {
      const d = stats[k];
      const p = d.played || 0;
      const w = d.won || 0;
      rows.push(labels[k] + ": " + (p === 0 ? "—" : w + " / " + p + " (" + (p > 0 ? Math.round(100 * w / p) : 0) + "%)"));
    }
    el.innerHTML = rows.map(function (r) { return "<div class=\"kw-stats-row\">" + r + "</div>"; }).join("");
  }

  function selectDifficulty(difficulty) {
    selectedDifficulty = difficulty || null;
    all(".kw-difficulty-btn").forEach(function (b) {
      b.classList.toggle("kw-selected", b.dataset.difficulty === selectedDifficulty);
    });
    updateStartButton();
  }

  function selectWordCount(count) {
    selectedWordCount = count === undefined || count === null ? null : parseInt(count, 10);
    all(".kw-word-count-btn").forEach(function (b) {
      b.classList.toggle(
        "kw-selected",
        parseInt(b.dataset.count, 10) === selectedWordCount
      );
    });
    updateStartButton();
  }

  function pickRandomAnswers(count) {
    const arr = answerSets[selectedDifficulty];
    if (!arr || arr.length < count) return [];
    const shuffled = arr.slice().sort(function () { return Math.random() - 0.5; });
    const seen = new Set();
    const out = [];
    for (let i = 0; i < shuffled.length && out.length < count; i++) {
      if (!seen.has(shuffled[i])) {
        seen.add(shuffled[i]);
        out.push(shuffled[i]);
      }
    }
    return out;
  }

  /** Wordle-style evaluation: 'correct' | 'present' | 'absent' per position */
  function evaluateGuess(guess, answer) {
    const g = guess.toLowerCase().split("");
    const a = answer.toLowerCase().split("");
    const result = new Array(5).fill("absent");
    const used = new Array(5).fill(false);

    for (let i = 0; i < 5; i++) {
      if (g[i] === a[i]) {
        result[i] = "correct";
        used[i] = true;
      }
    }
    for (let i = 0; i < 5; i++) {
      if (result[i] === "correct") continue;
      for (let j = 0; j < 5; j++) {
        if (!used[j] && g[i] === a[j]) {
          result[i] = "present";
          used[j] = true;
          break;
        }
      }
    }
    return result;
  }

  let gameState = {
    answers: [],
    maxGuesses: 0,
    guessIndex: 0,
    currentGuess: "",
    guesses: [],
    gridResults: [],
    solved: [],
    gameOver: false,
  };

  const KEYBOARD_ROWS = [
    ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p"],
    ["a", "s", "d", "f", "g", "h", "j", "k", "l"],
    ["Enter", "z", "x", "c", "v", "b", "n", "m", "Backspace"],
  ];

  function clearInputRow() {
    const grids = all(".kw-word-grid");
    const guessIdx = gameState.guessIndex;
    for (let w = 0; w < gameState.answers.length; w++) {
      if (gameState.solved[w]) continue;
      const rowEl = grids[w].querySelectorAll(".kw-word-row")[guessIdx];
      if (!rowEl) continue;
      const cells = rowEl.querySelectorAll(".kw-cell");
      for (let i = 0; i < 5; i++) {
        cells[i].textContent = "";
        cells[i].classList.remove("kw-cell-correct", "kw-cell-present", "kw-cell-absent");
      }
    }
  }

  function updateInputRow(text) {
    const grids = all(".kw-word-grid");
    const guessIdx = gameState.guessIndex;
    for (let w = 0; w < gameState.answers.length; w++) {
      if (gameState.solved[w]) continue;
      const rowEl = grids[w].querySelectorAll(".kw-word-row")[guessIdx];
      if (!rowEl) continue;
      const cells = rowEl.querySelectorAll(".kw-cell");
      for (let i = 0; i < 5; i++) {
        cells[i].textContent = (text[i] || "").toUpperCase();
        cells[i].classList.remove("kw-cell-correct", "kw-cell-present", "kw-cell-absent");
      }
    }
  }

  function showToast(msg) {
    const el = byId("kwToast");
    if (!el) return;
    el.textContent = msg;
    el.classList.remove("kw-hidden");
    clearTimeout(showToast._timer);
    showToast._timer = setTimeout(function () {
      el.classList.add("kw-hidden");
    }, 2000);
  }

  function showWin() {
    byId("kwWin").classList.remove("kw-hidden");
    byId("kwLose").classList.add("kw-hidden");
    gameState.gameOver = true;
    if (!resumeGame._restoring) updateStats(true);
  }

  function showLose() {
    byId("kwWin").classList.add("kw-hidden");
    const loseEl = byId("kwLose");
    loseEl.classList.remove("kw-hidden");
    const answersEl = byId("kwLoseAnswers");
    answersEl.innerHTML = "";
    gameState.answers.forEach(function (word) {
      const span = document.createElement("span");
      span.className = "kw-answer-word";
      span.textContent = word.toUpperCase();
      answersEl.appendChild(span);
    });
    gameState.gameOver = true;
    if (!resumeGame._restoring) updateStats(false);
  }

  function submitGuess() {
    const guess = gameState.currentGuess.toLowerCase();
    if (guess.length !== 5) return;
    if (!validGuesses.has(guess)) {
      showToast("Not in word list");
      return;
    }

    const answers = gameState.answers;
    const guessIdx = gameState.guessIndex;
    const grids = all(".kw-word-grid");

    for (let w = 0; w < answers.length; w++) {
      if (gameState.solved[w]) continue; /* skip already-solved words */
      const feedback = evaluateGuess(guess, answers[w]);
      gameState.gridResults[w][guessIdx] = feedback;
      const rowEl = grids[w].querySelectorAll(".kw-word-row")[guessIdx];
      const cells = rowEl.querySelectorAll(".kw-cell");
      for (let i = 0; i < 5; i++) {
        cells[i].textContent = guess[i].toUpperCase();
        cells[i].classList.remove("kw-cell-correct", "kw-cell-present", "kw-cell-absent");
        cells[i].classList.add("kw-cell-" + feedback[i]);
      }
      const allCorrect = feedback.every(function (x) { return x === "correct"; });
      if (allCorrect) gameState.solved[w] = true;
    }

    gameState.guesses.push(guess);
    gameState.currentGuess = "";
    gameState.guessIndex += 1;
    clearInputRow();
    updateKeyboardFeedback();
    saveGameState();

    if (gameState.solved.every(Boolean)) {
      showWin();
      return;
    }
    if (gameState.guessIndex >= gameState.maxGuesses) {
      showLose();
      return;
    }
  }

  function buildKeyboard() {
    const container = byId("kwKeyboard");
    if (!container) return;
    container.innerHTML = "";
    KEYBOARD_ROWS.forEach(function (row) {
      const rowEl = document.createElement("div");
      rowEl.className = "kw-keyboard-row";
      row.forEach(function (key) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "kw-key";
        btn.dataset.key = key;
        btn.textContent = key === "Enter" ? "Enter" : key === "Backspace" ? "⌫" : key.toUpperCase();
        if (key === "Enter" || key === "Backspace") btn.classList.add("kw-key-wide");
        btn.addEventListener("click", function () {
          if (gameState.gameOver) return;
          if (key === "Enter") {
            submitGuess();
            return;
          }
          if (key === "Backspace") {
            if (gameState.currentGuess.length > 0) {
              gameState.currentGuess = gameState.currentGuess.slice(0, -1);
              updateInputRow(gameState.currentGuess);
            }
            byId("kwBoard") && byId("kwBoard").focus();
            return;
          }
          if (gameState.currentGuess.length < 5) {
            gameState.currentGuess += key;
            updateInputRow(gameState.currentGuess);
            byId("kwBoard") && byId("kwBoard").focus();
          }
        });
        rowEl.appendChild(btn);
      });
      container.appendChild(rowEl);
    });
  }

  /** Best status per letter across all words and guesses: correct > present > absent */
  function updateKeyboardFeedback() {
    const container = byId("kwKeyboard");
    if (!container) return;
    const letterStatus = {};
    const order = { correct: 3, present: 2, absent: 1 };
    const answers = gameState.answers;
    const gridResults = gameState.gridResults;
    const guesses = gameState.guesses;

    for (let g = 0; g < guesses.length; g++) {
      const guess = guesses[g];
      for (let w = 0; w < answers.length; w++) {
        const feedback = gridResults[w][g];
        if (!feedback) continue;
        for (let i = 0; i < 5; i++) {
          const letter = guess[i];
          const status = feedback[i];
          const current = letterStatus[letter];
          if (!current || order[status] > order[current]) {
            letterStatus[letter] = status;
          }
        }
      }
    }

    all(".kw-key[data-key]", container).forEach(function (btn) {
      const key = btn.dataset.key;
      if (key === "Enter" || key === "Backspace") return;
      const status = letterStatus[key];
      btn.classList.remove("kw-key-correct", "kw-key-present", "kw-key-absent");
      if (status) btn.classList.add("kw-key-" + status);
    });
  }

  function getColumnsForWordCount(n) {
    const w = window.innerWidth;
    if (w >= 900) {
      if (n <= 4) return 4;
      if (n <= 6) return 6;
      return 4;
    }
    if (w >= 768) {
      if (n === 6) return 3;
      return 2;
    }
    if (n === 8) return 4;
    return n <= 2 ? n : 2;
  }

  function buildBoard(answers, maxGuesses) {
    const board = byId("kwBoard");
    board.innerHTML = "";
    const n = answers.length;
    const cols = getColumnsForWordCount(n);
    const layoutClass = "kw-layout-" + n;
    const container = document.createElement("div");
    container.className = "kw-grids " + layoutClass;
    container.dataset.columns = cols;

    for (let rowStart = 0; rowStart < n; rowStart += cols) {
      const rowWrapper = document.createElement("div");
      rowWrapper.className = "kw-grid-row";
      const rowEnd = Math.min(rowStart + cols, n);
      for (let w = rowStart; w < rowEnd; w++) {
        const grid = document.createElement("div");
        grid.className = "kw-word-grid";
        grid.dataset.wordIndex = w;
        for (let row = 0; row < maxGuesses; row++) {
          const rowEl = document.createElement("div");
          rowEl.className = "kw-word-row";
          for (let col = 0; col < 5; col++) {
            const cell = document.createElement("div");
            cell.className = "kw-cell";
            rowEl.appendChild(cell);
          }
          grid.appendChild(rowEl);
        }
        rowWrapper.appendChild(grid);
      }
      container.appendChild(rowWrapper);
    }
    board.appendChild(container);
  }

  function handleKeydown(e) {
    if (gameState.gameOver || !gameState.answers.length) return;
    var active = document.activeElement;
    if (active && (active.tagName === "INPUT" || active.tagName === "TEXTAREA" || active.isContentEditable)) {
      return;
    }

    if (e.key === "Backspace") {
      e.preventDefault();
      if (gameState.currentGuess.length > 0) {
        gameState.currentGuess = gameState.currentGuess.slice(0, -1);
        updateInputRow(gameState.currentGuess);
      }
      return;
    }
    if (e.key === "Enter") {
      e.preventDefault();
      submitGuess();
      return;
    }
    if (e.key.length === 1 && /^[a-zA-Z]$/.test(e.key)) {
      e.preventDefault();
      if (gameState.currentGuess.length < 5) {
        gameState.currentGuess += e.key.toLowerCase();
        updateInputRow(gameState.currentGuess);
      }
    }
  }

  function startGame() {
    if (!selectedDifficulty || !selectedWordCount) return;
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch (e) {}
    const answers = pickRandomAnswers(selectedWordCount);
    if (answers.length !== selectedWordCount) return;

    const maxGuesses = selectedWordCount + 5;
    gameState = {
      answers: answers,
      maxGuesses: maxGuesses,
      guessIndex: 0,
      currentGuess: "",
      guesses: [],
      gridResults: answers.map(function () { return []; }),
      solved: answers.map(function () { return false; }),
      gameOver: false,
    };

    byId("kwSetup").classList.add("kw-hidden");
    byId("kwGame").classList.remove("kw-hidden");
    byId("kwWin").classList.add("kw-hidden");
    byId("kwLose").classList.add("kw-hidden");
    byId("kwToast").classList.add("kw-hidden");

    buildBoard(answers, maxGuesses);
    buildKeyboard();
    clearInputRow();
    const board = byId("kwBoard");
    if (board) board.focus();
  }

  function newGame(skipConfirm) {
    if (!skipConfirm && !confirm("Leave this game and return to setup? Your progress will be lost.")) {
      return;
    }
    selectedDifficulty = null;
    selectedWordCount = null;
    selectDifficulty(null);
    selectWordCount(null);
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch (e) {}
    byId("kwGame").classList.add("kw-hidden");
    byId("kwSetup").classList.remove("kw-hidden");
    updateStartButton();
    checkForSavedGame();
    renderStats();
  }

  function init() {
    loadData();
    renderStats();

    all(".kw-difficulty-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        selectDifficulty(btn.dataset.difficulty);
      });
    });

    all(".kw-word-count-btn").forEach(function (btn) {
      btn.addEventListener("click", function () {
        selectWordCount(parseInt(btn.dataset.count, 10));
      });
    });

    const startBtn = byId("kwStartBtn");
    if (startBtn) startBtn.addEventListener("click", startGame);

    const resumeBtn = byId("kwResumeBtn");
    if (resumeBtn) resumeBtn.addEventListener("click", resumeGame);

    const winNewGameBtn = byId("kwWinNewGameBtn");
    if (winNewGameBtn) winNewGameBtn.addEventListener("click", function () { newGame(true); });
    const loseNewGameBtn = byId("kwLoseNewGameBtn");
    if (loseNewGameBtn) loseNewGameBtn.addEventListener("click", function () { newGame(true); });

    document.addEventListener("keydown", handleKeydown);

    const board = byId("kwBoard");
    if (board) {
      board.addEventListener("click", function () {
        board.focus();
      });
    }

    let resizeTimer;
    window.addEventListener("resize", function () {
      if (!gameState.answers.length || gameState.gameOver) return;
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(function () {
        buildBoard(gameState.answers, gameState.maxGuesses);
        restoreBoardFromState();
        updateInputRow(gameState.currentGuess);
      }, 150);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

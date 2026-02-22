/**
 * Kids Words - vanilla JS game logic
 * All letters displayed uppercase; word lists stay lowercase for validation
 */

(function () {
  "use strict";

  const API = window.KIDS_WORDS_API || {};
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
      fetch(API.grade2).then((r) => r.json()),
      fetch(API.grade4).then((r) => r.json()),
      fetch(API.guesses).then((r) => r.json()),
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
    gridResults: [],
    solved: [],
    gameOver: false,
  };

  function clearInputRow() {
    all(".kw-input-cell").forEach(function (cell) {
      cell.textContent = "";
    });
  }

  function updateInputRow(text) {
    const cells = all(".kw-input-cell");
    for (let i = 0; i < 5; i++) {
      cells[i].textContent = text[i] || "";
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
    byId("kwInputArea").classList.add("kw-hidden");
    byId("kwWin").classList.remove("kw-hidden");
    byId("kwLose").classList.add("kw-hidden");
    gameState.gameOver = true;
  }

  function showLose() {
    byId("kwInputArea").classList.add("kw-hidden");
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

    gameState.currentGuess = "";
    gameState.guessIndex += 1;
    clearInputRow();

    if (gameState.solved.every(Boolean)) {
      showWin();
      return;
    }
    if (gameState.guessIndex >= gameState.maxGuesses) {
      showLose();
      return;
    }
  }

  function buildBoard(answers, maxGuesses) {
    const board = byId("kwBoard");
    board.innerHTML = "";
    const n = answers.length;
    const layoutClass = "kw-layout-" + n;
    const container = document.createElement("div");
    container.className = "kw-grids " + layoutClass;

    for (let w = 0; w < n; w++) {
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
      container.appendChild(grid);
    }
    board.appendChild(container);
  }

  function handleKeydown(e) {
    if (gameState.gameOver) return;
    const inputRow = byId("kwInputRow");
    if (!inputRow || !document.activeElement || document.activeElement.id !== "kwInputRow") {
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
    const answers = pickRandomAnswers(selectedWordCount);
    if (answers.length !== selectedWordCount) return;

    const maxGuesses = selectedWordCount + 5;
    gameState = {
      answers: answers,
      maxGuesses: maxGuesses,
      guessIndex: 0,
      currentGuess: "",
      gridResults: answers.map(function () { return []; }),
      solved: answers.map(function () { return false; }),
      gameOver: false,
    };

    byId("kwSetup").classList.add("kw-hidden");
    byId("kwGame").classList.remove("kw-hidden");
    const inputArea = byId("kwInputArea");
    if (inputArea) inputArea.classList.remove("kw-hidden");
    byId("kwWin").classList.add("kw-hidden");
    byId("kwLose").classList.add("kw-hidden");
    byId("kwToast").classList.add("kw-hidden");

    buildBoard(answers, maxGuesses);
    clearInputRow();
    const inputRow = byId("kwInputRow");
    if (inputRow) inputRow.focus();
  }

  function newGame() {
    selectedDifficulty = null;
    selectedWordCount = null;
    selectDifficulty(null);
    selectWordCount(null);
    byId("kwGame").classList.add("kw-hidden");
    byId("kwSetup").classList.remove("kw-hidden");
    updateStartButton();
  }

  function init() {
    loadData();

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

    const newGameBtn = byId("kwNewGameBtn");
    if (newGameBtn) newGameBtn.addEventListener("click", newGame);

    document.addEventListener("keydown", handleKeydown);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

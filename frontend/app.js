// Owned by C. Talks to the /api/* endpoints defined in PLAN.md §2 / backend/models.py.
// session_id persists in localStorage so a page reload doesn't lose your progress
// (this is a real app the user runs locally, not an in-chat artifact, so this is fine).

const API_BASE = "/api";

function getSessionId() {
  let id = localStorage.getItem("interrogation_session_id");
  if (!id) {
    id = "session-" + Math.random().toString(36).slice(2, 10);
    localStorage.setItem("interrogation_session_id", id);
  }
  return id;
}

let sessionId = getSessionId();
let selectedSuspectId = null;
let suspects = [];

let renderedClueCount = 0;
const chatLogsBySuspect = {}; // suspect_id -> [{cls, text}, ...], client-side only

async function loadCase() {
  const res = await fetch(`${API_BASE}/case`);
  const data = await res.json();
  suspects = data.suspects;

  document.getElementById("case-title").textContent =
    `${data.title}`;

  const cardsEl = document.getElementById("suspect-cards");
  cardsEl.innerHTML = "";
  suspects.forEach((s) => {
    const card = document.createElement("div");
    card.className = "suspect-card";
    card.textContent = s.name;
    card.dataset.suspectId = s.id;
    card.addEventListener("click", () => selectSuspect(s.id, s.name));
    cardsEl.appendChild(card);
  });

  const select = document.getElementById("accuse-select");
  select.innerHTML = "";
  suspects.forEach((s) => {
    const opt = document.createElement("option");
    opt.value = s.id;
    opt.textContent = s.name;
    select.appendChild(opt);
  });
}

function selectSuspect(id, name) {
  selectedSuspectId = id;
  document.querySelectorAll(".suspect-card").forEach((c) => {
    c.classList.toggle("selected", c.dataset.suspectId === id);
  });
  document.getElementById("chat-panel").classList.remove("hidden");
  document.getElementById("chat-suspect-name").textContent = `Interrogating: ${name}`;

  const log = document.getElementById("chat-log");
  log.innerHTML = "";
  (chatLogsBySuspect[id] || []).forEach(({ cls, text }) => renderChatLine(cls, text));
  log.scrollTop = log.scrollHeight;
}

function renderChatLine(cls, text) {
  const log = document.getElementById("chat-log");
  const line = document.createElement("div");
  line.className = `chat-msg ${cls}`;
  line.textContent = text;
  log.appendChild(line);
  log.scrollTop = log.scrollHeight;
}

function appendChatLine(suspectId, cls, text) {
  if (!chatLogsBySuspect[suspectId]) chatLogsBySuspect[suspectId] = [];
  chatLogsBySuspect[suspectId].push({ cls, text });
  if (suspectId === selectedSuspectId) renderChatLine(cls, text);
}

async function playSpeech(suspectId, text) {
  try {
    const res = await fetch(`${API_BASE}/suspects/${suspectId}/speech`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (!res.ok) return; // best-effort — a TTS failure shouldn't break the chat
    const blob = await res.blob();
    new Audio(URL.createObjectURL(blob)).play();
  } catch (e) {
    console.error("TTS playback failed", e);
  }
}

async function sendMessage(message) {
  if (!selectedSuspectId) return;
  const askedSuspectId = selectedSuspectId;
  appendChatLine(askedSuspectId, "player", `You: ${message}`);

  const res = await fetch(`${API_BASE}/suspects/${askedSuspectId}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, message }),
  });
  const data = await res.json();
  appendChatLine(data.suspect_id, "suspect", `${data.suspect_id}: ${data.reply}`);
  if (data.suspect_id === selectedSuspectId) playSpeech(data.suspect_id, data.reply);
  await loadClues();
}

async function loadClues() {
  const res = await fetch(`${API_BASE}/clues?session_id=${encodeURIComponent(sessionId)}`);
  const data = await res.json();
  const board = document.getElementById("clue-board");
  const boardPanel = document.getElementById("clue-board-panel");

  if (data.claims.length === 0) {
    board.innerHTML = "<p>No clues pinned yet - ask a suspect something.</p>";
    renderedClueCount = 0;
    return;
  }
  if (renderedClueCount === 0) board.innerHTML = "";

  // Only append newly-arrived claims so previously-pinned notes (and any
  // position the player dragged them to) aren't rebuilt from scratch.
  for (let i = renderedClueCount; i < data.claims.length; i++) {
    const c = data.claims[i];
    const card = document.createElement("div");
    card.className = "claim-card";
    card.dataset.speakerId = c.speaker_id;

    const speaker = document.createElement("div");
    speaker.className = "claim-speaker";
    speaker.textContent = suspects.find((s) => s.id === c.speaker_id)?.name || c.speaker_id;

    const text = document.createElement("p");
    text.className = "claim-text";
    text.textContent = c.statement;

    card.appendChild(speaker);
    card.appendChild(text);
    board.appendChild(card);
    makePinDraggable(card, boardPanel);
  }
  renderedClueCount = data.claims.length;
}

function makePinDraggable(card, container) {
  card.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    // Absolutely positioned children sit relative to the container's padding
    // box (inside its border), while getBoundingClientRect() gives the outer
    // border box — offset by clientLeft/clientTop (the border width) so a
    // card doesn't jump when the drag starts.
    const containerRect = container.getBoundingClientRect();
    const paddingBoxLeft = containerRect.left + container.clientLeft;
    const paddingBoxTop = containerRect.top + container.clientTop;
    const cardRect = card.getBoundingClientRect();
    const startLeft = cardRect.left - paddingBoxLeft;
    const startTop = cardRect.top - paddingBoxTop;

    // Pulling this card out of the flex flow would let the board shrink to
    // fit the remaining cards — lock in its current height first.
    container.style.minHeight = `${containerRect.height}px`;

    card.style.position = "absolute";
    card.style.left = `${startLeft}px`;
    card.style.top = `${startTop}px`;
    card.style.margin = "0";
    card.classList.add("dragging");
    card.setPointerCapture(e.pointerId);

    const startX = e.clientX;
    const startY = e.clientY;

    // Cards rest at a slight CSS rotation, which visually extends their
    // corners a bit past their unrotated box — pad the clamp so a tilted
    // note can never poke past the cork board's edge.
    const EDGE_BUFFER = 16;

    function onMove(ev) {
      // clientWidth/clientHeight are the padding-box size (border excluded) —
      // the same box the card's left/top are positioned within.
      const maxLeft = Math.max(EDGE_BUFFER, container.clientWidth - card.offsetWidth - EDGE_BUFFER);
      const maxTop = Math.max(EDGE_BUFFER, container.clientHeight - card.offsetHeight - EDGE_BUFFER);
      const left = Math.min(Math.max(EDGE_BUFFER, startLeft + (ev.clientX - startX)), maxLeft);
      const top = Math.min(Math.max(EDGE_BUFFER, startTop + (ev.clientY - startY)), maxTop);
      card.style.left = `${left}px`;
      card.style.top = `${top}px`;
    }

    function onUp(ev) {
      card.releasePointerCapture(ev.pointerId);
      card.classList.remove("dragging");
      card.removeEventListener("pointermove", onMove);
      card.removeEventListener("pointerup", onUp);
    }

    card.addEventListener("pointermove", onMove);
    card.addEventListener("pointerup", onUp);
  });
}

async function makeAccusation(accusedId, motive) {
  const res = await fetch(`${API_BASE}/accuse`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, accused_id: accusedId, motive_guess: motive }),
  });
  const data = await res.json();
  showReveal(data);
}

function showReveal(data) {
  document.getElementById("reveal-verdict").textContent = data.correct
    ? "Correct! Case closed."
    : "Wrong suspect.";
  document.getElementById("reveal-story").textContent = data.true_story;
  document.getElementById("reveal-score").textContent =
    `${data.score.rank} (${data.score.stars}/3) — ${data.score.summary}`;
  document.getElementById("reveal-modal").classList.remove("hidden");
}

function clearBoardUI() {
  Object.keys(chatLogsBySuspect).forEach((id) => delete chatLogsBySuspect[id]);
  document.getElementById("chat-panel").classList.add("hidden");
  document.getElementById("reveal-modal").classList.add("hidden");
  selectedSuspectId = null;
}

// Replays the SAME case at default difficulty: wipes chat histories + clue board, keeps suspects/solution.
async function resetCase() {
  try {
    const res = await fetch(`${API_BASE}/reset`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId }),
    });
    if (!res.ok) throw new Error(`server said ${res.status}`);
    clearBoardUI();
    await loadClues();
  } catch (err) {
    alert(`Couldn't restart the case: ${err.message}`);
  }
}

// Generates a brand new case (new suspects, new solution) at the selected
// difficulty (controls how hard suspects are to crack) and starts fresh.
async function startNewGame() {
  try {
    const difficulty = document.getElementById("difficulty-select").value;
    const res = await fetch(`${API_BASE}/new-game`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, difficulty }),
    });
    if (!res.ok) throw new Error(`server said ${res.status}`);
    clearBoardUI();
    await loadCase();
    await loadClues();
  } catch (err) {
    alert(`Couldn't start a new game: ${err.message}`);
  }
}

document.getElementById("chat-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const input = document.getElementById("chat-input");
  const message = input.value.trim();
  if (!message) return;
  input.value = "";
  sendMessage(message);
});

document.getElementById("accuse-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const accusedId = document.getElementById("accuse-select").value;
  const motive = document.getElementById("motive-input").value.trim();
  makeAccusation(accusedId, motive);
});

document.getElementById("reset-btn").addEventListener("click", resetCase);
document.getElementById("new-game-btn").addEventListener("click", startNewGame);
document.getElementById("reveal-close").addEventListener("click", () => {
  document.getElementById("reveal-modal").classList.add("hidden");
});

loadCase();
loadClues();

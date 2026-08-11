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
let contradictions = []; // Contradiction[] from the last /api/clues fetch
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
  const speakerName = suspects.find((s) => s.id === data.suspect_id)?.name || data.suspect_id;
  appendChatLine(data.suspect_id, "suspect", `${speakerName}: ${data.reply}`);
  if (data.suspect_id === selectedSuspectId) playSpeech(data.suspect_id, data.reply);
  await loadClues();
}

async function loadClues() {
  const res = await fetch(`${API_BASE}/clues?session_id=${encodeURIComponent(sessionId)}`);
  const data = await res.json();
  contradictions = data.contradictions || [];
  const board = document.getElementById("clue-board");
  const boardPanel = document.getElementById("clue-board-panel");

  if (data.claims.length === 0) {
    board.innerHTML = "<p>No clues pinned yet - ask a suspect something.</p>";
    renderedClueCount = 0;
    contradictions = [];
    drawContradictionLines();
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
    card.dataset.claimId = c.id;

    const speaker = document.createElement("div");
    speaker.className = "claim-speaker";
    speaker.textContent = suspects.find((s) => s.id === c.speaker_id)?.name || c.speaker_id;

    const text = document.createElement("p");
    text.className = "claim-text";
    text.textContent = c.statement;

    card.appendChild(speaker);
    card.appendChild(text);
    board.appendChild(card);
    makePinDraggable(card, board, boardPanel);
  }
  renderedClueCount = data.claims.length;
  renderContradictions();
}

function renderContradictions() {
  const board = document.getElementById("clue-board");
  contradictions.forEach((con) => {
    [con.claim_id_a, con.claim_id_b].forEach((claimId) => {
      const card = board.querySelector(`[data-claim-id="${CSS.escape(String(claimId))}"]`);
      if (!card) return; // referenced claim not rendered yet - skip gracefully

      let badge = card.querySelector(".contradiction-badge");
      if (!badge) {
        badge = document.createElement("span");
        badge.className = "contradiction-badge";
        badge.textContent = "⚠";
        card.appendChild(badge);
      }
      // Recompute the full tooltip every time from the complete contradictions
      // list so repeated calls stay correct without diffing/dedup logic.
      badge.title = contradictions
        .filter((c) => c.claim_id_a === claimId || c.claim_id_b === claimId)
        .map((c) => c.explanation)
        .join("\n\n");
    });
  });
  drawContradictionLines();
}

function drawContradictionLines() {
  const svg = document.getElementById("contradiction-overlay");
  const panel = document.getElementById("clue-board-panel");
  const board = document.getElementById("clue-board");
  svg.innerHTML = ""; // cheap full redraw each time - avoids diffing
  if (contradictions.length === 0) return;

  const panelRect = panel.getBoundingClientRect();
  const originX = panelRect.left + panel.clientLeft;
  const originY = panelRect.top + panel.clientTop;

  contradictions.forEach((con) => {
    const cardA = board.querySelector(`[data-claim-id="${CSS.escape(String(con.claim_id_a))}"]`);
    const cardB = board.querySelector(`[data-claim-id="${CSS.escape(String(con.claim_id_b))}"]`);
    if (!cardA || !cardB) return; // graceful skip if either claim isn't rendered yet

    const rectA = cardA.getBoundingClientRect();
    const rectB = cardB.getBoundingClientRect();

    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("x1", rectA.left + rectA.width / 2 - originX);
    line.setAttribute("y1", rectA.top + rectA.height / 2 - originY);
    line.setAttribute("x2", rectB.left + rectB.width / 2 - originX);
    line.setAttribute("y2", rectB.top + rectB.height / 2 - originY);
    line.setAttribute("class", "contradiction-line");
    svg.appendChild(line);
  });
}

// Cards start out laid out by the flex container, so removing one from flow
// to drag it would normally reflow the rest. Convert every still-in-flow
// card to a fixed absolute position (matching where it already visually
// sits) before that happens, so picking one up never moves the others.
function freezeBoardLayout(board, container) {
  const containerRect = container.getBoundingClientRect();
  // Pulling cards out of the flex flow would let the board shrink to fit
  // whatever's left in flow — lock in its current height first.
  container.style.minHeight = `${containerRect.height}px`;

  const paddingBoxLeft = containerRect.left + container.clientLeft;
  const paddingBoxTop = containerRect.top + container.clientTop;

  // Read every still-in-flow card's rect BEFORE changing any of them —
  // freezing one card reflows the rest, so reading and mutating in the same
  // pass would capture already-shifted positions for the cards after it.
  const toFreeze = [...board.querySelectorAll(".claim-card")]
    .filter((el) => el.style.position !== "absolute")
    .map((el) => ({ el, rect: el.getBoundingClientRect() }));

  toFreeze.forEach(({ el, rect }) => {
    el.style.position = "absolute";
    el.style.left = `${rect.left - paddingBoxLeft}px`;
    el.style.top = `${rect.top - paddingBoxTop}px`;
    el.style.margin = "0";
  });
}

function makePinDraggable(card, board, container) {
  card.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    freezeBoardLayout(board, container);

    const startLeft = parseFloat(card.style.left) || 0;
    const startTop = parseFloat(card.style.top) || 0;

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
      drawContradictionLines();
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

async function resetCase() {
  const difficulty = document.getElementById("difficulty-select").value;
  await fetch(`${API_BASE}/reset`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, difficulty }),
  });
  Object.keys(chatLogsBySuspect).forEach((id) => delete chatLogsBySuspect[id]);
  document.getElementById("chat-panel").classList.add("hidden");
  document.getElementById("reveal-modal").classList.add("hidden");
  selectedSuspectId = null;
  await loadClues();
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
document.getElementById("difficulty-select").addEventListener("change", resetCase);
document.getElementById("reveal-close").addEventListener("click", () => {
  document.getElementById("reveal-modal").classList.add("hidden");
});
window.addEventListener("resize", drawContradictionLines);

loadCase();
loadClues();

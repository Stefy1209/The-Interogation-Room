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

async function loadCase() {
  const res = await fetch(`${API_BASE}/case`);
  const data = await res.json();
  suspects = data.suspects;

  document.getElementById("case-title").textContent =
    `${data.title} — missing: ${data.missing_item}`;

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
  document.getElementById("chat-log").innerHTML = "";
}

function appendChatLine(cls, text) {
  const log = document.getElementById("chat-log");
  const line = document.createElement("div");
  line.className = `chat-msg ${cls}`;
  line.textContent = text;
  log.appendChild(line);
  log.scrollTop = log.scrollHeight;
}

async function sendMessage(message) {
  if (!selectedSuspectId) return;
  appendChatLine("player", `You: ${message}`);

  const res = await fetch(`${API_BASE}/suspects/${selectedSuspectId}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, message }),
  });
  const data = await res.json();
  appendChatLine("suspect", `${data.suspect_id}: ${data.reply}`);
  await loadClues();
}

async function loadClues() {
  const res = await fetch(`${API_BASE}/clues?session_id=${encodeURIComponent(sessionId)}`);
  const data = await res.json();
  const board = document.getElementById("clue-board");
  board.innerHTML = "";
  if (data.claims.length === 0) {
    board.innerHTML = "<p>No clues pinned yet — ask a suspect something.</p>";
    return;
  }
  data.claims.forEach((c) => {
    const card = document.createElement("div");
    card.className = "claim-card";
    card.textContent = `[${c.speaker_id}] ${c.statement}`;
    board.appendChild(card);
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
  await fetch(`${API_BASE}/reset`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  });
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
document.getElementById("reveal-close").addEventListener("click", () => {
  document.getElementById("reveal-modal").classList.add("hidden");
});

loadCase();
loadClues();

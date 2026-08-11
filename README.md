# The Interrogation Room

Short Game using Chats — an AI whodunit. Four AI suspects, one goodie bag
missing, one liar. See `PLAN.md` for the full team plan, lane split, and API
contracts.

## Setup

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp ../.env.example ../.env    # then fill in OPENAI_API_KEY
```

## Run

```bash
cd backend
uvicorn main:app --reload --port 8000
```

Open http://localhost:8000 — the frontend is served as static files from the
same server, and calls `/api/*` on the same origin.

By default `USE_MOCK=true`, so the whole loop (chat, clue board, accusation,
reveal) works with zero OpenAI calls — useful for building the UI and testing
the flow without burning the shared API budget. Set `USE_MOCK=false` in `.env`
once real suspect chat and clue extraction are ready to test.

## Useful scripts (owned by the game master, but anyone can run them)

```bash
cd backend
python case_validator.py     # checks case.json for schema + game-design problems
python playtest.py           # scripts canned interrogations against a running server
python scoring.py            # quick sanity check of the scoring function
```

## Project structure

```
backend/
  main.py              # FastAPI app, mounts routers + serves the frontend
  case.json            # the case content (starter: "The Case of the Missing Goodie Bag")
  models.py            # shared pydantic contracts — the source of truth for API shapes
  case_loader.py        # loads + validates case.json once at startup
  prompts.py           # system-prompt assembly per suspect
  state.py             # in-memory session store
  scoring.py           # scoring/rank function
  case_validator.py    # CLI: validates case.json
  playtest.py          # CLI: scripted interrogation regression test
  routes/
    case.py            # GET /api/case (public case info for the frontend)
    suspects.py        # POST /api/suspects/{id}/chat
    clues.py           # GET /api/clues, claim extraction
    accusation.py       # POST /api/accuse
    session.py          # POST /api/reset
frontend/
  index.html
  app.js
  style.css
PLAN.md                # full team plan: lanes, timeline, API contracts, git workflow
.env.example
```

## Ground rules

- `.env` holds the real API key and is never committed (already in `.gitignore`).
- Everyone should be able to explain any function a mentor points at.
- Must-haves before stretch goals — see `PLAN.md`.

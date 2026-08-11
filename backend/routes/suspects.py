"""
Owned by A. Per-suspect chat endpoint: assembles the system prompt, calls the
model (or a mock reply), stores conversation history per session, and hands
the reply off to B's clue-extraction pass.
"""
import os

from fastapi import APIRouter, HTTPException

import case_loader
from models import ChatRequest, ChatResponse
from prompts import build_system_prompt
from routes.clues import record_claims_from_reply
from state import get_session

router = APIRouter()

USE_MOCK = os.getenv("USE_MOCK", "true").lower() == "true"

# Canned replies so C and B can build the whole loop before real API calls are wired in.
MOCK_REPLIES = {
    "suspect_1": "I set the bags out at 9am sharp and did a headcount at 10:30 — every intern bag was accounted for.",
    "suspect_2": "I was at my desk all afternoon, I barely even got up!",
    "suspect_3": "I moved a box of leftover bags into the storage closet around 11, just to clear the table. Didn't touch anything after that.",
    "suspect_4": "I saw Priya near the closet around 2pm, she had a bag with her, but I didn't think much of it.",
}


@router.post("/suspects/{suspect_id}/chat", response_model=ChatResponse)
def chat_with_suspect(suspect_id: str, req: ChatRequest) -> ChatResponse:
    case = case_loader.CASE
    suspect = next((s for s in case.suspects if s.id == suspect_id), None)
    if suspect is None:
        raise HTTPException(status_code=404, detail=f"Unknown suspect '{suspect_id}'")

    session = get_session(req.session_id)
    history = session.chat_histories.setdefault(suspect_id, [])
    history.append({"role": "user", "content": req.message})
    session.questions_asked += 1

    if USE_MOCK:
        reply = MOCK_REPLIES.get(suspect_id, "...")
    else:
        reply = _call_openai(suspect, case, history)

    history.append({"role": "assistant", "content": reply})
    turn_index = len(history) // 2

    record_claims_from_reply(req.session_id, suspect_id, reply, turn_index)

    return ChatResponse(suspect_id=suspect_id, reply=reply, turn_index=turn_index)


def _call_openai(suspect, case, history) -> str:
    from openai import OpenAI

    client = OpenAI()
    system_prompt = build_system_prompt(suspect, case)
    messages = [{"role": "system", "content": system_prompt}] + history
    response = client.chat.completions.create(
        model="gpt-5" if suspect.is_culprit else "gpt-5-mini",
        messages=messages,
    )
    return response.choices[0].message.content

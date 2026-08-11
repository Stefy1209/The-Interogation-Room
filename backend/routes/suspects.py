"""
Owned by A. Per-suspect chat endpoint: assembles the system prompt, calls the
model, stores conversation history per session, and hands the reply off to
B's clue-extraction pass.
"""
from fastapi import APIRouter, HTTPException

import case_loader
from models import ChatRequest, ChatResponse
from prompts import build_system_prompt
from routes.clues import record_claims_from_reply
from state import get_session

router = APIRouter()


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

    reply = _call_openai(suspect, case, history, session.difficulty)

    history.append({"role": "assistant", "content": reply})
    turn_index = len(history) // 2

    record_claims_from_reply(req.session_id, suspect_id, reply, turn_index)

    return ChatResponse(suspect_id=suspect_id, reply=reply, turn_index=turn_index)


def _call_openai(suspect, case, history, difficulty: str) -> str:
    from openai import OpenAI

    client = OpenAI()
    system_prompt = build_system_prompt(suspect, case, difficulty)
    messages = [{"role": "system", "content": system_prompt}] + history
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
    )
    return response.choices[0].message.content

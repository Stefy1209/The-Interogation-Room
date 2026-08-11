"""
Owned by A. Reset endpoint — wipes chat histories and the clue board for a
session so the case can be replayed cleanly during the demo.
"""
from fastapi import APIRouter

from models import ResetRequest
from state import reset_session

router = APIRouter()


@router.post("/reset")
def reset(req: ResetRequest) -> dict:
    reset_session(req.session_id, req.difficulty)
    return {"status": "ok"}

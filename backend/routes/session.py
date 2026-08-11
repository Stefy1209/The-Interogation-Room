"""
Owned by A. Two reset flavors:
- POST /api/reset     — replay the SAME case: wipes chat histories + clue board.
- POST /api/new-game  — generates a brand new case (new suspects, new
  solution) via case_generator, then wipes state the same way /api/reset does.
"""
import os

from fastapi import APIRouter

import case_loader
from case_generator import generate_case
from models import ResetRequest
from state import reset_session

router = APIRouter()

USE_MOCK = os.getenv("USE_MOCK", "true").lower() == "true"


@router.post("/reset")
def reset(req: ResetRequest) -> dict:
    reset_session(req.session_id, req.difficulty)
    return {"status": "ok"}


@router.post("/new-game")
def new_game(req: ResetRequest) -> dict:
    new_case = generate_case(use_mock=USE_MOCK)
    case_loader.reload_case(new_case)
    reset_session(req.session_id)
    return {"status": "ok"}

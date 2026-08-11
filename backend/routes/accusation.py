"""
Owned by A (or B). Verdict + reveal endpoint. Scoring itself lives in
scoring.py (owned by D) and is imported here rather than reimplemented.
"""
from fastapi import APIRouter

import case_loader
from models import AccuseRequest, AccuseResponse, ScoreResult
from scoring import compute_score
from state import get_session

router = APIRouter()


@router.post("/accuse", response_model=AccuseResponse)
def accuse(req: AccuseRequest) -> AccuseResponse:
    case = case_loader.CASE
    session = get_session(req.session_id)

    correct = req.accused_id == case.solution.culprit_id
    contradictions_found = len(session.contradictions)

    score = compute_score(
        questions_asked=session.questions_asked,
        contradictions_found=contradictions_found,
        correct=correct,
    )

    return AccuseResponse(
        correct=correct,
        actual_culprit_id=case.solution.culprit_id,
        true_story=case.solution.true_story,
        score=ScoreResult(**score),
    )

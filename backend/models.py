"""
Pydantic models mirroring the JSON contracts in the team plan (PLAN.md §2).
Treat these as the frozen shared contract between lanes A, B, C, D — if a
shape here needs to change, re-sync with the team before editing it.
"""
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# --- Case file (owned by D content-wise, A + D agree on structure) ---------

class TimelineEvent(BaseModel):
    time: str
    event: str


class Solution(BaseModel):
    culprit_id: str
    motive: str
    true_story: str


class Suspect(BaseModel):
    id: str
    name: str
    public_persona: str
    alibi: str
    private_knowledge: List[str] = Field(default_factory=list)
    relationships: Dict[str, str] = Field(default_factory=dict)
    is_culprit: bool = False
    behavior_rules: str


class CaseFile(BaseModel):
    case_id: str
    title: str
    missing_item: str
    setting: str
    timeline: List[TimelineEvent]
    shared_facts: List[str]
    solution: Solution
    suspects: List[Suspect]


# --- Suspect chat (owned by A) ----------------------------------------------

class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    suspect_id: str
    reply: str
    turn_index: int


# --- Clue board (owned by B) ------------------------------------------------

class Claim(BaseModel):
    id: Optional[str] = None
    speaker_id: str
    statement: str
    about_time: Optional[str] = None
    about_location: Optional[str] = None
    implicates: List[str] = Field(default_factory=list)
    claim_type: Literal["alibi", "observation", "accusation", "denial"]
    turn_index: Optional[int] = None
    created_at: Optional[str] = None


class ClaimsExtraction(BaseModel):
    claims: List[Claim]


class Contradiction(BaseModel):
    id: Optional[str] = None
    claim_id_a: str
    claim_id_b: str
    speaker_a: str
    speaker_b: str
    explanation: str
    created_at: Optional[str] = None


class ContradictionCandidate(BaseModel):
    claim_id_a: str
    explanation: str


class ContradictionsExtraction(BaseModel):
    contradictions: List[ContradictionCandidate]


class ClueBoardResponse(BaseModel):
    claims: List[Claim]
    contradictions: List[Contradiction] = Field(default_factory=list)


# --- Accusation & reveal (owned by A, scoring by D) -------------------------

class AccuseRequest(BaseModel):
    session_id: str
    accused_id: str
    motive_guess: str


class ScoreResult(BaseModel):
    rank: str
    stars: int
    summary: str


class AccuseResponse(BaseModel):
    correct: bool
    actual_culprit_id: str
    true_story: str
    score: ScoreResult


# --- Session reset -----------------------------------------------------------

class ResetRequest(BaseModel):
    session_id: str

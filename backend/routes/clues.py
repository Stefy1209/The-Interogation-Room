"""
Owned by B. Structured-Outputs claim extraction + the clue board endpoint.
Set USE_MOCK=false (and a real OPENAI_API_KEY) once ready to swap off canned data.
"""
import json
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Query

from models import Claim, ClaimsExtraction, ClueBoardResponse
from state import get_session

router = APIRouter()

USE_MOCK = os.getenv("USE_MOCK", "true").lower() == "true"

CLAIM_SCHEMA = {
    "name": "extract_claims",
    "schema": {
        "type": "object",
        "properties": {
            "claims": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "speaker_id": {"type": "string"},
                        "statement": {"type": "string"},
                        "about_time": {"type": ["string", "null"]},
                        "about_location": {"type": ["string", "null"]},
                        "implicates": {"type": "array", "items": {"type": "string"}},
                        "claim_type": {
                            "type": "string",
                            "enum": ["alibi", "observation", "accusation", "denial"],
                        },
                    },
                    "required": [
                        "speaker_id",
                        "statement",
                        "about_time",
                        "about_location",
                        "implicates",
                        "claim_type",
                    ],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["claims"],
        "additionalProperties": False,
    },
    "strict": True,
}


@router.get("/clues", response_model=ClueBoardResponse)
def get_clues(session_id: str = Query(...)) -> ClueBoardResponse:
    session = get_session(session_id)
    return ClueBoardResponse(claims=session.claims)


def record_claims_from_reply(session_id: str, suspect_id: str, reply: str, turn_index: int) -> None:
    """Called by routes/suspects.py right after a suspect answers."""
    session = get_session(session_id)
    extraction = _mock_extraction(suspect_id, reply) if USE_MOCK else extract_claims(suspect_id, reply)

    for claim in extraction.claims:
        claim.id = f"c{session.next_claim_id}"
        session.next_claim_id += 1
        claim.turn_index = turn_index
        claim.created_at = datetime.now(timezone.utc).isoformat()
        session.claims.append(claim.model_dump())


def _mock_extraction(suspect_id: str, reply: str) -> ClaimsExtraction:
    """Canned extraction so B and C can build without real OpenAI calls (§3 of the plan)."""
    return ClaimsExtraction(
        claims=[
            Claim(
                speaker_id=suspect_id,
                statement=reply,
                about_time=None,
                about_location=None,
                implicates=[],
                claim_type="observation",
            )
        ]
    )


def extract_claims(suspect_id: str, reply: str) -> ClaimsExtraction:
    from openai import OpenAI

    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "Extract factual claims from this suspect's statement as structured "
                    "data. One claim per distinct fact asserted."
                ),
            },
            {"role": "user", "content": f"Suspect '{suspect_id}' said: {reply}"},
        ],
        response_format={"type": "json_schema", "json_schema": CLAIM_SCHEMA},
    )
    data = json.loads(response.choices[0].message.content)
    return ClaimsExtraction(**data)

"""
Compares a newly recorded claim against prior claims from other speakers and
flags contradictions. USE_MOCK mirrors clues.py's flag: a cheap deterministic
heuristic in mock mode, a Structured-Outputs OpenAI call in real mode. Called
from routes/clues.record_claims_from_reply right after a claim is appended
to session.claims.
"""
import json
import os
import re

import case_loader
from models import Claim, Contradiction, ContradictionsExtraction

USE_MOCK = os.getenv("USE_MOCK", "true").lower() == "true"

CONTRADICTION_SCHEMA = {
    "name": "detect_contradictions",
    "schema": {
        "type": "object",
        "properties": {
            "contradictions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "claim_id_a": {"type": "string"},
                        "explanation": {"type": "string"},
                    },
                    "required": ["claim_id_a", "explanation"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["contradictions"],
        "additionalProperties": False,
    },
    "strict": True,
}

_STOPWORDS = {
    "i", "me", "my", "you", "your", "he", "she", "they", "them", "it", "we",
    "was", "were", "is", "am", "are", "be", "been", "being",
    "a", "an", "the", "and", "or", "but", "if", "of", "to", "in", "on", "at",
    "for", "with", "about", "around", "near", "over", "into", "up", "down",
    "did", "do", "does", "didn't", "don't", "doesn't", "not",
    "just", "even", "all", "afternoon", "morning", "day", "time",
    "had", "have", "has", "got", "get", "barely", "think", "thought",
    "much", "so", "her", "his", "him",
}


def detect_contradictions(new_claim: Claim, prior_claims: list[dict]) -> list[Contradiction]:
    """prior_claims are session.claims dicts from OTHER speakers, snapshotted
    before new_claim was appended. Returned Contradiction objects still need
    id/created_at filled in by the caller."""
    if not prior_claims:
        return []
    return _mock_detect(new_claim, prior_claims) if USE_MOCK else _llm_detect(new_claim, prior_claims)


def _significant_tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z]+", text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 2}


def _mock_detect(new_claim: Claim, prior_claims: list[dict]) -> list[Contradiction]:
    suspects_by_id = {s.id: s for s in case_loader.CASE.suspects}
    new_lower = new_claim.statement.lower()
    new_tokens = _significant_tokens(new_claim.statement)
    results = []

    for prior in prior_claims:
        prior_speaker = suspects_by_id.get(prior["speaker_id"])
        if prior_speaker is None:
            continue

        mentioned = any(
            tok.lower() in new_lower for tok in prior_speaker.name.split()
        )
        if not mentioned:
            continue

        overlap = new_tokens & _significant_tokens(prior["statement"])
        if len(overlap) <= 1:
            results.append(
                Contradiction(
                    claim_id_a=prior["id"],
                    claim_id_b=new_claim.id,
                    speaker_a=prior["speaker_id"],
                    speaker_b=new_claim.speaker_id,
                    explanation=(
                        f"{new_claim.speaker_id} mentions {prior_speaker.name}, but their "
                        f"account shares no common detail with {prior_speaker.name}'s own "
                        "statement — possible conflicting whereabouts."
                    ),
                )
            )
    return results


def _llm_detect(new_claim: Claim, prior_claims: list[dict]) -> list[Contradiction]:
    from openai import OpenAI

    client = OpenAI()
    prior_text = "\n".join(
        f"[{c['id']}] {c['speaker_id']}: {c['statement']}" for c in prior_claims
    )
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are comparing suspect statements in a murder-mystery "
                    "interrogation game. Given one new claim and a list of prior "
                    "claims made by OTHER suspects, identify which prior claims it "
                    "directly contradicts (conflicting facts about time, location, "
                    "or who did what — not just different topics). Return only "
                    "genuine contradictions, referencing prior claims by their id."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"New claim [{new_claim.id}] from {new_claim.speaker_id}: "
                    f"{new_claim.statement}\n\nPrior claims:\n{prior_text}"
                ),
            },
        ],
        response_format={"type": "json_schema", "json_schema": CONTRADICTION_SCHEMA},
    )
    data = json.loads(response.choices[0].message.content)
    extraction = ContradictionsExtraction(**data)

    id_to_claim = {c["id"]: c for c in prior_claims}
    results = []
    for candidate in extraction.contradictions:
        prior = id_to_claim.get(candidate.claim_id_a)
        if prior is None:
            continue  # guard against a hallucinated id
        results.append(
            Contradiction(
                claim_id_a=candidate.claim_id_a,
                claim_id_b=new_claim.id,
                speaker_a=prior["speaker_id"],
                speaker_b=new_claim.speaker_id,
                explanation=candidate.explanation,
            )
        )
    return results

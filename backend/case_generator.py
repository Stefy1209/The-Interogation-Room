"""
Generates a brand new CaseFile for each /api/reset call (routes/session.py).
Real mode calls OpenAI with Structured Outputs; mock mode rotates between the
fixtures below so the "new game" loop is demoable with zero API spend,
consistent with the rest of the app's USE_MOCK convention.
"""
import json
import os
import random

from openai import OpenAI

from case_validator import validate_case
from models import CaseFile

MAX_ATTEMPTS = 3

# Relationships are a free-form {suspect_id: note} map in models.Suspect, but
# OpenAI's strict Structured Outputs mode can't express a dict with unknown
# keys — so the model emits a list of {suspect_id, note} objects instead, and
# _parse_generated() below converts that list back into the dict shape.
CASE_SCHEMA = {
    "name": "generate_case",
    "schema": {
        "type": "object",
        "properties": {
            "case_id": {"type": "string"},
            "title": {"type": "string"},
            "missing_item": {"type": "string"},
            "setting": {"type": "string"},
            "timeline": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "time": {"type": "string"},
                        "event": {"type": "string"},
                    },
                    "required": ["time", "event"],
                    "additionalProperties": False,
                },
            },
            "shared_facts": {"type": "array", "items": {"type": "string"}},
            "solution": {
                "type": "object",
                "properties": {
                    "culprit_id": {"type": "string"},
                    "motive": {"type": "string"},
                    "true_story": {"type": "string"},
                },
                "required": ["culprit_id", "motive", "true_story"],
                "additionalProperties": False,
            },
            "suspects": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "name": {"type": "string"},
                        "gender": {"type": "string", "enum": ["female", "male"]},
                        "public_persona": {"type": "string"},
                        "alibi": {"type": "string"},
                        "private_knowledge": {"type": "array", "items": {"type": "string"}},
                        "relationships": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "suspect_id": {"type": "string"},
                                    "note": {"type": "string"},
                                },
                                "required": ["suspect_id", "note"],
                                "additionalProperties": False,
                            },
                        },
                        "is_culprit": {"type": "boolean"},
                        "behavior_rules": {"type": "string"},
                    },
                    "required": [
                        "id", "name", "gender", "public_persona", "alibi",
                        "private_knowledge", "relationships", "is_culprit", "behavior_rules",
                    ],
                    "additionalProperties": False,
                },
            },
        },
        "required": [
            "case_id", "title", "missing_item", "setting", "timeline",
            "shared_facts", "solution", "suspects",
        ],
        "additionalProperties": False,
    },
    "strict": True,
}

GENERATION_INSTRUCTIONS = """
Invent a brand new short "whodunit" case for an office-themed interrogation
game, in the same style as this example: something ordinary goes missing or
gets broken/ruined around a workplace, four suspects, one of them did it by
accident or a small lapse of judgement (not malice), and is now hiding it out
of embarrassment rather than any real villainy.

Hard requirements:
- Exactly 4 suspects, each with a unique id "suspect_1".."suspect_4".
- Exactly one suspect has is_culprit=true, and solution.culprit_id must equal
  that suspect's id.
- Every suspect needs a "gender" of exactly "female" or "male".
- Every innocent suspect needs at least one private_knowledge fact that isn't
  in their public alibi.
- At least one OTHER (non-culprit) suspect's alibi or private_knowledge must
  mention the culprit by name or id, so the case is solvable by
  cross-referencing testimony, not just guessing.
- Never mention the solution's true_story or motive inside any suspect's
  public_persona, alibi, or private_knowledge except the culprit's own.
- relationships is a list of {suspect_id, note} entries, one per OTHER
  suspect in the case (not itself).
""".strip()


def generate_case(use_mock: bool) -> CaseFile:
    if use_mock:
        return _generate_mock_case()

    last_problems = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        raw = _call_openai(feedback=last_problems)
        case = _parse_generated(raw)
        problems = validate_case(case)
        if not problems:
            return case
        last_problems = problems

    raise RuntimeError(
        f"Could not generate a valid case after {MAX_ATTEMPTS} attempts: {last_problems}"
    )


def _call_openai(feedback: list) -> dict:
    client = OpenAI()
    user_message = GENERATION_INSTRUCTIONS
    if feedback:
        user_message += (
            "\n\nYour previous attempt had these problems — fix all of them:\n"
            + "\n".join(f"- {p}" for p in feedback)
        )
    response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[{"role": "user", "content": user_message}],
        response_format={"type": "json_schema", "json_schema": CASE_SCHEMA},
    )
    return json.loads(response.choices[0].message.content)


def _parse_generated(raw: dict) -> CaseFile:
    data = dict(raw)
    data["suspects"] = [
        {**s, "relationships": {r["suspect_id"]: r["note"] for r in s["relationships"]}}
        for s in data["suspects"]
    ]
    return CaseFile(**data)


def _generate_mock_case() -> CaseFile:
    fixture = random.choice(_MOCK_FIXTURES)
    return CaseFile(**fixture)


_MOCK_FIXTURES = [
    {
        "case_id": "missing-team-trophy",
        "title": "The Case of the Missing Team Trophy",
        "missing_item": "The 'Fantasy League Champion' trophy from the break room shelf",
        "setting": "The office fantasy-football trophy, proudly displayed on the break room shelf all season, vanished days before the league's final photo op.",
        "timeline": [
            {"time": "Mon 09:00", "event": "Sam dusts the shelf and confirms the trophy is in place."},
            {"time": "Wed 13:00", "event": "Devon sees Casey near the break room carrying something wrapped in a jacket."},
            {"time": "Fri 08:00", "event": "Sam goes to prep the trophy for the league photo and finds it gone."},
        ],
        "shared_facts": [
            "The fantasy-football trophy has gone missing from the break room shelf.",
            "It was last confirmed in place Monday morning.",
            "Three people were regularly in and out of the break room this week: Sam, Devon, and Casey.",
        ],
        "solution": {
            "culprit_id": "suspect_3",
            "motive": "Casey borrowed the trophy Wednesday to stage a joke photo for the league group chat, knocked it off a table, cracked its base, and has been too embarrassed to admit it while quietly trying to figure out how to fix or replace it.",
            "true_story": "Casey took the trophy to their desk Wednesday afternoon to set up a prank photo, but it slipped while being repositioned and the base cracked. Casey hid it in a desk drawer, meaning to get it repaired before anyone noticed, and has been dodging questions out of embarrassment ever since.",
        },
        "suspects": [
            {
                "id": "suspect_1",
                "name": "Sam Rivera",
                "gender": "female",
                "public_persona": "League commissioner. Organized, a little possessive of 'her' trophy, quick to worry she'll be blamed for losing it.",
                "alibi": "Dusted and confirmed the trophy Monday morning, then didn't check the shelf again until Friday.",
                "private_knowledge": [
                    "Noticed a faint scuff mark on the shelf edge Wednesday afternoon but didn't think much of it at the time.",
                ],
                "relationships": {
                    "suspect_2": "Trusts Devon, they run the league together.",
                    "suspect_3": "Likes Casey but thinks they're a bit clumsy with office stuff.",
                },
                "is_culprit": False,
                "behavior_rules": "Answer truthfully about the shelf and timeline. Get anxious and slightly scattered if asked whether she checked on it mid-week.",
            },
            {
                "id": "suspect_2",
                "name": "Devon Park",
                "gender": "male",
                "public_persona": "Office prankster. Easygoing, finds the whole situation funny, not great with exact times.",
                "alibi": "Was around the office all week, nothing unusual to report.",
                "private_knowledge": [
                    "Saw Casey near the break room Wednesday around 1pm carrying something bulky wrapped in a jacket, but assumed it was nothing.",
                ],
                "relationships": {
                    "suspect_1": "Co-runs the league with Sam, generally easygoing about it.",
                    "suspect_3": "Friendly with Casey, doesn't suspect them of anything.",
                },
                "is_culprit": False,
                "behavior_rules": "Relaxed and cooperative. Will mention seeing Casey with something wrapped up if asked about the break room or Wednesday, without realizing it matters.",
            },
            {
                "id": "suspect_3",
                "name": "Casey Nolan",
                "gender": "male",
                "public_persona": "Newer team member. Eager to fit in, gets visibly nervous under direct questioning.",
                "alibi": "Claims to have been at their desk all week and never touched the trophy.",
                "private_knowledge": [
                    "Borrowed the trophy Wednesday afternoon to stage a joke photo for the league chat.",
                    "The trophy's base cracked when it slipped off a table during the photo attempt.",
                    "Hid the cracked trophy in the bottom desk drawer, planning to quietly get it repaired.",
                ],
                "relationships": {
                    "suspect_1": "Wants Sam's approval, feels guilty for worrying her.",
                    "suspect_2": "Considers Devon a friend, hasn't told him what happened.",
                },
                "is_culprit": True,
                "behavior_rules": "Deny touching the trophy and stay visibly nervous. If confronted with Devon's sighting, get flustered and deflect once more before admitting to borrowing it if pressed with specific evidence (the sighting AND the timing).",
            },
        ],
    },
    {
        "case_id": "missing-signed-poster",
        "title": "The Case of the Missing Signed Poster",
        "missing_item": "The signed conference poster from the lobby wall",
        "setting": "A poster signed by every speaker at last year's company conference hung proudly in the lobby — until it disappeared off the wall this week.",
        "timeline": [
            {"time": "Mon 08:00", "event": "Morgan confirms the poster is on the wall before the morning rush."},
            {"time": "Tue 15:00", "event": "Nadia sees Theo near the lobby wall holding a coffee cup right next to the poster."},
            {"time": "Wed 09:00", "event": "Morgan notices the poster is gone and the wall hook is empty."},
        ],
        "shared_facts": [
            "The signed conference poster is missing from the lobby wall.",
            "It was confirmed in place Monday morning.",
            "Three people pass through the lobby daily: Morgan, Theo, and Nadia.",
        ],
        "solution": {
            "culprit_id": "suspect_2",
            "motive": "Theo spilled coffee across the poster Tuesday afternoon, panicked about ruining something everyone loved, and took it down to try to clean and dry it out before anyone noticed the stain.",
            "true_story": "Theo bumped the lobby table Tuesday afternoon and splashed coffee across the bottom of the poster. Afraid of the reaction, Theo unpinned it and took it to a supply closet to try to blot it dry, intending to sneak it back before anyone looked closely — but the stain didn't come out, and Theo has been avoiding the topic since.",
        },
        "suspects": [
            {
                "id": "suspect_1",
                "name": "Morgan Yu",
                "gender": "female",
                "public_persona": "Office manager. Proud of the lobby display, mildly protective of it, quick to notice when things are out of place.",
                "alibi": "Confirmed the poster was up Monday morning, didn't pass through the lobby again until Wednesday.",
                "private_knowledge": [
                    "Noticed the wall hook was slightly bent when the poster went missing, as if it had been removed in a hurry.",
                ],
                "relationships": {
                    "suspect_2": "Friendly with Theo, wouldn't have suspected him.",
                    "suspect_3": "Trusts Nadia's attention to detail.",
                },
                "is_culprit": False,
                "behavior_rules": "Answer truthfully about the wall and hook. Get a little indignant if asked whether she was careless with the display.",
            },
            {
                "id": "suspect_2",
                "name": "Theo Brandt",
                "gender": "male",
                "public_persona": "Sales rep who's always got a coffee in hand. Friendly but visibly anxious when the poster comes up.",
                "alibi": "Was at his desk most of Tuesday, doesn't remember being near the lobby wall.",
                "private_knowledge": [
                    "Bumped the lobby table Tuesday afternoon and splashed coffee across the bottom of the poster.",
                    "Took the poster down and brought it to the supply closet to try to dry and clean the stain.",
                    "The stain didn't come out, and the poster is still folded inside a supply closet box.",
                ],
                "relationships": {
                    "suspect_1": "Likes Morgan, feels bad about the mess he caused her.",
                    "suspect_3": "Doesn't realize Nadia saw him near the wall Tuesday.",
                },
                "is_culprit": True,
                "behavior_rules": "Deny being near the lobby wall Tuesday and stay visibly anxious. If confronted with Nadia's sighting, get flustered and deflect once more before admitting to the coffee spill if pressed with specific evidence (the sighting AND the timing).",
            },
            {
                "id": "suspect_3",
                "name": "Nadia Ilves",
                "gender": "female",
                "public_persona": "Designer who helped pick the poster's frame. Observant, a little blunt, not one to gossip without being asked directly.",
                "alibi": "Passed through the lobby Tuesday afternoon on the way to a meeting, nothing seemed off at the time.",
                "private_knowledge": [
                    "Saw Theo standing right by the poster with a coffee cup around 3pm Tuesday, but didn't think anything of it.",
                ],
                "relationships": {
                    "suspect_1": "Respects Morgan's care for the lobby display.",
                    "suspect_2": "Friendly with Theo, no reason to suspect him.",
                },
                "is_culprit": False,
                "behavior_rules": "Blunt and cooperative. Will mention seeing Theo near the wall with coffee if asked directly about Tuesday afternoon, without realizing it's significant.",
            },
        ],
    },
]


if __name__ == "__main__":
    # Quick manual check: python case_generator.py [--mock]
    import sys

    mock = "--mock" in sys.argv
    case = generate_case(use_mock=mock)
    print(f"Generated: {case.title} (culprit: {case.solution.culprit_id})")

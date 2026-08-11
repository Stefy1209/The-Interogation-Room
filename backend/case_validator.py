#!/usr/bin/env python3
"""
Owned by D. Run this all day while writing/editing case.json:

    python case_validator.py            # validates ./case.json
    python case_validator.py path/to/other_case.json

Checks schema compliance plus the game-design invariants that keep the case
solvable-but-not-obvious: exactly one culprit, the solution matches that
culprit, no innocent suspect is a dead end, and no relationship points at a
suspect that doesn't exist.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pydantic import ValidationError

from models import CaseFile


def validate(path: str) -> list:
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    try:
        case = CaseFile(**raw)
    except ValidationError as e:
        return [f"Schema error: {line}" for line in str(e).splitlines()]

    return validate_case(case)


def validate_case(case: CaseFile) -> list:
    """Same checks as validate(), but on an already-parsed CaseFile — no disk I/O.
    Used by case_generator.py to check a freshly generated case before it's written."""
    problems = []

    culprits = [s for s in case.suspects if s.is_culprit]
    if len(culprits) != 1:
        problems.append(f"Expected exactly 1 suspect with is_culprit=true, found {len(culprits)}.")

    suspect_ids = {s.id for s in case.suspects}
    if case.solution.culprit_id not in suspect_ids:
        problems.append("solution.culprit_id does not match any suspect id.")
    elif culprits and case.solution.culprit_id != culprits[0].id:
        problems.append("solution.culprit_id does not match the suspect flagged is_culprit=true.")

    if len(case.suspects) < 2:
        problems.append("Need at least 2 suspects for the game to make sense (brief calls for 4).")

    for s in case.suspects:
        if not s.is_culprit and not s.private_knowledge:
            problems.append(
                f"{s.id} ({s.name}) is innocent but has no private_knowledge — "
                "nothing distinguishes their testimony."
            )
        for other_id in s.relationships:
            if other_id not in suspect_ids:
                problems.append(f"{s.id} has a relationship entry for unknown suspect '{other_id}'.")
            if other_id == s.id:
                problems.append(f"{s.id} has a relationship entry pointing at itself.")

    # Very rough solvability heuristic: at least one OTHER suspect's private
    # knowledge or alibi should reference the culprit by name or id, giving
    # players a cross-reference to catch them on.
    if culprits:
        culprit = culprits[0]
        culprit_name_tokens = culprit.name.split()  # match on first/last name, not just full name
        mentions = 0
        for s in case.suspects:
            if s.id == culprit.id:
                continue
            haystack = " ".join(s.private_knowledge) + " " + s.alibi
            if culprit.id in haystack or any(tok in haystack for tok in culprit_name_tokens):
                mentions += 1
        if mentions == 0:
            problems.append(
                f"No other suspect's alibi/private_knowledge mentions the culprit "
                f"({culprit.name}) — the case may be unsolvable without a lucky guess."
            )

    return problems


if __name__ == "__main__":
    default_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "case.json")
    path = sys.argv[1] if len(sys.argv) > 1 else default_path
    found = validate(path)
    if not found:
        print(f"case OK: {path} looks valid.")
    else:
        print(f"case INVALID: {len(found)} problem(s) found in {path}:")
        for p in found:
            print(f"  - {p}")
        sys.exit(1)

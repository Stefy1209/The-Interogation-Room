"""
Owned by D. A pure function — no FastAPI, no OpenAI, no session-state import —
so it can be written and unit-tested completely independently of everyone
else's lanes. A's /api/accuse route just imports compute_score and calls it.

Tune the thresholds/wording below while playtesting; this is real game design.
"""


def compute_score(questions_asked: int, contradictions_found: int, correct: bool) -> dict:
    """
    Returns e.g. {"rank": "Sharp-eyed Detective", "stars": 2, "summary": "..."}
    """
    if not correct:
        return {
            "rank": "Wrong Suspect",
            "stars": 0,
            "summary": "You accused the wrong person — the real culprit is still out there.",
        }

    if questions_asked <= 6 and contradictions_found >= 1:
        rank, stars = "Master Detective", 3
    elif questions_asked <= 12:
        rank, stars = "Sharp-eyed Detective", 2
    else:
        rank, stars = "Case Closed (Eventually)", 1

    return {
        "rank": rank,
        "stars": stars,
        "summary": (
            f"Solved it in {questions_asked} question(s) with "
            f"{contradictions_found} contradiction(s) caught."
        ),
    }


if __name__ == "__main__":
    # Quick manual sanity check: python scoring.py
    for qa, cf, ok in [(4, 2, True), (10, 0, True), (20, 0, True), (5, 1, False)]:
        print(qa, cf, ok, "->", compute_score(qa, cf, ok))

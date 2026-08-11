"""
Loads case.json once at import time and validates it against models.CaseFile.
Every route imports `CASE` from here rather than re-reading the file.
"""
import json
import os

from models import CaseFile

_CASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "case.json")

with open(_CASE_PATH, encoding="utf-8") as f:
    CASE: CaseFile = CaseFile(**json.load(f))


def reload_case(case: CaseFile) -> None:
    """Writes `case` to case.json (atomically) and swaps it in as the live CASE.
    Routes read `case_loader.CASE` fresh on every request, so this takes effect
    immediately with no server restart needed."""
    global CASE

    tmp_path = _CASE_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(case.model_dump_json(indent=2))
    os.replace(tmp_path, _CASE_PATH)

    CASE = case

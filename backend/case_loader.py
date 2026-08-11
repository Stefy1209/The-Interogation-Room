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

"""
Owned by A. Public case info for the frontend to render suspect cards —
deliberately excludes `solution` and every suspect's `private_knowledge`.
"""
from fastapi import APIRouter

import case_loader

router = APIRouter()


@router.get("/case")
def get_case_public() -> dict:
    case = case_loader.CASE
    return {
        "case_id": case.case_id,
        "title": case.title,
        "missing_item": case.missing_item,
        "setting": case.setting,
        "shared_facts": case.shared_facts,
        "suspects": [
            {"id": s.id, "name": s.name, "public_persona": s.public_persona}
            for s in case.suspects
        ],
    }

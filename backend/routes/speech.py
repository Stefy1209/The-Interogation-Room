"""
Text-to-speech for suspect replies via OpenAI's audio API. Voice choice is
driven entirely by case.json's per-suspect `gender` field, so this works for
any case (not just the current one) without hardcoding suspect names.

Each suspect gets a fixed voice, assigned once at startup by cycling through
a gender-appropriate pool — same gender suspects still sound distinct from
each other, and the same suspect always sounds the same across a session.
"""
from itertools import cycle

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

import case_loader

router = APIRouter()

FEMALE_VOICES = ["nova", "shimmer", "alloy", "coral", "sage"]
MALE_VOICES = ["onyx", "echo", "fable", "ash", "ballad", "verse"]


def _assign_voices() -> dict:
    pools = {"female": cycle(FEMALE_VOICES), "male": cycle(MALE_VOICES)}
    return {suspect.id: next(pools[suspect.gender]) for suspect in case_loader.CASE.suspects}


SUSPECT_VOICES = _assign_voices()


class SpeechRequest(BaseModel):
    text: str


@router.post("/suspects/{suspect_id}/speech")
def suspect_speech(suspect_id: str, req: SpeechRequest) -> Response:
    voice = SUSPECT_VOICES.get(suspect_id)
    if voice is None:
        raise HTTPException(status_code=404, detail=f"Unknown suspect '{suspect_id}'")

    from openai import OpenAI

    client = OpenAI()
    audio = client.audio.speech.create(model="tts-1", voice=voice, input=req.text)
    return Response(content=audio.content, media_type="audio/mpeg")

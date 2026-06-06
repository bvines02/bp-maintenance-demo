from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound, TranscriptsDisabled, VideoUnavailable, YouTubeTranscriptApiException
)
import anthropic
import os
import re
import json
from datetime import datetime, timezone

router = APIRouter(prefix="/youtube", tags=["youtube"])

MAX_TRANSCRIPT_CHARS = 80_000


def _extract_video_id(url: str) -> str:
    patterns = [
        r"(?:v=|youtu\.be/|embed/)([A-Za-z0-9_-]{11})",
        r"^([A-Za-z0-9_-]{11})$",
    ]
    for pattern in patterns:
        match = re.search(pattern, url.strip())
        if match:
            return match.group(1)
    raise HTTPException(status_code=400, detail="Could not extract a valid YouTube video ID from the URL provided.")


def _get_transcript(video_id: str) -> tuple[str, str]:
    try:
        ytt = YouTubeTranscriptApi()
        transcript_list = ytt.list(video_id)
        try:
            transcript = transcript_list.find_manually_created_transcript(["en", "en-US", "en-GB"])
        except NoTranscriptFound:
            try:
                transcript = transcript_list.find_generated_transcript(["en", "en-US", "en-GB"])
            except NoTranscriptFound:
                transcript = next(iter(transcript_list))
        fetched = transcript.fetch()
        language = fetched.language
        text = " ".join(entry.text for entry in fetched)
        return text[:MAX_TRANSCRIPT_CHARS], language
    except TranscriptsDisabled:
        raise HTTPException(status_code=422, detail="Transcripts are disabled for this video.")
    except VideoUnavailable:
        raise HTTPException(status_code=422, detail="This video is unavailable.")
    except YouTubeTranscriptApiException as e:
        raise HTTPException(status_code=422, detail=f"Could not fetch transcript: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Unexpected error fetching transcript: {str(e)}")


SYSTEM_PROMPT = """\
You are an expert analyst. You will be given a YouTube video transcript and must produce a structured JSON response.

Return ONLY valid JSON with this exact schema (no markdown fences, no extra text):
{
  "summary": "A concise 2-3 paragraph summary of the video",
  "key_learnings": ["learning 1", "learning 2", ...],
  "key_concepts": [{"concept": "Name", "explanation": "1-2 sentence explanation"}, ...],
  "action_items": ["actionable takeaway 1", "actionable takeaway 2", ...],
  "notable_quotes": ["verbatim or near-verbatim quote from the transcript", ...]
}

Guidelines:
- key_learnings: 5-10 specific, concrete insights a viewer should take away
- key_concepts: 3-8 important ideas, frameworks, or terms introduced
- action_items: 3-6 things the viewer could do or apply from this video
- notable_quotes: 2-5 memorable or important statements from the speaker
- If a section has no relevant content, return an empty array []
"""


class TranscribeRequest(BaseModel):
    url: str


class TranscribeResponse(BaseModel):
    video_id: str
    language: str
    transcript_excerpt: str
    summary: str
    key_learnings: list[str]
    key_concepts: list[dict]
    action_items: list[str]
    notable_quotes: list[str]


@router.post("/transcribe", response_model=TranscribeResponse)
def transcribe_and_analyze(request: TranscribeRequest):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not set")

    video_id = _extract_video_id(request.url)
    transcript_text, language = _get_transcript(video_id)

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"Here is the transcript:\n\n{transcript_text}"
        }],
    )

    raw = response.content[0].text.strip()
    # Strip markdown fences if the model wraps output anyway
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        insights = json.loads(raw)
    except json.JSONDecodeError:
        insights = {
            "summary": raw,
            "key_learnings": [],
            "key_concepts": [],
            "action_items": [],
            "notable_quotes": [],
        }

    excerpt = transcript_text[:500] + ("..." if len(transcript_text) > 500 else "")

    return TranscribeResponse(
        video_id=video_id,
        language=language,
        transcript_excerpt=excerpt,
        summary=insights.get("summary", ""),
        key_learnings=insights.get("key_learnings", []),
        key_concepts=insights.get("key_concepts", []),
        action_items=insights.get("action_items", []),
        notable_quotes=insights.get("notable_quotes", []),
    )


class NotionExportRequest(BaseModel):
    page_id: str
    video_id: str
    video_url: str
    summary: str
    key_learnings: list[str]
    key_concepts: list[dict]
    action_items: list[str]
    notable_quotes: list[str]


def _t(text: str) -> dict:
    return {"type": "text", "text": {"content": text}}


def _heading(level: int, text: str) -> dict:
    return {
        "object": "block",
        "type": f"heading_{level}",
        f"heading_{level}": {"rich_text": [_t(text)]},
    }


def _paragraph(text: str) -> dict:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": [_t(text)]},
    }


def _bulleted(text: str) -> dict:
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": [_t(text)]},
    }


def _quote(text: str) -> dict:
    return {
        "object": "block",
        "type": "quote",
        "quote": {"rich_text": [_t(f'"{text}"')]},
    }


def _divider() -> dict:
    return {"object": "block", "type": "divider", "divider": {}}


def _build_notion_blocks(req: NotionExportRequest) -> list[dict]:
    blocks: list[dict] = []
    blocks.append(_paragraph(f"YouTube: https://www.youtube.com/watch?v={req.video_id}"))
    blocks.append(_paragraph(f"Saved: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"))
    blocks.append(_divider())

    blocks.append(_heading(2, "Summary"))
    for para in req.summary.split("\n\n"):
        if para.strip():
            blocks.append(_paragraph(para.strip()))

    if req.key_learnings:
        blocks.append(_divider())
        blocks.append(_heading(2, "Key Learnings"))
        for item in req.key_learnings:
            blocks.append(_bulleted(item))

    if req.key_concepts:
        blocks.append(_divider())
        blocks.append(_heading(2, "Key Concepts"))
        for c in req.key_concepts:
            concept = c.get("concept", "")
            explanation = c.get("explanation", "")
            blocks.append(_paragraph(f"{concept} — {explanation}"))

    if req.action_items:
        blocks.append(_divider())
        blocks.append(_heading(2, "Action Items"))
        for item in req.action_items:
            blocks.append(_bulleted(item))

    if req.notable_quotes:
        blocks.append(_divider())
        blocks.append(_heading(2, "Notable Quotes"))
        for q in req.notable_quotes:
            blocks.append(_quote(q))

    return blocks


@router.post("/save-to-notion")
def save_to_notion(req: NotionExportRequest):
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="NOTION_TOKEN not set in environment.")

    try:
        from notion_client import Client as NotionClient
        notion = NotionClient(auth=token)

        page_id_clean = req.page_id.replace("-", "")
        title = f"YT Insights — {req.video_id}"

        child_page = notion.pages.create(
            parent={"type": "page_id", "page_id": page_id_clean},
            properties={"title": {"title": [_t(title)]}},
            children=_build_notion_blocks(req),
        )
        return {"notion_url": child_page.get("url", ""), "page_id": child_page.get("id", "")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Notion export failed: {str(e)}")

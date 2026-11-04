"""Select a story moment and identify named figures in a generated scene."""
import json
from .meta_api import WONDER_IN, WONDER_OUT, cached, data_url

MODEL = "muse-wonder-1.0"
CAST_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["figures"],
    "properties": {"figures": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["mark", "name"],
        "properties": {"mark": {"type": "integer"}, "name": {"type": "string"}}}}},
}


def direct(marked, shot, characters, marks, label, feedback=None):
    prompt = (f"Identify the story characters using the numbered outlines in this image. "
              f"Scene: {shot}\nCharacters: {', '.join(characters)}\n"
              f"Available marks: {marks}. Return each matching mark and character name. "
              "Use each mark at most once. Exclude unrelated extras.")
    if feedback:
        prompt += "\nCorrect these errors: " + feedback
    body = {
        "model": MODEL,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": data_url(marked, quality=92)}}]}],
        "response_format": {"type": "json_schema", "json_schema": {
            "name": "scene_cast", "strict": True, "schema": CAST_SCHEMA}},
        "max_completion_tokens": 8000,
    }
    def cost(res):
        usage = res.get("usage", {})
        return usage.get("prompt_tokens", 0) * WONDER_IN + usage.get("completion_tokens", 0) * WONDER_OUT
    usable = lambda r: r["choices"][0].get("finish_reason") == "stop" and bool(r["choices"][0]["message"].get("content"))
    res = cached("wonder", "/chat/completions", body, cost, label, ok=usable)
    return json.loads(res["choices"][0]["message"]["content"]), res.get("usage", {})


READ_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["sentence", "shot", "characters"],
    "properties": {
        "sentence": {"type": "string"},
        "shot": {"type": "string"},
        "characters": {"type": "array", "items": {"type": "string"}}},
}

READ_PROMPT = """You are choosing the one moment from a passage of a novel to paint as a scene in an illustrated edition.

Book: {book}
Passage:
{passage}

Return:
- sentence: the single sentence from the passage, copied exactly, that the picture should show.
- shot: one or two sentences describing the picture: the place, the light, and what the characters in it are doing.
- characters: the named characters who appear in the picture, by their full names as the book gives them. Leave out crowds and unnamed passersby."""


def read(book, passage, label):
    """Muse Wonder reads a passage and picks the moment to paint and who is in it.
    Its shot and characters are the brief SAM's outlines are cast against."""
    body = {
        "model": MODEL,
        "messages": [{"role": "user", "content": [{"type": "text", "text": READ_PROMPT.format(book=book, passage=passage)}]}],
        "response_format": {"type": "json_schema", "json_schema": {"name": "scene_moment", "strict": True, "schema": READ_SCHEMA}},
        "max_completion_tokens": 8000,
    }

    def cost(res):
        u = res.get("usage", {})
        return u.get("prompt_tokens", 0) * WONDER_IN + u.get("completion_tokens", 0) * WONDER_OUT

    usable = lambda r: r["choices"][0].get("finish_reason") == "stop" and bool(r["choices"][0]["message"].get("content"))
    res = cached("wonder", "/chat/completions", body, cost, label, ok=usable)
    return json.loads(res["choices"][0]["message"]["content"])


def problems(plan, marks):
    issues, used = [], set()
    for figure in plan["figures"]:
        mark = figure["mark"]
        if mark not in marks:
            issues.append(f"Unknown mark: {mark}")
        elif mark in used:
            issues.append(f"Duplicate mark: {mark}")
        used.add(mark)
    return issues

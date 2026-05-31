import os
import json
from typing import Any

CACHE_FILE = ".grading_cache.json"

def _get_cache_path() -> str:
    # Save cache file in the current working directory for simplicity
    return os.path.abspath(CACHE_FILE)

def load_cache() -> dict[str, dict[str, dict[str, Any]]]:
    """
    Returns a dict structure:
    {
        "session_id": {
            "question_id": {
                "examiner_score": 10.0,
                "examiner_comment": "Good job"
            }
        }
    }
    """
    path = _get_cache_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_cache(cache: dict) -> None:
    path = _get_cache_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
    except Exception:
        pass

def get_session_cache(session_id: str) -> dict[str, dict[str, Any]]:
    cache = load_cache()
    return cache.get(str(session_id), {})

def save_answer_draft(session_id: str, question_id: str, score: float | None, comment: str, is_synced: bool = False) -> None:
    session_id = str(session_id)
    question_id = str(question_id)
    
    cache = load_cache()
    if session_id not in cache:
        cache[session_id] = {}
        
    cache[session_id][question_id] = {
        "examiner_score": score,
        "examiner_comment": comment,
        "is_synced": is_synced
    }
    
    save_cache(cache)

def get_unsynced_drafts(session_id: str) -> dict[str, dict[str, Any]]:
    cache = get_session_cache(session_id)
    return {qid: data for qid, data in cache.items() if not data.get("is_synced", False)}

def mark_as_synced(session_id: str, question_ids: list[str]) -> None:
    session_id = str(session_id)
    cache = load_cache()
    if session_id not in cache:
        return
    for qid in question_ids:
        qid = str(qid)
        if qid in cache[session_id]:
            cache[session_id][qid]["is_synced"] = True
    save_cache(cache)

def clear_session_cache(session_id: str) -> None:
    session_id = str(session_id)
    cache = load_cache()
    if session_id in cache:
        del cache[session_id]
        save_cache(cache)

def has_drafts(session_id: str) -> bool:
    cache = get_session_cache(session_id)
    return len(cache) > 0

def load_drafts(session_id: str) -> dict[str, dict[str, Any]]:
    return get_session_cache(session_id)

def clear_drafts(session_id: str) -> None:
    clear_session_cache(session_id)


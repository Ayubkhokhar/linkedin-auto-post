"""
topic_manager.py — Manages post type rotation and topic selection.

Tracks recently used topics (stored in data/post_history.json) to
avoid repetition and ensure varied content across posts.
"""

import json
import random
import os
from datetime import datetime, timezone
from typing import Tuple, Optional


SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "settings.json")
HISTORY_PATH  = os.path.join(os.path.dirname(__file__), "..", "data", "post_history.json")


def load_settings() -> dict:
    with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_history() -> dict:
    try:
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"posts": [], "last_updated": None, "total_posts": 0, "topics_used": []}


def save_history(history: dict) -> None:
    os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def weighted_choice(weights: dict) -> str:
    """Pick a post type based on configured weights."""
    types = list(weights.keys())
    probs = [weights[t] for t in types]
    return random.choices(types, weights=probs, k=1)[0]


def avoid_repeat(candidates: list, recently_used: list, lookback: int = 5) -> list:
    """Filter out recently used topics to encourage variety."""
    filtered = [c for c in candidates if c not in recently_used[-lookback:]]
    return filtered if filtered else candidates  # fallback if all used recently


def select_post_type_and_topic(hint: Optional[str] = None) -> Tuple[str, str]:
    """
    Returns (post_type, topic) for the next post.
    
    Args:
        hint: Optional keyword hint from manual trigger via dashboard.
    
    Returns:
        Tuple of (post_type_key, topic_string)
    """
    settings = load_settings()
    history  = load_history()

    recent_topics = [p.get("topic", "") for p in history.get("posts", [])[-10:]]
    recent_types  = [p.get("post_type", "") for p in history.get("posts", [])[-5:]]

    # Adjust weights to downrank recent types
    weights = dict(settings["post_type_weights"])
    for pt in recent_types:
        if pt in weights:
            weights[pt] = max(0.01, weights[pt] * 0.3)

    # Normalize weights
    total = sum(weights.values())
    weights = {k: v / total for k, v in weights.items()}

    post_type = weighted_choice(weights)
    topics    = settings["topics"].get(post_type, ["developer life"])
    available = avoid_repeat(topics, recent_topics)

    # If a hint was given, try to match it to a topic
    if hint:
        matched = [t for t in topics if hint.lower() in t.lower()]
        if matched:
            topic = random.choice(matched)
        else:
            topic = random.choice(available)
    else:
        topic = random.choice(available)

    return post_type, topic


def get_hashtags(post_type: str, topic: str) -> list:
    """Select relevant hashtags (max 5, never repetitive)."""
    settings = load_settings()
    history  = load_history()

    recent_tags = []
    for p in history.get("posts", [])[-6:]:
        recent_tags.extend(p.get("hashtags", []))

    pool    = settings["hashtag_pools"]["rotating"]
    always  = settings["hashtag_pools"]["always_include"]
    max_ht  = settings["hashtag_pools"]["max_hashtags"]

    # Filter out recently used tags
    fresh_pool = [t for t in pool if t not in recent_tags[-12:]]
    if len(fresh_pool) < 3:
        fresh_pool = pool

    # Always include 2 base tags + 3 random rotating ones
    chosen = random.sample(fresh_pool, min(max_ht - len(always), len(fresh_pool)))
    return always + chosen


def log_post(post_type: str, topic: str, hashtags: list, linkedin_post_id: str,
             post_text: str, image_url: str = "") -> None:
    """Log a successfully published post to history."""
    history = load_history()
    
    entry = {
        "id": linkedin_post_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "post_type": post_type,
        "topic": topic,
        "hashtags": hashtags,
        "text_preview": post_text[:200] + ("..." if len(post_text) > 200 else ""),
        "image_url": image_url,
        "linkedin_url": f"https://www.linkedin.com/feed/update/{linkedin_post_id}/" if linkedin_post_id else "",
    }

    history["posts"].append(entry)
    history["total_posts"] = len(history["posts"])
    history["last_updated"] = datetime.now(timezone.utc).isoformat()

    if topic not in history.get("topics_used", []):
        history.setdefault("topics_used", []).append(topic)

    save_history(history)
    print(f"[topic_manager] Post logged: type={post_type}, topic='{topic}'")


if __name__ == "__main__":
    # Quick test
    pt, topic = select_post_type_and_topic()
    tags = get_hashtags(pt, topic)
    print(f"Post type : {pt}")
    print(f"Topic     : {topic}")
    print(f"Hashtags  : {tags}")

"""
generate_post.py — Main orchestrator for LinkedIn auto-posting.

Workflow:
    1. Select post type and topic (via topic_manager)
    2. Generate human-like post text via Gemini API
    3. Generate relevant image via Imagen API (or Unsplash fallback)
    4. Refresh LinkedIn token if needed
    5. Upload image to LinkedIn
    6. Publish post to LinkedIn /rest/posts
    7. Update GitHub Secrets with new tokens (if refreshed)
    8. Log post to data/post_history.json

Run:
    python scripts/generate_post.py              # Full run
    python scripts/generate_post.py --dry-run    # Generate only, do NOT post
    python scripts/generate_post.py --hint "React hooks"   # Topic hint
"""

import os
import sys
import json
import time
import base64
import argparse
import random
import requests
from datetime import datetime, timezone
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent))
from topic_manager import select_post_type_and_topic, get_hashtags, log_post

from google import genai
from google.genai import types as genai_types

# ─── ENV VARS (from GitHub Secrets) ─────────────────────────────────────────
GEMINI_API_KEY         = os.getenv("GEMINI_API_KEY", "")
LINKEDIN_CLIENT_ID     = os.getenv("LINKEDIN_CLIENT_ID", "")
LINKEDIN_CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET", "")
LINKEDIN_ACCESS_TOKEN  = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
LINKEDIN_REFRESH_TOKEN = os.getenv("LINKEDIN_REFRESH_TOKEN", "")
LINKEDIN_USER_URN      = os.getenv("LINKEDIN_USER_URN", "")
GH_PAT                 = os.getenv("GH_PAT", "")
GH_REPO                = os.getenv("GITHUB_REPOSITORY", "")  # auto-set by Actions
DRY_RUN                = os.getenv("DRY_RUN", "false").lower() == "true"
TOPIC_HINT             = os.getenv("TOPIC_HINT", "")
# ─────────────────────────────────────────────────────────────────────────────

LINKEDIN_API_BASE  = "https://api.linkedin.com"
LINKEDIN_VERSION   = "202501"
TOKEN_REFRESH_URL  = "https://www.linkedin.com/oauth/v2/accessToken"


# ══════════════════════════════════════════════════════════════════════════════
# 1. POST TEXT GENERATION
# ══════════════════════════════════════════════════════════════════════════════

POST_PROMPTS = {
    "dev_tip": """You are a real developer named Irfan — a passionate full-stack developer from Pakistan with 3 years of experience. 
You are writing a LinkedIn post about: {topic}

Write a SHORT, natural LinkedIn post (250-400 words MAX) that:
- Shares a genuine tip or insight from your own experience
- Uses first-person, conversational voice ("I", "my", "me")
- Feels like a human wrote it, not an AI
- Includes ONE specific story or moment (e.g. "Last week I was building...")
- Mixes short punchy sentences with longer ones
- Shows real emotion: curiosity, excitement, mild frustration — whatever fits
- Ends with a subtle call to action or genuine question

STRICT RULES — NEVER break these:
- No em dashes (—) at all
- No "Game-changer", "Dive into", "Leverage", "Seamless", "Revolutionize"
- No "In today's world" or "In conclusion"
- No "I am excited to share" or "I am thrilled"
- No perfect numbered lists for the entire post
- Do NOT use hashtags in the body — add them ONLY at the very end on a new line
- Max 5 hashtags total

Persona:
- Stack: React, Next.js, Node.js, TypeScript, Python, PostgreSQL
- Specialties: freelance dev, REST APIs, UI/UX, web apps
- Tone: real, grounded, sometimes self-deprecating, always learning

Write the post now. No intro, no explanation — just the post content:""",

    "client_story": """You are Irfan, a freelance full-stack developer from Pakistan. 
You are writing a LinkedIn post about a real client experience: {topic}

Write a gripping SHORT story post (280-420 words) that:
- Starts with the problem or situation (NOT "I had a client who...")
- Uses narrative storytelling: sets the scene, builds tension, gives the resolution
- Includes specific details that make it feel real (numbers, error messages, tools used)
- Shows what YOU learned or what YOU did to fix it
- Feels genuinely personal, not like a case study

STRICT RULES:
- No em dashes (—)
- No AI clichés ("game-changer", "leverage", "deep dive")
- No "In conclusion" or "Key takeaways:"
- Hashtags only at the very end on a separate line (max 5)
- Do NOT use headers or subheadings

Write the post now:""",

    "tech_discovery": """You are Irfan, a full-stack dev who loves exploring new tools. 
You are writing a LinkedIn post about: {topic}

Write an honest, exploratory post (220-380 words) that:
- Shares your REAL first impression of a tool or technology
- Is honest — include both pros AND at least one "but" or limitation
- Uses conversational language like you're telling a friend
- Shows your thought process, not just the conclusion
- Doesn't oversell it — be genuine

STRICT RULES:
- No em dashes (—)
- No "Game-changer", "must-have", "revolutionary"  
- No "I am excited to share"
- Hashtags only at the end, separate line (max 5)

Write the post now:""",

    "dev_journey": """You are Irfan, a self-taught full-stack developer. 
You are writing a reflective LinkedIn post about: {topic}

Write a vulnerable, honest personal story (250-400 words) that:
- Shares a real moment of struggle or growth in your developer journey
- Shows the before/after — how you felt then vs now
- Includes one specific memory or detail that grounds the story
- Ends with an insight or encouragement that doesn't sound preachy
- Feels like you're talking to a developer who's going through the same thing

STRICT RULES:
- No em dashes (—)
- No "journey", "imposter syndrome" (overused), no "hustle"
- No generic motivational phrases
- Hashtags only at the end (max 5)

Write the post now:""",

    "debugging_story": """You are Irfan, a full-stack developer. 
You are writing about a real debugging experience: {topic}

Write a dramatic, relatable debugging story (220-360 words) that:
- Opens with the pain: "X hours. Same error. I was losing my mind."
- Describes what you tried (and failed) before finding the fix
- Reveals the actual cause (often embarrassingly simple)
- Ends with the lesson or the laugh
- Uses short, tense sentences during the struggle — longer sentences during the resolution

STRICT RULES:
- No em dashes (—)
- Hashtags only at the end (max 5)
- No "spoiler alert:"
- Keep it real, not dramatized for the sake of drama

Write the post now:""",

    "community_question": """You are Irfan, a full-stack developer who genuinely loves the dev community. 
You are writing an engagement post about: {topic}

Write a SHORT, genuine question-based post (150-250 words) that:
- States your own opinion or preference FIRST
- Then asks the community for theirs
- Feels like real curiosity, not manufactured engagement bait
- Might include a brief personal anecdote (2-3 sentences max)
- Ends with a clear, simple question

STRICT RULES:
- No em dashes (—)
- No "I'd love to hear your thoughts!"
- Hashtags only at the end (max 5)

Write the post now:"""
}


def build_prompt(post_type: str, topic: str, hashtags: list) -> str:
    template = POST_PROMPTS.get(post_type, POST_PROMPTS["dev_tip"])
    base_prompt = template.format(topic=topic)
    hashtag_str = " ".join(f"#{h}" for h in hashtags)
    base_prompt += f"\n\nEnd the post with exactly these hashtags on the last line:\n{hashtag_str}"
    return base_prompt


def generate_post_text(post_type: str, topic: str, hashtags: list) -> str:
    """Generate post text using Gemini API."""
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        generation_config={
            "temperature": 0.92,
            "top_p": 0.95,
            "max_output_tokens": 800,
        }
    )

    prompt = build_prompt(post_type, topic, hashtags)
    
    for attempt in range(3):
        try:
            response = model.generate_content(prompt)
            text = response.text.strip()
            
            # Sanitize: remove any em dashes that slipped through
            text = text.replace("—", "-").replace("–", "-")
            
            # Ensure hashtags are at the end
            if not any(f"#{h}" in text for h in hashtags):
                hashtag_line = " ".join(f"#{h}" for h in hashtags)
                text = f"{text}\n\n{hashtag_line}"
            
            print(f"[gemini] Post text generated ({len(text)} chars)")
            return text
            
        except Exception as e:
            print(f"[gemini] Attempt {attempt+1} failed: {e}")
            time.sleep(2 ** attempt)

    raise RuntimeError("Failed to generate post text after 3 attempts")


# ══════════════════════════════════════════════════════════════════════════════
# 2. IMAGE GENERATION
# ══════════════════════════════════════════════════════════════════════════════

IMAGE_PROMPTS = {
    "dev_tip":          "A developer's clean minimal workspace with code on screen, modern setup, soft blue lighting, photorealistic",
    "client_story":     "A professional video call between developer and client, laptop with code visible, warm office lighting, realistic",
    "tech_discovery":   "A developer exploring a new app or tool on a widescreen monitor, modern dark UI, excited expression, photorealistic",
    "dev_journey":      "A lone developer late at night at their desk with a coffee cup, code on screen, warm lamp light, cinematic",
    "debugging_story":  "A developer staring intensely at a computer screen with multiple browser tabs open, slightly stressed, realistic",
    "community_question": "A diverse group of developers collaborating in a modern tech office, laptops open, animated discussion",
}


def generate_image_gemini(post_type: str, post_text: str) -> bytes | None:
    """Try to generate image using Gemini/Imagen API."""
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        
        # Use imagen-3.0-fast-generate-001 (available on free tier)
        model = genai.ImageGenerationModel("imagen-3.0-generate-001")
        
        base_prompt = IMAGE_PROMPTS.get(post_type, IMAGE_PROMPTS["dev_tip"])
        full_prompt = f"{base_prompt}. Professional LinkedIn post image, 16:9 aspect ratio, no text overlay."
        
        response = model.generate_images(
            prompt=full_prompt,
            number_of_images=1,
            aspect_ratio="16:9",
            safety_filter_level="block_some",
        )
        
        if response.images:
            img = response.images[0]
            print("[imagen] Image generated successfully")
            return img._image_bytes
            
    except Exception as e:
        print(f"[imagen] Failed (will use Unsplash fallback): {e}")
    
    return None


def get_unsplash_image(post_type: str) -> tuple[str, bytes]:
    """
    Fallback: get a relevant image from Unsplash (no API key needed for source).
    Returns (url, image_bytes)
    """
    # Unsplash Source API — free, no key required
    keywords = {
        "dev_tip":           "programming,code,developer",
        "client_story":      "business,meeting,laptop",
        "tech_discovery":    "technology,innovation,computer",
        "dev_journey":       "developer,night,coding",
        "debugging_story":   "code,screen,developer",
        "community_question": "team,collaboration,office",
    }
    kw = keywords.get(post_type, "developer,code")
    
    # Use a curated set of high-quality tech images from Unsplash
    # These are stable IDs of beautiful tech photos
    photo_pools = {
        "dev_tip":           ["oalS4H1IIDA", "Bj6ENZDMSDY", "m_HRfLhgABo", "vXInUOv1n84"],
        "client_story":      ["5fNmWej4tAA", "GI1hwOGqGtE", "1K9T5YiZ2jU", "7okkFhxrxNw"],
        "tech_discovery":    ["IgWNxx7paz4", "BfrQnKBulYQ", "ZVprbBmT8QA", "mkbX8PXMxaU"],
        "dev_journey":       ["5Ntkpxqt54Y", "ygtbDbgjRYQ", "2EJCSULRwC8", "KE0nC8-58MQ"],
        "debugging_story":   ["hGV2TfOh0ns", "qjX0QBtDXto", "FO7JIlwjOtU", "b18TRXc8UPQ"],
        "community_question":["people,team,meeting", "collaboration,office", "startup,team", "developers,office"],
    }
    
    photo_id = random.choice(photo_pools.get(post_type, photo_pools["dev_tip"]))
    
    # Direct Unsplash photo URL (reliable, no API key)
    if "/" not in photo_id:  # it's a photo ID
        url = f"https://images.unsplash.com/photo-{photo_id}?w=1200&h=627&fit=crop&auto=format&q=80"
    else:
        url = f"https://source.unsplash.com/1200x627/?{kw}"
    
    try:
        resp = requests.get(url, timeout=15)
        if resp.ok and len(resp.content) > 1000:
            print(f"[unsplash] Image fetched ({len(resp.content)//1024}KB)")
            return url, resp.content
    except Exception as e:
        print(f"[unsplash] Failed: {e}")
    
    return url, b""


# ══════════════════════════════════════════════════════════════════════════════
# 3. LINKEDIN TOKEN MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

def refresh_linkedin_token() -> tuple[str, str]:
    """Refresh LinkedIn access token using refresh token."""
    global LINKEDIN_ACCESS_TOKEN, LINKEDIN_REFRESH_TOKEN
    
    if not LINKEDIN_REFRESH_TOKEN:
        print("[linkedin] No refresh token available. Using existing access token.")
        return LINKEDIN_ACCESS_TOKEN, LINKEDIN_REFRESH_TOKEN
    
    print("[linkedin] Refreshing access token...")
    resp = requests.post(TOKEN_REFRESH_URL, data={
        "grant_type": "refresh_token",
        "refresh_token": LINKEDIN_REFRESH_TOKEN,
        "client_id": LINKEDIN_CLIENT_ID,
        "client_secret": LINKEDIN_CLIENT_SECRET,
    })
    
    if resp.ok:
        data = resp.json()
        new_access  = data.get("access_token", LINKEDIN_ACCESS_TOKEN)
        new_refresh = data.get("refresh_token", LINKEDIN_REFRESH_TOKEN)
        LINKEDIN_ACCESS_TOKEN  = new_access
        LINKEDIN_REFRESH_TOKEN = new_refresh
        print("[linkedin] Token refreshed successfully")
        return new_access, new_refresh
    else:
        print(f"[linkedin] Token refresh failed: {resp.status_code} {resp.text}")
        return LINKEDIN_ACCESS_TOKEN, LINKEDIN_REFRESH_TOKEN


def validate_token() -> bool:
    """Check if current access token is valid."""
    headers = {
        "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
        "LinkedIn-Version": LINKEDIN_VERSION,
    }
    resp = requests.get(f"{LINKEDIN_API_BASE}/v2/userinfo", headers=headers, timeout=10)
    return resp.status_code == 200


def update_github_secrets(access_token: str, refresh_token: str) -> None:
    """Update GitHub Secrets with new tokens via GitHub API."""
    if not GH_PAT or not GH_REPO:
        print("[github] Cannot update secrets — GH_PAT or GITHUB_REPOSITORY not set")
        return
    
    try:
        from nacl import encoding, public as nacl_public
        
        # Get repo public key for secret encryption
        headers = {
            "Authorization": f"Bearer {GH_PAT}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        key_resp = requests.get(
            f"https://api.github.com/repos/{GH_REPO}/actions/secrets/public-key",
            headers=headers
        )
        
        if not key_resp.ok:
            print(f"[github] Failed to get public key: {key_resp.status_code}")
            return
        
        key_data   = key_resp.json()
        public_key = key_data["key"]
        key_id     = key_data["key_id"]
        
        def encrypt_secret(public_key_str: str, secret_value: str) -> str:
            pk = nacl_public.PublicKey(public_key_str.encode("utf-8"), encoding.Base64Encoder())
            sealed_box = nacl_public.SealedBox(pk)
            encrypted  = sealed_box.encrypt(secret_value.encode("utf-8"))
            return base64.b64encode(encrypted).decode("utf-8")
        
        secrets_to_update = {
            "LINKEDIN_ACCESS_TOKEN":  access_token,
            "LINKEDIN_REFRESH_TOKEN": refresh_token,
        }
        
        for secret_name, secret_value in secrets_to_update.items():
            if not secret_value:
                continue
            encrypted = encrypt_secret(public_key, secret_value)
            update_resp = requests.put(
                f"https://api.github.com/repos/{GH_REPO}/actions/secrets/{secret_name}",
                headers=headers,
                json={"encrypted_value": encrypted, "key_id": key_id},
            )
            if update_resp.ok or update_resp.status_code == 204:
                print(f"[github] Secret {secret_name} updated")
            else:
                print(f"[github] Failed to update {secret_name}: {update_resp.status_code}")
    
    except ImportError:
        print("[github] PyNaCl not installed — cannot update secrets")
    except Exception as e:
        print(f"[github] Error updating secrets: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# 4. LINKEDIN POSTING
# ══════════════════════════════════════════════════════════════════════════════

def get_auth_headers() -> dict:
    return {
        "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
        "LinkedIn-Version": LINKEDIN_VERSION,
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json",
    }


def upload_image_to_linkedin(image_bytes: bytes) -> str | None:
    """Upload image to LinkedIn and return the asset URN."""
    if not image_bytes:
        return None
    
    headers = get_auth_headers()
    
    # Step 1: Register upload
    register_body = {
        "initializeUploadRequest": {
            "owner": LINKEDIN_USER_URN,
        }
    }
    
    init_resp = requests.post(
        f"{LINKEDIN_API_BASE}/rest/images?action=initializeUpload",
        headers=headers,
        json=register_body,
        timeout=15,
    )
    
    if not init_resp.ok:
        print(f"[linkedin] Image init failed: {init_resp.status_code} {init_resp.text}")
        return None
    
    init_data    = init_resp.json()
    upload_url   = init_data["value"]["uploadUrl"]
    image_urn    = init_data["value"]["image"]
    
    # Step 2: Upload binary
    upload_headers = {
        "Authorization": f"Bearer {LINKEDIN_ACCESS_TOKEN}",
        "Content-Type": "image/jpeg",
    }
    upload_resp = requests.put(upload_url, headers=upload_headers, data=image_bytes, timeout=30)
    
    if not upload_resp.ok:
        print(f"[linkedin] Image upload failed: {upload_resp.status_code}")
        return None
    
    print(f"[linkedin] Image uploaded: {image_urn}")
    return image_urn


def publish_post(text: str, image_urn: str | None = None) -> str | None:
    """Publish the post to LinkedIn. Returns the post URN."""
    headers = get_auth_headers()
    
    content = {
        "author": LINKEDIN_USER_URN,
        "commentary": text,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    
    if image_urn:
        content["content"] = {
            "media": {
                "altText": "Developer workspace",
                "id": image_urn,
            }
        }
    
    resp = requests.post(
        f"{LINKEDIN_API_BASE}/rest/posts",
        headers=headers,
        json=content,
        timeout=20,
    )
    
    if resp.ok or resp.status_code == 201:
        post_urn = resp.headers.get("x-restli-id", "")
        print(f"[linkedin] Post published! URN: {post_urn}")
        return post_urn
    else:
        print(f"[linkedin] Post failed: {resp.status_code}")
        print(resp.text)
        return None


# ══════════════════════════════════════════════════════════════════════════════
# 5. MAIN ORCHESTRATOR
# ══════════════════════════════════════════════════════════════════════════════

def main(dry_run: bool = False, hint: str = "") -> None:
    print("\n" + "="*55)
    print("  LinkedIn Auto-Post — Starting")
    print(f"  Mode: {'DRY RUN (no posting)' if dry_run else 'LIVE'}")
    print(f"  Time: {datetime.now(timezone.utc).isoformat()}")
    print("="*55 + "\n")

    # Validate config
    if not GEMINI_API_KEY:
        raise EnvironmentError("GEMINI_API_KEY is not set")
    if not LINKEDIN_USER_URN and not dry_run:
        raise EnvironmentError("LINKEDIN_USER_URN is not set")

    # 1. Select topic
    post_type, topic = select_post_type_and_topic(hint or TOPIC_HINT)
    hashtags          = get_hashtags(post_type, topic)
    print(f"[step 1] Post type: {post_type}")
    print(f"[step 1] Topic: {topic}")
    print(f"[step 1] Hashtags: {hashtags}\n")

    # 2. Generate text
    print("[step 2] Generating post text...")
    post_text = generate_post_text(post_type, topic, hashtags)
    print(f"\n{'─'*50}\n{post_text}\n{'─'*50}\n")

    # 3. Generate image
    print("[step 3] Generating image...")
    image_bytes = generate_image_gemini(post_type, post_text)
    image_url   = ""
    
    if not image_bytes:
        image_url, image_bytes = get_unsplash_image(post_type)
        print(f"[step 3] Using Unsplash fallback: {image_url}")

    if dry_run:
        print("\n[DRY RUN] Skipping LinkedIn posting. Post content above is what would be published.")
        print(f"[DRY RUN] Image source: {image_url or 'Gemini-generated'}")
        return

    # 4. Validate / refresh LinkedIn token
    print("[step 4] Validating LinkedIn token...")
    token_refreshed  = False
    new_access_token = LINKEDIN_ACCESS_TOKEN
    new_refresh_token = LINKEDIN_REFRESH_TOKEN
    
    if not validate_token():
        print("[step 4] Token invalid. Refreshing...")
        new_access_token, new_refresh_token = refresh_linkedin_token()
        if not validate_token():
            raise RuntimeError("LinkedIn token is invalid and could not be refreshed. Re-run token_helper.py locally.")
        token_refreshed = True
    else:
        print("[step 4] Token valid.")

    # 5. Upload image
    print("[step 5] Uploading image to LinkedIn...")
    image_urn = upload_image_to_linkedin(image_bytes) if image_bytes else None

    # 6. Publish post
    print("[step 6] Publishing post...")
    post_urn = publish_post(post_text, image_urn)

    if not post_urn:
        raise RuntimeError("Post failed to publish. Check logs above.")

    # 7. Update GitHub secrets if token was refreshed
    if token_refreshed:
        print("[step 7] Updating GitHub Secrets with new tokens...")
        update_github_secrets(new_access_token, new_refresh_token)
    else:
        print("[step 7] Token not refreshed, skipping secret update.")

    # 8. Log post
    print("[step 8] Logging post to history...")
    log_post(post_type, topic, hashtags, post_urn, post_text, image_url)

    print("\n" + "="*55)
    print("  SUCCESS! Post published to LinkedIn.")
    print(f"  URN: {post_urn}")
    print("="*55 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LinkedIn Auto-Post Generator")
    parser.add_argument("--dry-run", action="store_true", help="Generate post without publishing")
    parser.add_argument("--hint", type=str, default="", help="Optional topic hint keyword")
    args = parser.parse_args()
    
    main(dry_run=args.dry_run or DRY_RUN, hint=args.hint)

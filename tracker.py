import os
import re
import json
import urllib.request
from datetime import datetime, timezone, timedelta

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
DATA_FILE = "data.json"

TRACKED_REPOS = [
    {"name": "VIctory", "repo": "Marvisak/VIctory"},
    {"name": "XCL", "repo": "ivall/xcl"}
]

def fetch_url(url, is_json=True):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GTA6-Intel/3.1"}
    if GITHUB_TOKEN and "api.github.com" in url:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
            return json.loads(raw) if is_json else raw
    except Exception as e:
        print(f"Fetch error ({url}): {e}")
        return None

def get_daily_github_work():
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)
    work_summary = {}

    for item in TRACKED_REPOS:
        slug = item["repo"]
        commits = fetch_url(f"https://api.github.com/repos/{slug}/commits?per_page=50") or []
        info = fetch_url(f"https://api.github.com/repos/{slug}") or {}
        work_today = 0
        latest_msg = "No recent commit"
        for idx, c in enumerate(commits):
            dt_str = c.get("commit", {}).get("author", {}).get("date", "")
            if idx == 0:
                latest_msg = c.get("commit", {}).get("message", "").splitlines()[0]
            if dt_str and datetime.fromisoformat(dt_str.replace("Z", "+00:00")) >= day_ago:
                work_today += 1
        work_summary[item["name"]] = {
            "commits_24h": work_today,
            "stars": info.get("stargazers_count", 0),
            "pushed_at": info.get("pushed_at", ""),
            "latest_commit": latest_msg
        }
    return work_summary

def analyze_all_sources(sources, old_data):
    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY environment variable is missing or empty!")
        return {
            "current_leader": "VIctory",
            "leader_stage": "In-Development / Booting",
            "most_active_today": "VIctory",
            "ai_summary": "API Key not detected in GitHub Secrets. Please check your repository secrets configuration.",
            "prediction": "Configure GEMINI_API_KEY in repository secrets to enable live AI analysis.",
            "leaderboard": [
                {
                    "rank": 1,
                    "name": "VIctory",
                    "stage": "Booting",
                    "progress_pct": 45,
                    "highest_achievement": "Initial codebase setup and compilation attempts",
                    "work_today_score": 50,
                    "work_today_note": "Awaiting active AI token sync",
                    "works": ["Repository active"],
                    "known_issues": ["Missing API Key secret"],
                    "remaining_todo": "Add GEMINI_API_KEY to GitHub repo settings"
                }
            ],
            "news_highlights": [{"source": "System", "headline": "Awaiting valid Gemini API Key in GitHub Secrets"}]
        }

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    prompt = f"""
    You are an analytical tracker monitoring the entire unofficial GTA VI PC port / Xbox compatibility race.
    Analyze the live data scraped from PortWatch VI (portwatch-vi.xyz), vuyp.github.io/gta6-pc-race, GitHub daily work counts, and Reddit.

    SCRAPED SOURCES:
    {json.dumps(sources)}

    PREVIOUS STATE:
    {json.dumps(old_data.get("analysis") if old_data else None)}

    Rules:
- Identify the TRUE current overall leader across ALL projects mentioned in the trackers (e.g., CGBJ, VIctory, AnyXboxX, XCL, Palmwave, etc. — whoever is actually #1, even if it's not VIctory or XCL).
- For EVERY project in the leaderboard, specify their "highest_achievement" (the biggest milestone they have successfully achieved so far, e.g., "Successfully booted main menu and rendered first gameplay frame", "Reached opening mission loading sequence").
- Return ONLY valid JSON matching this schema:
    {{
      "current_leader": "Exact name of #1 leading project right now",
      "leader_stage": "Current milestone stage of leader",
      "most_active_today": "Project doing the most work in the last 24 hours",
      "ai_summary": "Clear 2-3 sentence executive summary of the entire race right now and what changed today",
      "prediction": "Concrete prediction on who will hit stable playable gameplay first and rough timeline/blockers",
      "leaderboard": [
        {{
          "rank": 1,
          "name": "Project Name",
          "stage": "e.g., In-Game",
          "progress_pct": 68,
          "highest_achievement": "The single highest technical milestone they've pulled off so far",
          "work_today_score": 85,
          "work_today_note": "Summary of today's progress / commits",
          "works": ["Item 1 that works", "Item 2 that works"],
          "known_issues": ["Main crash/glitch 1"],
          "remaining_todo": "What still needs to be built to reach stable 30 FPS"
        }}
      ],
      "news_highlights": [
        {{"source": "PortWatch / GitHub", "headline": "Short factual update"}}
      ]
    }}
    Include the top 4-5 active projects in "leaderboard" (making sure to prominently feature VIctory, XCL, and any project currently ahead of them).
    """
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.25}
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=35) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            return json.loads(res["candidates"][0]["content"]["parts"][0]["text"])
    except Exception as e:
        print(f"Gemini API request failed: {e}")
        raise e

def send_discord_alert(new_data, old_data):
    if not DISCORD_WEBHOOK:
        return
    pass

if __name__ == "__main__":
    print("Starting GTA VI Port Intel Sync...")
    github_data = get_daily_github_work()
    
    sources = {
        "github": github_data,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    old_data = {}
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                old_data = json.load(f)
        except Exception:
            pass
            
    print("Running Gemini analysis...")
    analysis = analyze_all_sources(sources, old_data)
    
    output = {
        "sources": sources,
        "analysis": analysis,
        "last_updated": datetime.now(timezone.utc).isoformat()
    }
    
    with open(DATA_FILE, "w") as f:
        json.dump(output, f, indent=2)
    print("Successfully updated data.json!")

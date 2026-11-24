import os
import re
import json
import urllib.request
import urllib.error
import time
from datetime import datetime, timezone, timedelta

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
DATA_FILE = "data.json"

TRACKED_REPOS = [
    {"name": "VIctory", "repo": "Marvisak/VIctory"},
    {"name": "XCL", "repo": "ivall/xcl"}
]

def fetch_url(url, is_json=True):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GTA6-Intel/3.3"}
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

def strip_html(html_text):
    if not html_text:
        return ""
    clean = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", html_text)
    clean = re.sub(r"<[^>]+>", " ", clean)
    return re.sub(r"\s+", " ", clean).strip()[:5500]

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
            "leader_stage": "Playable",
            "leader_score": 59.8,
            "most_active_today": "VIctory",
            "ai_summary": "API Key not detected in GitHub Secrets. Please check your repository configuration.",
            "prediction": "Configure GEMINI_API_KEY in repository secrets to enable live AI analysis.",
            "leaderboard": [
                {
                    "rank": 1,
                    "name": "VIctory",
                    "stage": "Playable",
                    "progress_pct": 59.8,
                    "highest_achievement": "Reached opening prison/gameplay sequence",
                    "work_today_score": 50,
                    "work_today_note": "Awaiting active AI token sync",
                    "works": ["Repository active"],
                    "known_issues": ["Missing API Key secret"],
                    "remaining_stages": ["Rendering", "Performance", "Stability"]
                }
            ],
            "news_highlights": [{"source": "System", "headline": "Awaiting valid Gemini API Key in GitHub Secrets"}]
        }

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    prompt = f"""
    You are an analytical tracker monitoring the unofficial GTA VI PC port / Xbox compatibility race.
    Analyze the live & historical data scraped from PortWatch VI (https://portwatch-vi.xyz) and gta6-pc-race (https://vuyp.github.io/gta6-pc-race/), alongside GitHub commit velocity.

    SCRAPED SOURCES:
    {json.dumps(sources)}

    PREVIOUS STATE:
    {json.dumps(old_data.get("analysis") if old_data else None)}

    Rules:
    - Match PortWatch VI's scoring style where projects are measured on a 0% to 100% scale spanning milestones: 0% Groundwork, 10% Exe runs, 20% First frame, 30% Main menu, 40% In the world, 50% Playable, 70% Rendering, 85% Performance, 100% Complete.
    - Identify the TRUE current overall leader across all tracked projects (e.g. CGBJ, VIctory, AnyXboxX, XCL, hyphenn, etc.).
    - Return ONLY valid JSON matching this schema:
    {{
      "current_leader": "Exact name of #1 leading project right now",
      "leader_stage": "Furthest milestone reached by leader (e.g. Playable)",
      "leader_score": 59.8,
      "most_active_today": "Project doing the most work in the last 24 hours",
      "ai_summary": "Clear 2-3 sentence executive summary combining PortWatch VI, gta6-pc-race, and GitHub commit data",
      "prediction": "Concrete prediction on who will hit stable playable gameplay first",
      "leaderboard": [
        {{
          "rank": 1,
          "name": "Project Name",
          "stage": "Current milestone stage",
          "progress_pct": 59.8,
          "highest_achievement": "Highest technical milestone achieved",
          "work_today_score": 85,
          "work_today_note": "Summary of today's progress",
          "works": ["Feature 1 working"],
          "known_issues": ["Issue 1"],
          "remaining_stages": ["Rendering", "Performance", "Stability"]
        }}
      ],
      "news_highlights": [
        {{"source": "PortWatch VI / GitHub", "headline": "Short factual update"}}
      ]
    }}
    Include top 4-5 active projects in "leaderboard".
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

    retry_codes = {429, 500, 502, 503, 504}
    delays = [5, 15, 30, 60]
    for attempt in range(len(delays) + 1):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                return json.loads(res["candidates"][0]["content"]["parts"][0]["text"])
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore")
            print(f"Gemini API request failed (model={GEMINI_MODEL}, attempt {attempt + 1}): {e} - {body}")
            if e.code in retry_codes and attempt < len(delays):
                time.sleep(delays[attempt])
                continue
            raise
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"Gemini API network error (attempt {attempt + 1}): {e}")
            if attempt < len(delays):
                time.sleep(delays[attempt])
                continue
            raise
        except Exception as e:
            print(f"Gemini API request failed: {e}")
            raise

if __name__ == "__main__":
    print("Starting GTA VI Port Intel Sync...")
    github_data = get_daily_github_work()
    
    print("Scraping PortWatch VI and gta6-pc-race...")
    portwatch_raw = strip_html(fetch_url("https://portwatch-vi.xyz", is_json=False))
    pc_race_raw = strip_html(fetch_url("https://vuyp.github.io/gta6-pc-race/", is_json=False))

    sources = {
        "portwatch_vi_data": portwatch_raw or "Unavailable during fetch",
        "gta6_pc_race_data": pc_race_raw or "Unavailable during fetch",
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

    history = old_data.get("history", [])
    now_label = datetime.now(timezone.utc).strftime("%H:%M UTC")
    scores = {p["name"]: p["progress_pct"] for p in analysis.get("leaderboard", [])}
    history.append({"time": now_label, "scores": scores})
    history = history[-24:]

    output = {
        "sources": sources,
        "analysis": analysis,
        "history": history,
        "last_updated": datetime.now(timezone.utc).isoformat()
    }

    with open(DATA_FILE, "w") as f:
        json.dump(output, f, indent=2)
    print("Successfully updated data.json!")

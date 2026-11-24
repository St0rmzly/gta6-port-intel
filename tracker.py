import os
import re
import json
import urllib.request
from datetime import datetime, timezone, timedelta

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
DATA_FILE = "data.json"

TRACKED_REPOS = [
    {"name": "VIctory", "repo": "Marvisak/VIctory"},
    {"name": "XCL", "repo": "ivall/xcl"}
]

def fetch_url(url, is_json=True):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GTA6-Intel/3.0"}
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
    return re.sub(r"\s+", " ", clean).strip()[:4500]

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
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    prompt = f"""
    You are an analytical tracker monitoring the entire unofficial GTA VI PC port / Xbox compatibility race.
    Analyze the live data scraped from PortWatch VI (portwatch-vi.xyz), vuyp.github.io/gta6-pc-race, GitHub daily work counts, and Reddit.

    SCRAPED SOURCES:
    {json.dumps(sources)}

    PREVIOUS STATE:
    {json.dumps(old_data.get("analysis") if old_data else None)}

    Rules:
    - Identify the TRUE current overall leader across ALL projects mentioned in the trackers (e.g., CGBJ, VIctory, AnyXboxX, XCL, Palmwave, etc.).
    - Focus on how much real work was done today, technical stage reached, what works, known issues, and AI predictions.
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
          "work_today_score": 85,
          "work_today_note": "Summary of today's progress / commits",
          "works": ["Item 1 that works", "Item 2 that works"],
          "known_issues": ["Main crash/glitch 1"],
          "remaining_todo": "What still needs to be built"
        }}
      ],
      "news_highlights": [
        {{"source": "PortWatch / GitHub", "headline": "Short factual update"}}
      ]
    }}
    Include the top 4-5 active projects in "leaderboard".
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
    with urllib.request.urlopen(req, timeout=35) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        return json.loads(res["candidates"][0]["content"]["parts"][0]["text"])

def send_discord_alert(new_data, old_data):
    if not DISCORD_WEBHOOK:
        return
    new_ai = new_data["analysis"]
    old_ai = old_data.get("analysis", {}) if old_data else {}

    if old_data and old_ai.get("current_leader") == new_ai.get("current_leader") and old_ai.get("ai_summary") == new_ai.get("ai_summary"):
        return

    embed = {
        "title": f"📊 GTA VI Port Intel — Leader: {new_ai['current_leader']} ({new_ai['leader_stage']})",
        "description": new_ai['ai_summary'],
        "color": 3447003,
        "fields": [
            {"name": "🔥 Most Work Today", "value": new_ai.get("most_active_today", "N/A"), "inline": True},
            {"name": "🔮 AI Prediction", "value": new_ai.get("prediction", "N/A"), "inline": False}
        ]
    }
    req = urllib.request.Request(
        DISCORD_WEBHOOK,
        data=json.dumps({"embeds": [embed]}).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "GTA6-Intel-Bot"}
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"Webhook error: {e}")

if __name__ == "__main__":
    old_data = None
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            try:
                old_data = json.load(f)
            except Exception:
                old_data = None

    sources = {
        "vuyp_race_tracker": strip_html(fetch_url("https://vuyp.github.io/gta6-pc-race/", is_json=False)),
        "portwatch_vi": strip_html(fetch_url("https://portwatch-vi.xyz/", is_json=False)),
        "github_24h_work": get_daily_github_work()
    }

    reddit_hits = []
    for sub in ["GTAVI", "Piracy"]:
        r_data = fetch_url(f"https://www.reddit.com/r/{sub}/new.json?limit=10")
        if r_data and "data" in r_data:
            for c in r_data["data"].get("children", []):
                t = c["data"].get("title", "")
                if any(k in t.lower() for k in ["portwatch", "victory", "xcl", "cgbj", "anyxbox", "pc port"]):
                    reddit_hits.append(f"[r/{sub}] {t}")
    sources["reddit"] = reddit_hits[:6]

    analysis = analyze_all_sources(sources, old_data)

    history = old_data.get("history", []) if old_data else []
    now_label = datetime.now(timezone.utc).strftime("%H:%M")
    snapshot = {"time": now_label, "scores": {p["name"]: p["progress_pct"] for p in analysis.get("leaderboard", [])}}
    history.append(snapshot)
    history = history[-24:]

    output = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "github_24h": sources["github_24h_work"],
        "analysis": analysis,
        "history": history
    }

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    send_discord_alert(output, old_data)
    print("Intel sync complete.")

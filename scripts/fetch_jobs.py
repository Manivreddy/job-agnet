"""
fetch_jobs.py
Pulls fresh job postings from FREE, public, ToS-friendly sources:
  - Greenhouse public job boards (no key needed)
  - Lever public job boards (no key needed)
  - RemoteOK public API (no key needed)
  - Adzuna job search API (free tier, needs a free API key - see README)

No scraping / no login-walled sites are touched, so this won't get you
rate-limited or violate site terms of service.

Add/remove companies in COMPANIES_GREENHOUSE / COMPANIES_LEVER below.
Find a company's board slug by visiting:
  https://boards.greenhouse.io/<slug>
  https://jobs.lever.co/<slug>
"""

import json
import os
import time
import requests
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

# --- Configure your target companies here -----------------------------
# Verified as of Aug 2026 - re-check with boards.greenhouse.io/<slug> or
# jobs.lever.co/<slug> occasionally, since companies do switch ATS providers.
COMPANIES_GREENHOUSE = [
    "razorpaysoftwareprivatelimited",  # Razorpay
    "alphasenseindia",                 # AlphaSense India
    "groww",                           # Groww
    "chargebee",                       # Chargebee
    "freshworks",                      # Freshworks
]
COMPANIES_LEVER = [
    "meesho",    # Meesho
    "whatfix",   # Whatfix
    "postman",   # Postman
]

# Keywords used to pre-filter postings before they even reach the matcher
KEYWORDS = [
    "data analyst", "sql", "python", "business intelligence",
    "power bi", "tableau", "data analytics",
]

# Adzuna is optional - only runs if these env vars are set (both free, see README)
ADZUNA_APP_ID = os.environ.get("ADZUNA_APP_ID")
ADZUNA_APP_KEY = os.environ.get("ADZUNA_APP_KEY")
ADZUNA_COUNTRY = "in"  # India; use "gb", "us", etc. for other markets
ADZUNA_QUERIES = ["data analyst", "sql developer", "business intelligence analyst"]


def fetch_greenhouse(slug):
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        jobs = r.json().get("jobs", [])
        out = []
        for j in jobs:
            out.append({
                "source": "greenhouse",
                "company": slug,
                "title": j.get("title", ""),
                "location": (j.get("location") or {}).get("name", ""),
                "url": j.get("absolute_url", ""),
                "description": j.get("content", ""),
                "id": f"greenhouse-{slug}-{j.get('id')}",
            })
        return out
    except Exception as e:
        print(f"  [greenhouse:{slug}] failed: {e}")
        return []


def fetch_lever(slug):
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        jobs = r.json()
        out = []
        for j in jobs:
            out.append({
                "source": "lever",
                "company": slug,
                "title": j.get("text", ""),
                "location": (j.get("categories") or {}).get("location", ""),
                "url": j.get("hostedUrl", ""),
                "description": j.get("descriptionPlain", ""),
                "id": f"lever-{slug}-{j.get('id')}",
            })
        return out
    except Exception as e:
        print(f"  [lever:{slug}] failed: {e}")
        return []


def fetch_remoteok():
    url = "https://remoteok.com/api"
    headers = {"User-Agent": "job-agent-bot (personal use)"}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        jobs = r.json()
        out = []
        for j in jobs:
            if not isinstance(j, dict) or "position" not in j:
                continue  # first element is metadata, skip it
            out.append({
                "source": "remoteok",
                "company": j.get("company", ""),
                "title": j.get("position", ""),
                "location": j.get("location", "Remote"),
                "url": j.get("url", ""),
                "description": j.get("description", ""),
                "id": f"remoteok-{j.get('id')}",
            })
        return out
    except Exception as e:
        print(f"  [remoteok] failed: {e}")
        return []


def fetch_adzuna():
    if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
        print("  [adzuna] skipped (ADZUNA_APP_ID / ADZUNA_APP_KEY not set)")
        return []

    out = []
    for query in ADZUNA_QUERIES:
        url = f"https://api.adzuna.com/v1/api/jobs/{ADZUNA_COUNTRY}/search/1"
        params = {
            "app_id": ADZUNA_APP_ID,
            "app_key": ADZUNA_APP_KEY,
            "results_per_page": 20,
            "what": query,
            "content-type": "application/json",
        }
        try:
            r = requests.get(url, params=params, timeout=15)
            r.raise_for_status()
            results = r.json().get("results", [])
            for j in results:
                out.append({
                    "source": "adzuna",
                    "company": (j.get("company") or {}).get("display_name", "Unknown"),
                    "title": j.get("title", ""),
                    "location": (j.get("location") or {}).get("display_name", ""),
                    "url": j.get("redirect_url", ""),
                    "description": j.get("description", ""),
                    "id": f"adzuna-{j.get('id')}",
                })
        except Exception as e:
            print(f"  [adzuna:{query}] failed: {e}")
        time.sleep(0.5)
    return out


def keyword_prefilter(jobs):
    filtered = []
    for j in jobs:
        haystack = f"{j['title']} {j['description']}".lower()
        if any(k in haystack for k in KEYWORDS):
            filtered.append(j)
    return filtered


def dedupe(jobs):
    seen = set()
    out = []
    for j in jobs:
        if j["id"] in seen:
            continue
        seen.add(j["id"])
        out.append(j)
    return out


def main():
    all_jobs = []

    print("Fetching Greenhouse boards...")
    for slug in COMPANIES_GREENHOUSE:
        all_jobs.extend(fetch_greenhouse(slug))
        time.sleep(0.5)

    print("Fetching Lever boards...")
    for slug in COMPANIES_LEVER:
        all_jobs.extend(fetch_lever(slug))
        time.sleep(0.5)

    print("Fetching RemoteOK...")
    all_jobs.extend(fetch_remoteok())

    print("Fetching Adzuna...")
    all_jobs.extend(fetch_adzuna())

    all_jobs = dedupe(all_jobs)
    print(f"Fetched {len(all_jobs)} raw postings")
    filtered = keyword_prefilter(all_jobs)
    print(f"{len(filtered)} postings after keyword pre-filter")

    DATA_DIR.mkdir(exist_ok=True)
    out_path = DATA_DIR / "raw_jobs.json"
    out_path.write_text(json.dumps(filtered, indent=2))
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()

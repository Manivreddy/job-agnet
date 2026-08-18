"""
match_jobs.py
Scores each fetched job posting against your resume profile using
keyword/skill overlap. This is intentionally free (no LLM call) so
you can run it as often as you want - the LLM is only used later,
in tailor_resume.py, and only for jobs that pass this filter.
"""

import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
MIN_SCORE = 3          # minimum overlap points to be considered a match
TOP_N = 10              # cap how many jobs get sent to the (paid) tailoring step


def load_json(path):
    return json.loads(Path(path).read_text())


def tokenize(text):
    return set(re.findall(r"[a-zA-Z][a-zA-Z0-9+#.]{1,}", text.lower()))


def score_job(job, profile):
    text = f"{job['title']} {job['description']}"
    tokens = tokenize(text)

    score = 0
    matched_skills = []
    for skill in profile["core_skills"]:
        if skill.lower() in tokens or skill.lower() in text.lower():
            score += 2
            matched_skills.append(skill)
    for skill in profile["secondary_skills"]:
        if skill.lower() in text.lower():
            score += 1
            matched_skills.append(skill)
    for title in profile["target_titles"]:
        if title.lower() in job["title"].lower():
            score += 3

    # Penalize obviously senior roles for a fresher profile
    if profile["seniority"] == "entry-level / fresher":
        senior_flags = ["senior", "staff", "principal", "lead ", "10+ years", "8+ years"]
        if any(f in text.lower() for f in senior_flags):
            score -= 4

    return score, matched_skills


def main():
    jobs = load_json(DATA_DIR / "raw_jobs.json")
    profile = load_json(DATA_DIR / "resume_profile.json")

    scored = []
    for job in jobs:
        s, matched = score_job(job, profile)
        if s >= MIN_SCORE:
            job["match_score"] = s
            job["matched_skills"] = matched
            scored.append(job)

    scored.sort(key=lambda j: j["match_score"], reverse=True)
    top = scored[:TOP_N]

    out_path = DATA_DIR / "matched_jobs.json"
    out_path.write_text(json.dumps(top, indent=2))
    print(f"{len(scored)} jobs passed the threshold, kept top {len(top)}")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()

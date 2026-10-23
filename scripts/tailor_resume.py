"""
tailor_resume.py
For each job in matched_jobs.json, asks Gemini to rewrite the resume's
summary + bullet points to fit that job, WITHOUT inventing experience.
Writes one .docx per job.

If the AI step fails for a job, the job is STILL saved to final_results.json
(without a tailored resume) so it shows up on the dashboard.

Requires: pip install requests python-docx
Requires env var: GEMINI_API_KEY (free key: https://aistudio.google.com/apikey)
"""

import json
import os
import time
from pathlib import Path

import requests
from docx import Document
from docx.shared import Pt

DATA_DIR = Path(__file__).parent.parent / "data"
OUT_DIR = Path(__file__).parent.parent / "tailored_resumes"

# Tried in order. Google retires models often (gemini-2.0-flash died June 1 2026,
# gemini-2.5-flash was scheduled for Oct 16 2026), so keep a fallback list.
GEMINI_MODELS = ["gemini-flash-latest", "gemini-3.5-flash", "gemini-3-flash-preview"]
_working_model = None

SYSTEM_PROMPT = """You tailor resumes. You NEVER invent skills, employers, dates, \
degrees, or achievements that are not present in the candidate's original resume \
profile. You may only: reorder bullets, rephrase bullets to mirror the job \
description's language, and rewrite the summary to foreground the most relevant \
existing skills. Output strict JSON matching the schema you're given, nothing else - \
no markdown fences, no commentary."""

USER_PROMPT_TEMPLATE = """CANDIDATE RESUME PROFILE (source of truth - do not add anything not in here):
{profile_json}

JOB POSTING:
Title: {job_title}
Company: {company}
Description:
{job_description}

Return ONLY valid JSON with this exact schema:
{{
  "summary": "2-3 sentence tailored summary",
  "highlighted_skills": ["skill1", "skill2"],
  "experience_bullets": ["rewritten bullet 1", "rewritten bullet 2"],
  "project_bullets": ["rewritten bullet 1", "rewritten bullet 2"],
  "why_matched": "1 sentence explaining the fit, for your own review"
}}
"""


def call_gemini(api_key, profile, job, retries=3):
    global _working_model
    prompt = USER_PROMPT_TEMPLATE.format(
        profile_json=json.dumps(profile),
        job_title=job["title"],
        company=job["company"],
        job_description=job["description"][:4000],
    )
    body = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 2000,
            "responseMimeType": "application/json",
        },
    }

    models = [_working_model] if _working_model else GEMINI_MODELS
    last_err = None
    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        for attempt in range(retries):
            try:
                resp = requests.post(url, params={"key": api_key}, json=body, timeout=60)
                if resp.status_code == 429:
                    wait = 15 * (attempt + 1)
                    print(f"  [{model}] rate limited, waiting {wait}s...")
                    time.sleep(wait)
                    last_err = f"{model}: HTTP 429 {resp.text[:200]}"
                    continue
                if resp.status_code in (400, 403, 404):
                    last_err = f"{model}: HTTP {resp.status_code} {resp.text[:300]}"
                    print(f"  [{model}] unusable -> {last_err}")
                    break  # try the next model
                resp.raise_for_status()
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                result = json.loads(text)
                _working_model = model
                return result
            except Exception as e:
                last_err = f"{model}: {e}"
                time.sleep(2)
    raise RuntimeError(f"All Gemini models failed. Last error: {last_err}")


def build_docx(profile, tailored, job, out_path):
    doc = Document()
    style = doc.styles["Normal"]
    style.font.size = Pt(10.5)

    doc.add_heading(profile["name"], level=1)
    doc.add_paragraph(f"{profile['phone']} | {profile['email']} | {profile['linkedin']}")

    doc.add_heading("Summary", level=2)
    doc.add_paragraph(tailored["summary"])

    doc.add_heading("Skills", level=2)
    doc.add_paragraph(", ".join(tailored["highlighted_skills"]))

    doc.add_heading("Experience", level=2)
    for exp in profile["experience"]:
        doc.add_paragraph(f"{exp['title']} - {exp['org']} ({exp['dates']})", style="Intense Quote")
        for b in tailored["experience_bullets"]:
            doc.add_paragraph(b, style="List Bullet")

    doc.add_heading("Projects", level=2)
    for proj in profile["projects"]:
        doc.add_paragraph(f"{proj['title']} ({proj['dates']})", style="Intense Quote")
    for b in tailored["project_bullets"]:
        doc.add_paragraph(b, style="List Bullet")

    doc.add_heading("Education", level=2)
    for edu in profile["education"]:
        doc.add_paragraph(f"{edu['degree']}, {edu['institution']} ({edu['dates']}) - {edu['score']}")

    doc.add_heading("Certifications", level=2)
    for c in profile["certifications"]:
        doc.add_paragraph(c, style="List Bullet")

    doc.save(out_path)


def main():
    profile = json.loads((DATA_DIR / "resume_profile.json").read_text())
    jobs = json.loads((DATA_DIR / "matched_jobs.json").read_text())
    print(f"{len(jobs)} matched jobs to process")

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        print("WARNING: GEMINI_API_KEY is not set - jobs will be listed without tailored resumes")

    OUT_DIR.mkdir(exist_ok=True)

    results = []
    tailored_count = 0
    for job in jobs:
        print(f"Tailoring for: {job['title']} @ {job['company']}")
        try:
            if not api_key:
                raise RuntimeError("no API key")
            tailored = call_gemini(api_key, profile, job)
            docx_path = OUT_DIR / f"{job['id'].replace('/', '-')}.docx"
            build_docx(profile, tailored, job, docx_path)
            job["tailored"] = tailored
            job["tailored_resume_file"] = docx_path.name
            tailored_count += 1
            time.sleep(4)  # stay under free-tier rate limits
        except Exception as e:
            print(f"  tailoring failed: {e}")
            job["tailored"] = {
                "why_matched": "Tailored resume unavailable for this job (AI step failed). "
                               "Matched on skills: " + ", ".join(job.get("matched_skills", []))
            }
            job["tailored_resume_file"] = None
        results.append(job)

    (DATA_DIR / "final_results.json").write_text(json.dumps(results, indent=2))
    print(f"Done. {len(results)} jobs saved, {tailored_count} with tailored resumes.")


if __name__ == "__main__":
    main()

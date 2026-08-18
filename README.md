# Daily job-match & resume-tailoring agent

Runs once a day, for free, and gives you a dashboard of matched jobs with a
tailored resume ready to download for each one. You review and click through
to apply on the company's own site — nothing auto-submits.

## How it works

```
fetch_jobs.py   -> pulls new postings from Greenhouse / Lever / RemoteOK (free, public APIs)
match_jobs.py   -> scores them against your resume with keyword overlap (free, no API call)
tailor_resume.py -> for the top ~10 matches only, asks Claude to rewrite your
                     summary/bullets to fit that job, then builds a .docx
dashboard/      -> a static page you open to review everything and click "apply"
```

Only the tailoring step costs money, and only runs on jobs that already
passed the free filter — so a normal day is ~5–10 short Claude calls.

## Cost breakdown

| Piece | Cost |
|---|---|
| Job fetching (Greenhouse/Lever/RemoteOK APIs) | Free, no key needed |
| Matching/scoring | Free, runs locally, no API call |
| Daily scheduling (GitHub Actions) | Free (public repos get 2,000 min/month; this job uses ~2 min/day) |
| Dashboard hosting (GitHub Pages) | Free |
| Resume tailoring (Gemini 2.0 Flash, free tier) | **$0** |

Everything here is $0. The trade-off: Gemini's free tier has a daily
request-count cap (comfortably above the ~10 tailoring calls/day this
does) and Google may use free-tier traffic to help improve their models —
that's the usual trade for "free," and it's a different trade than the
paid Claude API, which doesn't train on your data. If that matters to you,
you can point `tailor_resume.py` at a paid model later; the rest of the
pipeline doesn't change either way.

## What this does NOT do (and why)

- **It will not auto-submit applications.** Most job sites (LinkedIn, Indeed,
  Workday-based portals) prohibit automated submission in their terms of
  service, and their bot-detection would likely just break the flow or flag
  your account. The dashboard gets you one click from applying — you do the
  actual submit.
- **It doesn't scrape LinkedIn/Indeed directly.** Those require login and
  scraping them breaks ToS. Instead it pulls from Greenhouse and Lever, which
  are the actual applicant-tracking systems many companies (including ones
  that also post to LinkedIn) use, and expose free public job APIs.
- **It won't invent experience.** The tailoring prompt explicitly restricts
  Claude to rephrasing/reordering your real bullets, not adding skills or
  jobs you didn't do.

## Setup (about 15 minutes, one time)

1. **Create a free GitHub account** if you don't have one.
2. **Create a new repository** and upload all these files to it.
3. **Get a free Gemini API key**: aistudio.google.com/apikey → Create API
   key. No payment details needed for the free tier.
4. **Add the key as a repo secret**: repo → Settings → Secrets and variables
   → Actions → New repository secret → name it `GEMINI_API_KEY`.
5. **Enable GitHub Pages**: repo → Settings → Pages → Source → "GitHub
   Actions".
6. **Edit `scripts/fetch_jobs.py`**: swap the example companies in
   `COMPANIES_GREENHOUSE` / `COMPANIES_LEVER` for ones you actually want to
   target. (Find a company's slug by checking if
   `boards.greenhouse.io/<slug>` or `jobs.lever.co/<slug>` resolves.)
7. **Edit `data/resume_profile.json`** — I generated this from your uploaded
   resume; double check it, and fill in your real LinkedIn URL.
8. Commit. The workflow runs automatically every day at 9am IST (edit the
   `cron` line in `.github/workflows/daily.yml` to change the time), and you
   can also trigger it manually anytime from the repo's Actions tab.
9. Your dashboard will be live at `https://<your-username>.github.io/<repo-name>/dashboard/`.

## Running it locally instead (no GitHub needed)

If you'd rather not use GitHub Actions, you can run it manually whenever you want:

```bash
pip install requests python-docx
export GEMINI_API_KEY=your_key_here
python scripts/fetch_jobs.py
python scripts/match_jobs.py
python scripts/tailor_resume.py
open dashboard/index.html   # or just double-click it
```

## Extending it

- **More job sources**: add more Greenhouse/Lever company slugs, or plug in
  a free tier from Adzuna or USAJobs for broader coverage.
- **Better matching**: swap the keyword scorer in `match_jobs.py` for an
  embedding-similarity score if keyword matching feels too blunt.
- **Notifications**: add a step to the workflow that emails you or posts to
  Slack/Discord when new matches land, instead of only checking the dashboard.

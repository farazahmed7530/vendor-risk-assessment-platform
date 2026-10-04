# Vendor Risk Assessment Platform

Send security questionnaires to your vendors, score the responses, and **show how every
score was arrived at**.

**FastAPI + Next.js.** Two user types — your security team, and the vendor. Runs with no setup.

---

## The problem

Before you let a supplier touch customer data, someone has to ask them whether they encrypt
it. In most companies that process is a spreadsheet emailed back and forth, and it fails in
three specific ways:

1. **Vendors will not create an account** to answer your questionnaire. Any flow that starts
   with "sign up" ends with a PDF attached to a reply-all.
2. **The score cannot be explained.** A vendor told they scored 69 will ask why. "The model
   said so" is not an answer when a renewal is at stake.
3. **Last year's score cannot be reproduced.** Someone tweaks a weight, and the number you
   reported to the board quietly changes.

Each of those is a design decision, not a feature.

## The three decisions

### 1. Vendors have no accounts

Each assessment carries a long random token. The vendor gets a link containing it, and that
token resolves to exactly one assessment — nothing to sign up for, no password to reset, no
account to deprovision afterwards.

Internal routes (`/api/vendors/...`) and vendor routes (`/api/portal/{token}`) share no path
prefix, so there is no way to drift into exposing one through the other.

**The questionnaire is sent stripped of its scoring.** A vendor who can see that "No" scores
90 is being invited to answer the scoring rather than the question. There is a test asserting
the string `"risk"` never appears in a portal response.

### 2. Scoring shows its working

```
question risk    0–100, from the chosen answer option
section score    weighted mean of that section's answered questions
inherent risk    weighted mean across sections
residual risk    inherent risk × how much damage this vendor could do
```

A real result from the seeded data:

```
inherent 46.0 × critical multiplier 1.5 = residual 69.0 (high)

Certifications 55.0 · Access Control 70.0 · Data Protection 27.1
Incident Response 56.0 · Resilience 5.0

top contributors
  270.0  Is MFA enforced for all staff with production access?  → No
  150.0  Will you notify customers of a breach within 72 hours? → Best effort
  140.0  Is an independent penetration test carried out?        → No
```

The criticality multiplier is explicit rather than buried, because it is the part people
argue about: a careless vendor who touches nothing important is a smaller problem than a
careless vendor holding your customer database.

**Unanswered questions are reported, never assumed.** Treating a blank as worst-case would be
a silent judgement. Same for an answer that is not one of the offered options.

### 3. An assessment snapshots its questionnaire

Templates get edited — questions reworded, weights tuned. If an assessment pointed at a live
template, last year's risk score would change whenever someone adjusted a weight.

So the questionnaire definition is **copied into the assessment** when it is sent, and frozen
there. A score reported last quarter still reproduces today.

## What it does

**Security team** — a risk matrix bucketed low / moderate / high / critical, a vendor list
with residual scores, one-click link generation, and a scoring breakdown that shows section
scores, the multiplier applied, and the answers contributing most to the result.

**Vendor** — a plain questionnaire grouped by section, with optional notes per answer, that
saves incrementally. Vendors fill these in over days, usually after asking three colleagues,
so saving and submitting are separate and deliberate steps.

## Running it

**Backend** (Python 3.9+)

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Seeds a ten-question security questionnaire and three vendors with live assessments.
API docs at `http://localhost:8000/docs`.

**Frontend** (Node 18+)

```bash
cd frontend
npm install
npm run dev
```

`http://localhost:3000` — dashboard. Copy a vendor link from any card to see the external
side at `/vendor/{token}`.

**Tests**

```bash
cd backend && .venv/bin/python -m pytest tests -q
```

**Postgres**

```bash
export DATABASE_URL=postgresql://user:pass@localhost:5432/vendors
```

## API

| Method | Path | Who |
|---|---|---|
| `GET` | `/api/vendors` | internal — vendors with latest scores |
| `POST` | `/api/vendors` | internal — add a vendor |
| `POST` | `/api/vendors/{id}/assessments` | internal — send, snapshotting the questionnaire |
| `GET` | `/api/vendors/{id}/assessments/{aid}` | internal — responses and full scoring breakdown |
| `GET` | `/api/portal/{token}` | vendor — open the questionnaire |
| `POST` | `/api/portal/{token}` | vendor — save progress, or submit |

## Tests

Eleven, aimed at what would actually hurt:

```
scoring     weighting changes the score · criticality scales residual but not inherent
            residual is capped at 100 · unanswered reported not assumed
            unrecognised answers are not silently scored · top risks ordered correctly
portal      option risk values never reach the vendor  ← the one that matters
            a token resolves only to its own assessment · invalid tokens rejected
            answers save incrementally, submit is refused while incomplete, no double submit
snapshot    editing the questionnaire does not change an assessment already sent
```

## A note on authentication

The internal routes have none — this is a portfolio project and adding half an auth system
would be surface without insight. In production the internal side sits behind SSO; the vendor
side stays tokenised, because that is the right answer there regardless.

Tokens here never expire. Production would give them a lifetime and a rotation path.

## What I would add next

- **Evidence upload** — the schema has the column; storage is the missing half.
- **Reassessment cadence** — annual re-send, driven by criticality.
- **Reviewer overrides** with a reason, so a human can disagree with the score on record.
- **Diffing between assessments** — what got better or worse since last year.
- **Export to PDF**, which is what actually gets attached to a board paper.

## Licence

MIT

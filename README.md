# cicd-autopsy

A multi-agent system that investigates CI/CD failures automatically.
Given a failed GitHub Actions run, it classifies the failure type,
identifies the likely responsible source file(s), suggests a fix,
generates a structured report, and can open a GitHub issue with the
findings.

Built and evaluated against [taskhub-api](#), a small repo with 18
intentionally-broken commits across 6 known failure categories, used
as a labeled eval dataset (see that repo's `FAILURE_MATRIX.md` for
the ground truth). This repo is designed to work against ANY GitHub
repo, not just that one -- the target repo is passed as a parameter,
not hardcoded.

## Architecture

Six agents, wired as a LangGraph pipeline:

1. **Workflow Monitor** -- finds a failed GitHub Actions run, downloads
   its logs, detects the repo's tech stack.
2. **Failure Analyzer** -- classifies the failure into one of six
   categories (Dependency, Test, Configuration, Database,
   Infrastructure, Build) and explains the root cause.
3. **Repository Investigator** -- guesses likely responsible files,
   then fetches their real content from GitHub to confirm or correct
   the guess (grounded in actual file text, not assumptions).
4. **Fix Recommendation Agent** -- generates a specific, actionable
   fix with a confidence score.
5. **Report Generator** -- assembles everything into a Markdown report
   and a JSON summary.
6. **GitHub Issue Creator** -- opens a real issue with the report
   (skips automatically if classification confidence is too low).

## Stack

- LangGraph for agent orchestration
- Groq (Llama 3.3 70B) for the LLM reasoning steps -- free tier
- PyGithub + requests for the GitHub API
- SQLite for storing investigation history (Postgres-ready later --
  just change `DATABASE_URL`)
- Pydantic for the shared state model passed between agents

## Setup

```bash
cp .env.example .env
# fill in GITHUB_TOKEN and GROQ_API_KEY
pip install -r requirements.txt
```

## Usage

Investigate the latest failed run on a specific branch:
```bash
python -m app.run_investigation --owner <owner> --repo <repo> --branch <branch>
```

Investigate a specific run by ID:
```bash
python -m app.run_investigation --owner <owner> --repo <repo> --run-id <id>
```

By default, issue creation runs in dry-run mode (prints what it would
post, doesn't actually create anything). Add `--create-issue` to
actually open a real GitHub issue.

## Evaluation

Scores the investigator against taskhub-api's 18 labeled failures:
```bash
python -m eval.run_eval --owner <owner> --repo Taskhub-api
```

Outputs category accuracy, file-retrieval accuracy, and a confusion
matrix across the six failure categories, written to
`eval_results.json`.

Note: this makes 18+ real Groq and GitHub API calls. Test the
pipeline on 1-2 branches individually first via
`app.run_investigation` before running the full eval.

# SpringBoot PR Review Agent

## What this is
GitHub Action. Reviews Java/SpringBoot PRs using 3 parallel AI agents.
Users add one workflow file + one repo secret. No server, no webhook.

## Stack
Python 3.11 · LangGraph · Anthropic Claude API · PyGithub · GitHub Actions

## How it runs
GitHub triggers action/main.py → reads env vars → LangGraph graph → posts PR comment.
No FastAPI. No webhook. Entry point is action/main.py only.

## Layout
```
action/main.py           ← entry point, reads GitHub env vars, calls orchestrator
app/config.py            ← all env var loading
app/tools/github.py      ← fetch_diff, post_review, load_review_rules (PyGithub only)
app/tools/java_parser.py ← extract annotations/signals from diff text
app/agents/
  orchestrator.py        ← LangGraph StateGraph, parallel fan-out
  code_agent.py          ← SpringBoot patterns, JPA, transactions, naming
  security_agent.py      ← secrets, Spring Security, OWASP, injection
  test_agent.py          ← JUnit coverage, assertions, SpringBootTest overuse
  synthesiser.py         ← deduplicate, verdict, format PR comment
action.yml               ← GitHub Action interface
REVIEW_RULES.md          ← loaded per-PR, user-customisable
docs/architecture.md     ← design decisions and data flow
docs/java-rules.md       ← all rules (source of truth for agent prompts)
tests/tools/             ← unit tests for github.py and java_parser.py
eval_set/                ← known-bad PR diffs for regression testing
scripts/eval.py          ← runs eval suite, reports precision/recall
```

## Coding rules
- All LLM calls inside LangGraph nodes only — never outside the graph
- Tools are plain Python functions — no @tool decorator needed
- Agent system prompts are module-level string constants in each agent file
- All data between agents uses TypedDict — never raw dicts or strings
- github.py is the only file that imports PyGithub
- Agents use claude-haiku-4-5, synthesiser uses claude-sonnet-4-6
- Max diff: 5000 lines — larger PRs get file-list-only mode

## Env vars (GitHub Actions injects these automatically)
```
GITHUB_TOKEN             # auto by GitHub Actions
GITHUB_REPOSITORY        # e.g. owner/repo
PR_NUMBER                # from github.event.pull_request.number
PR_TITLE                 # from github.event.pull_request.title
PR_BASE_SHA
PR_HEAD_SHA
ANTHROPIC_API_KEY        # from action with: block → secrets.ANTHROPIC_API_KEY
MODEL_CODE               # default: claude-haiku-4-5
MODEL_SYNTH              # default: claude-sonnet-4-6
MAX_DIFF_LINES           # default: 5000
POST_COMMENT             # default: true (set false for dry-run)
```

## Commands
```bash
pip install -r requirements.txt
python -m pytest tests/ -v
python scripts/eval.py
POST_COMMENT=false python action/main.py   # local dry-run
```

## Finding TypedDict schema
```python
{
  "severity": "critical|high|medium|low|suggestion",
  "file": str,       # e.g. "src/main/java/UserService.java"
  "line": str,       # line number or "unknown"
  "rule": str,       # e.g. "no-field-injection"
  "message": str,    # what is wrong and why, 1-2 sentences
  "suggestion": str, # concrete fix
  "agent": str       # "code" | "security" | "test"
}
```

## Build order (follow this exactly)
1. requirements.txt + .gitignore + app/__init__.py stubs
2. app/config.py
3. app/tools/github.py + app/tools/java_parser.py
4. action/main.py + action.yml
5. app/agents/orchestrator.py (single node first, then split to parallel)
6. app/agents/code_agent.py
7. app/agents/security_agent.py
8. app/agents/test_agent.py
9. app/agents/synthesiser.py
10. tests/tools/test_github.py + tests/tools/test_java_parser.py
11. eval_set/001-field-injection/ + scripts/eval.py
12. README.md

After step 4: verify end-to-end works with POST_COMMENT=false before continuing.
Use @docs/java-rules.md when writing code_agent or security_agent prompts.
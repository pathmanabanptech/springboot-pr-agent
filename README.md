# springboot-pr-agent

> Automated code review for Java/SpringBoot pull requests — runs as a GitHub Action, posts findings as a PR comment, and can block merges on critical issues.

![Python 3.11](https://img.shields.io/badge/python-3.11-blue)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-green)
![LLM](https://img.shields.io/badge/LLM-Anthropic%20%7C%20OpenAI%20%7C%20Google%20%7C%20HuggingFace-purple)

---

## What it does

- Triggers automatically on every `pull_request` opened or updated in your repo
- Reviews the diff for SpringBoot-specific issues: field injection, N+1 queries, hardcoded credentials, missing tests, CSRF disabled, swallowed exceptions, and more
- Posts a structured review comment with severity-ranked findings and concrete fix suggestions
- Exits with code 1 on critical findings — pair with branch protection rules to block the merge
- Works with any LLM provider: Anthropic, OpenAI, Google Gemini, or HuggingFace

---

## Architecture

```
GitHub PR opened / synchronize
  └─► GitHub Actions runner (ubuntu-latest)
        └─► action/main.py
              ├─ Config.from_env()           read env vars injected by the runner
              └─ run_review(config)          LangGraph graph
                    │
                    ├─ fetch_node
                    │     github.fetch_pr_diff()        → DiffContext
                    │     java_parser.extract_signals()  → {file: signals}
                    │
                    ├─ review_node
                    │     load_review_rules()            → REVIEW_RULES.md contents
                    │     LLM via provider (diff+signals)→ list[Finding]
                    │
                    ├─ synthesise_node
                    │     determine verdict
                    │     format markdown PR comment
                    │
                    └─ post_node
                          github.post_review_comment()
                          exit 0 (APPROVE / REQUEST_CHANGES)
                          exit 1 (BLOCK) ← fails the Action
```

---

## How it works

### Nodes

| Node | What it does |
|---|---|
| `fetch_node` | Fetches the PR diff via PyGithub. Scans each file for Spring annotations (`@Autowired`, `@Transactional`, `@Entity`, etc.) and builds a signal summary injected into the prompt. Stops at `MAX_DIFF_LINES` and sets `truncated=True`. |
| `review_node` | Sends the diff + annotation signals + your team's `REVIEW_RULES.md` to the configured LLM provider (Anthropic / OpenAI / Google / HuggingFace). Parses the returned JSON array into typed `Finding` objects. |
| `synthesise_node` | Picks a verdict from the worst severity found. Formats a markdown comment with findings grouped by severity. |
| `post_node` | Calls `pr.create_review()` via PyGithub. Skipped when `POST_COMMENT=false` (dry-run). |

### Verdict logic

| Worst severity in findings | Verdict | GitHub review event |
|---|---|---|
| `critical` | BLOCK | `REQUEST_CHANGES` + Action exits 1 |
| `high` or `medium` | REQUEST_CHANGES | `REQUEST_CHANGES` |
| `low`, `suggestion`, or none | APPROVE | `APPROVE` |

### Large diffs

If the diff exceeds `MAX_DIFF_LINES` (default 5000), the agent reviews only the files that fit and adds a truncation warning to the PR comment.

---

## Project layout

```
springboot-pr-agent/
├── action/
│   └── main.py              Entry point — loads config, runs graph, exits 0 or 1
├── action.yml               GitHub Action interface (inputs, env wiring, steps)
├── app/
│   ├── config.py            Config dataclass + from_env() — all env var loading lives here
│   ├── llm.py               LLM provider factory — get_llm() returns the right BaseChatModel
│   ├── agents/
│   │   └── orchestrator.py  LangGraph StateGraph, Finding + AgentState TypedDicts
│   └── tools/
│       ├── github.py        fetch_pr_diff, post_review_comment, load_review_rules
│       └── java_parser.py   extract_signals — Spring annotation scanner
├── tests/
│   ├── test_llm.py              Provider dispatch + unknown-provider error tests
│   └── tools/
│       ├── test_github.py       Unit tests for github.py (mocked PyGithub)
│       └── test_java_parser.py  Unit tests for java_parser.py
├── REVIEW_RULES.md          Default team rules — copy to your repo and customise
├── docs/
│   ├── architecture.md      Design decisions and data flow
│   └── java-rules.md        All rules enforced by the agent (source of truth)
└── requirements.txt
```

---

## Local setup

### 1. Clone and install

```bash
git clone https://github.com/your-username/springboot-pr-agent.git
cd springboot-pr-agent
pip3 install -r requirements.txt
```

### 2. Create a `.env` file

```bash
# ── Always required ────────────────────────────────────────────────────────────
GITHUB_TOKEN=ghp_xxxxxxxxxxxx        # github.com/settings/tokens → repo scope
GITHUB_REPOSITORY=owner/repo         # repo containing the PR, e.g. acme/api-service

MODEL_PROVIDER=anthropic             # anthropic | openai | google | huggingface
LLM_API_KEY=sk-ant-xxxx             # API key for your chosen provider (see section below)
# Note: ANTHROPIC_API_KEY is also accepted as a fallback if LLM_API_KEY is not set

# ── Local dry-run only (GitHub Actions injects these automatically) ─────────────
PR_NUMBER=42                         # number of an open PR in GITHUB_REPOSITORY
PR_TITLE=My feature branch           # title of that PR

# ── Optional — sensible defaults apply ────────────────────────────────────────
MODEL_CODE=claude-haiku-4-5          # model name for your provider  (default: claude-haiku-4-5)
MODEL_SYNTH=claude-sonnet-4-6        # synthesiser model             (default: claude-sonnet-4-6)
MAX_DIFF_LINES=5000                  # truncate diffs larger than this (default: 5000)
POST_COMMENT=false                   # set true to post to GitHub    (default: true)
```

> **When running via GitHub Actions:** `PR_NUMBER`, `PR_TITLE`, `PR_BASE_SHA`, and `PR_HEAD_SHA`
> are all injected automatically by the runner from `github.event.pull_request.*` — you never
> set these in your workflow file. They are only needed in `.env` for local runs.

> Never commit `.env` — it is already in `.gitignore`.

### 3. Dry-run (prints the comment, does not post to GitHub)

```bash
POST_COMMENT=false python3 action/main.py
```

Example output:

```
[dry-run] Would post comment:
## ⚠️ PR Review — Changes requested

**3 finding(s)** across 2 file(s).

### 🔴 High (2)

**`no-field-injection`** — src/UserService.java:4
Use constructor injection. Field injection hides dependencies and breaks testability.
> **Fix:** Add a constructor that accepts UserRepository as a parameter and remove @Autowired from the field.

...
verdict=REQUEST_CHANGES findings=3
```

### 4. Full run (posts a real review comment to the PR)

```bash
POST_COMMENT=true python3 action/main.py
```

### 5. Test with a fake diff (no GitHub token or PR required)

Only `LLM_API_KEY` is needed:

```python
# test_local.py
import os
from dotenv import load_dotenv
load_dotenv()

from app.config import Config
from app.tools.github import DiffContext
from app.tools.java_parser import extract_signals
from app.agents.orchestrator import _review_node, AgentState

fake_diff = """--- src/UserService.java
+@Service
+public class UserService {
+    @Autowired
+    private UserRepository repo;
+    public List findAll() {
+        System.out.println("debug");
+        return repo.findAll();
+    }
+}"""

config = Config(
    github_token="unused", github_repository="unused", pr_number=1,
    pr_title="Test", llm_api_key=os.environ["LLM_API_KEY"],
    model_provider=os.getenv("MODEL_PROVIDER", "anthropic"),
    post_comment=False,
)
diff = DiffContext(repo="x", pr_number=1, title="Test",
                   diff_text=fake_diff, files=["src/UserService.java"], truncated=False)
state = AgentState(config=config, diff=diff,
                   java_signals=extract_signals(fake_diff),
                   findings=[], verdict="", comment_body="", findings_count=0)

result = _review_node(state)
for f in result["findings"]:
    print(f["severity"].upper(), "|", f["rule"], "|", f["message"])
```

```bash
python3 test_local.py
```

---

## Choosing an LLM provider

Set `MODEL_PROVIDER` and `LLM_API_KEY` in your `.env` (local) or as secrets in your workflow (GitHub Actions).

| Provider | `MODEL_PROVIDER` value | Key source |
|---|---|---|
| Anthropic (default) | `anthropic` | console.anthropic.com/keys |
| OpenAI | `openai` | platform.openai.com/api-keys |
| Google Gemini | `google` | aistudio.google.com/apikey |
| HuggingFace | `huggingface` | huggingface.co/settings/tokens |

---

## Running tests

```bash
python3 -m pytest tests/ -v
```

```
tests/test_llm.py::test_unknown_provider_raises               PASSED
tests/test_llm.py::test_provider_name_is_case_insensitive     PASSED
tests/test_llm.py::test_anthropic_provider                    PASSED
tests/test_llm.py::test_openai_provider                       PASSED
tests/test_llm.py::test_google_provider                       PASSED
tests/test_llm.py::test_huggingface_provider                  PASSED
tests/tools/test_github.py::test_fetch_pr_diff_basic          PASSED
tests/tools/test_github.py::test_fetch_pr_diff_truncates_...  PASSED
tests/tools/test_github.py::test_fetch_pr_diff_skips_...      PASSED
tests/tools/test_github.py::test_post_review_comment_approve  PASSED
tests/tools/test_github.py::test_post_review_comment_block_.. PASSED
tests/tools/test_github.py::test_post_review_comment_...      PASSED
tests/tools/test_github.py::test_load_review_rules_...        PASSED
tests/tools/test_github.py::test_load_review_rules_none_...   PASSED
tests/tools/test_java_parser.py::test_extract_signals_...     PASSED
...
21 passed in 1.05s
```

| File | What is tested |
|---|---|
| `tests/test_llm.py` | Provider factory dispatch for all 4 providers, unknown-provider `ValueError`, case-insensitive provider name |
| `tests/tools/test_github.py` | Diff fetching, line truncation, binary file skipping, review event mapping (`BLOCK` → `REQUEST_CHANGES`), 404 handling for `REVIEW_RULES.md` |
| `tests/tools/test_java_parser.py` | Annotation detection for `@Service`, `@Autowired`, `@Entity`, `@PreAuthorize`, `@SpringBootTest`, `@MockBean`; empty diff; files with no annotations |

---

## Wiring into your GitHub repo

Create `.github/workflows/pr-review.yml` in the repo you want reviewed:

```yaml
name: PR Review
on:
  pull_request:
    types: [opened, synchronize]

jobs:
  review:
    runs-on: ubuntu-latest
    permissions:
      pull-requests: write   # required to post the review comment
    steps:
      - uses: your-github-username/springboot-pr-agent@main
        with:
          llm-api-key: ${{ secrets.LLM_API_KEY }}
          model-provider: anthropic          # or openai | google | huggingface
          # github-token defaults to ${{ github.token }} — no extra secret needed
          # PR_NUMBER, PR_TITLE, PR_BASE_SHA, PR_HEAD_SHA are injected automatically
```

> **Backward compat:** If you previously used `anthropic-api-key`, it still works — no migration needed.
> ```yaml
> - uses: your-github-username/springboot-pr-agent@main
>   with:
>     anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}   # legacy — still accepted
> ```

Add the secret in the target repo: **Settings → Secrets and variables → Actions → New repository secret**
- Name: `LLM_API_KEY` (or `ANTHROPIC_API_KEY` for legacy)
- Value: your API key for the chosen provider

To block merges on critical findings: **Settings → Branches → Add branch protection rule → Require status checks to pass → select the `review` job**.

---

## Customising rules for your team

Copy `REVIEW_RULES.md` from this repo to the root of the repo being reviewed:

```bash
cp REVIEW_RULES.md /path/to/your-springboot-repo/REVIEW_RULES.md
```

Edit it freely. The agent fetches it on every PR and injects its contents into the review prompt alongside the built-in rules. If the file is absent, only the built-in rules apply. No code changes needed.


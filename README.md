# springboot-pr-agent

> Automated code review for Java/SpringBoot pull requests — runs as a GitHub Action, posts findings as a PR comment, and can block merges on critical issues.

![Python 3.11](https://img.shields.io/badge/python-3.11-blue)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-green)
![Claude](https://img.shields.io/badge/Claude-Haiku%20%2B%20Sonnet-purple)

---

## What it does

- Triggers automatically on every `pull_request` opened or updated in your repo
- Reviews the diff for SpringBoot-specific issues: field injection, N+1 queries, hardcoded credentials, missing tests, CSRF disabled, swallowed exceptions, and more
- Posts a structured review comment with severity-ranked findings and concrete fix suggestions
- Exits with code 1 on critical findings — pair with branch protection rules to block the merge

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
                    │     Claude Haiku (diff + signals)  → list[Finding]
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
| `review_node` | Sends the diff + annotation signals + your team's `REVIEW_RULES.md` to Claude Haiku. Parses the returned JSON array into typed `Finding` objects. |
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
│   ├── agents/
│   │   └── orchestrator.py  LangGraph StateGraph, Finding + AgentState TypedDicts
│   └── tools/
│       ├── github.py        fetch_pr_diff, post_review_comment, load_review_rules
│       └── java_parser.py   extract_signals — Spring annotation scanner
├── tests/
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
# Required
GITHUB_TOKEN=ghp_xxxxxxxxxxxx        # github.com/settings/tokens → repo scope
GITHUB_REPOSITORY=owner/repo         # repo containing the PR, e.g. acme/api-service
PR_NUMBER=42                         # number of an open PR in that repo
PR_TITLE=My feature branch           # title of that PR
ANTHROPIC_API_KEY=sk-ant-xxxx        # console.anthropic.com/keys

# Optional — these have sensible defaults
MODEL_CODE=claude-haiku-4-5          # model for the review agent   (default: claude-haiku-4-5)
MODEL_SYNTH=claude-sonnet-4-6        # model for the synthesiser    (default: claude-sonnet-4-6)
MAX_DIFF_LINES=5000                  # truncate diffs larger than this (default: 5000)
POST_COMMENT=false                   # set true to post to GitHub   (default: true)
```

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

The bot posts a `REQUEST_CHANGES` or `APPROVE` review on the PR.

### 5. Test with a fake diff (no GitHub token or PR required)

Only `ANTHROPIC_API_KEY` is needed:

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
    pr_title="Test", anthropic_api_key=os.environ["ANTHROPIC_API_KEY"],
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

## Running tests

```bash
python3 -m pytest tests/ -v
```

```
tests/tools/test_github.py::test_fetch_pr_diff_basic                          PASSED
tests/tools/test_github.py::test_fetch_pr_diff_truncates_at_max_lines         PASSED
tests/tools/test_github.py::test_fetch_pr_diff_skips_files_without_patch      PASSED
tests/tools/test_github.py::test_post_review_comment_approve                  PASSED
tests/tools/test_github.py::test_post_review_comment_block_maps_to_...        PASSED
tests/tools/test_github.py::test_post_review_comment_request_changes          PASSED
tests/tools/test_github.py::test_load_review_rules_returns_content            PASSED
tests/tools/test_github.py::test_load_review_rules_returns_none_on_404        PASSED
tests/tools/test_java_parser.py::test_extract_signals_finds_service_...       PASSED
tests/tools/test_java_parser.py::test_extract_signals_finds_controller_...    PASSED
tests/tools/test_java_parser.py::test_extract_signals_empty_diff              PASSED
tests/tools/test_java_parser.py::test_extract_signals_no_annotations          PASSED
tests/tools/test_java_parser.py::test_extract_signals_jpa_annotations         PASSED
tests/tools/test_java_parser.py::test_extract_signals_security_annotations    PASSED
tests/tools/test_java_parser.py::test_extract_signals_test_annotations        PASSED

15 passed in 0.28s
```

| File | What is tested |
|---|---|
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
          anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}
          # github-token defaults to ${{ github.token }} — no extra secret needed
```

Add the secret: **repo Settings → Secrets and variables → Actions → New repository secret**
- Name: `ANTHROPIC_API_KEY`
- Value: your key from `console.anthropic.com/keys`

To block merges on critical findings: **Settings → Branches → Add branch protection rule → Require status checks to pass → select the `review` job**.

---

## Customising rules for your team

Copy `REVIEW_RULES.md` from this repo to the root of the repo being reviewed:

```bash
cp REVIEW_RULES.md /path/to/your-springboot-repo/REVIEW_RULES.md
```

Edit it freely. The agent fetches it on every PR and injects its contents into the review prompt alongside the built-in rules. If the file is absent, only the built-in rules apply. No code changes needed — the rules update takes effect on the next PR.

---

## Cost estimate

| Volume | Approximate cost |
|---|---|
| Single PR (500-line diff) | ~$0.005 – $0.008 |
| 1,000 PRs / month | ~$5 – $8 |

Claude Haiku handles the diff review; Sonnet is reserved for the synthesiser in the multi-agent version. Both models bill per token — larger diffs cost proportionally more.

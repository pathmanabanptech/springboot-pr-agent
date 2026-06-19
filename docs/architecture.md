# Architecture

## Deployment model
GitHub Action — runs inside the user's CI pipeline on every PR.
No server to host. No webhook to manage.
Users add one workflow file and one repo secret (ANTHROPIC_API_KEY).

## Data flow
```
GitHub PR opened/synchronize
  → GitHub Actions runner (ubuntu-latest)
    → action/main.py
      → Config.from_env()
      → orchestrator.run_review(config)
        → fetch_node
            github.fetch_pr_diff()       → DiffContext
            java_parser.extract_signals() → {filename: JavaSignals}
        → [parallel — all 3 run simultaneously]
            code_node     → code_agent.run()     → list[Finding]
            security_node → security_agent.run() → list[Finding]
            test_node     → test_agent.run()     → list[Finding]
        → synthesise_node
            deduplicate findings
            determine verdict
            format PR comment markdown
        → post_node
            github.post_review_comment()
      → return {verdict, findings_count}
    → exit 0 (APPROVE or REQUEST_CHANGES)
    → exit 1 (BLOCK) — fails the Action, can block merge via branch protection
```

## LangGraph AgentState
```python
class AgentState(TypedDict):
    config: Config
    diff: DiffContext
    java_signals: dict[str, str]          # filename → signal context string
    findings: Annotated[list[Finding], operator.add]  # agents append in parallel
    verdict: str
    comment_body: str
    findings_count: int
```

## Why parallel agents not one big prompt
- Speed: 3 × 10s ≈ 10s total vs 30s sequential
- Each agent has focused system prompt → better precision per domain
- Independent tuning: change security rules without touching code rules
- Isolated failures: one agent timeout doesn't break the others
- Deduplication in synthesiser handles any overlap

## Verdict logic
- BLOCK          → any critical finding (exits 1)
- REQUEST_CHANGES → any high or medium finding
- APPROVE        → only low/suggestion findings or none

## Cost profile (approximate)
- Haiku for 3 agents: ~$0.003–0.005 per PR (500-line diff)
- Sonnet for synthesiser: ~$0.002 per PR
- Total: ~$0.005–0.008 per PR
- 1000 PRs/month ≈ $5–8

## REVIEW_RULES.md
The orchestrator tries to fetch REVIEW_RULES.md from the root of the target repo
via GitHub API on every PR. If found, its contents are injected into the code_agent
prompt alongside the built-in rules. If not found, only built-in rules apply.
This is what makes the agent team-customisable without touching agent code.

## Max diff handling
If the PR diff exceeds MAX_DIFF_LINES (default 5000):
- DiffContext.truncated = True
- Only the first N files are reviewed
- synthesiser adds a truncation warning to the PR comment

## File structure
```
springboot-pr-agent/
  action.yml                 ← GitHub Action interface declaration
  action/main.py             ← entry point
  app/
    config.py
    agents/
      orchestrator.py
      code_agent.py
      security_agent.py
      test_agent.py
      synthesiser.py
    tools/
      github.py
      java_parser.py
  docs/
    architecture.md          ← this file
    java-rules.md            ← rule definitions (source of truth)
  tests/tools/               ← unit tests for tools
  eval_set/                  ← known-bad diffs for regression
  scripts/eval.py            ← eval runner
  REVIEW_RULES.md            ← default team rules (users copy + customise)
  requirements.txt
```

## Build status
- [ ] Step 1: project scaffold + requirements
- [ ] Step 2: app/config.py
- [ ] Step 3: app/tools/github.py + java_parser.py
- [ ] Step 4: action/main.py + action.yml  ← verify end-to-end here
- [ ] Step 5: orchestrator (single node first)
- [ ] Step 6: code_agent
- [ ] Step 7: security_agent
- [ ] Step 8: test_agent
- [ ] Step 9: synthesiser + parallel graph
- [ ] Step 10: tests
- [ ] Step 11: eval_set + scripts/eval.py
- [ ] Step 12: README.md
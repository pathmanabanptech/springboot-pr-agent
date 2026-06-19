import json
import operator
import re
from typing import Annotated, TypedDict

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from app.config import Config
from app.tools.github import DiffContext, fetch_pr_diff, load_review_rules, post_review_comment
from app.tools.java_parser import extract_signals

SYSTEM_PROMPT = """You are an expert Java and SpringBoot code reviewer.
Analyse the PR diff provided and return a JSON array of findings.
Each finding must be a JSON object with exactly these keys:
  severity   – one of: critical, high, medium, low, suggestion
  file       – the Java source file path (e.g. "src/main/java/UserService.java")
  line       – line number as a string, or "unknown"
  rule       – short rule id (e.g. "no-field-injection")
  message    – what is wrong and why (1-2 sentences)
  suggestion – a concrete fix

Return ONLY the JSON array — no prose before or after it.
If there are no issues, return an empty array: []

Focus on these categories:
- Dependency injection: prefer constructor injection over @Autowired field injection
- Transactions: @Transactional belongs on service layer only
- JPA: detect N+1 risks, entity exposure in REST responses
- Security: hardcoded credentials, CSRF disabled, missing @PreAuthorize
- Error handling: swallowed exceptions, try-catch in controllers
- Testing: empty test bodies, tests with no assertions, @SpringBootTest overuse"""


class Finding(TypedDict):
    severity: str
    file: str
    line: str
    rule: str
    message: str
    suggestion: str
    agent: str


class AgentState(TypedDict):
    config: Config
    diff: DiffContext
    java_signals: dict[str, str]
    findings: Annotated[list[Finding], operator.add]
    verdict: str
    comment_body: str
    findings_count: int


def _fetch_node(state: AgentState) -> dict:
    cfg = state["config"]
    diff = fetch_pr_diff(cfg.github_token, cfg.github_repository, cfg.pr_number, cfg.max_diff_lines)
    signals = extract_signals(diff["diff_text"])
    return {"diff": diff, "java_signals": signals}


def _review_node(state: AgentState) -> dict:
    cfg = state["config"]
    diff = state["diff"]
    signals = state["java_signals"]

    review_rules = load_review_rules(cfg.github_token, cfg.github_repository)

    signal_block = ""
    if signals:
        signal_block = "\n\n## Detected annotations per file\n" + "\n".join(
            f"- {fname}: {sigs}" for fname, sigs in signals.items()
        )

    rules_block = ""
    if review_rules:
        rules_block = f"\n\n## Team review rules (REVIEW_RULES.md)\n{review_rules}"

    truncation_note = ""
    if diff["truncated"]:
        truncation_note = f"\n\n> NOTE: Diff was truncated at {cfg.max_diff_lines} lines. Reviewed files: {', '.join(diff['files'])}"

    human_content = (
        f"PR: {diff['title']}\n"
        f"Repository: {diff['repo']}\n"
        f"{truncation_note}"
        f"{signal_block}"
        f"{rules_block}"
        f"\n\n## Diff\n```diff\n{diff['diff_text']}\n```"
    )

    llm = ChatAnthropic(model=cfg.model_code, api_key=cfg.anthropic_api_key, max_tokens=4096)
    response = llm.invoke([SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=human_content)])

    raw = response.content
    # extract JSON array even if the model wrapped it in markdown fences
    json_match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not json_match:
        return {"findings": []}

    try:
        items = json.loads(json_match.group())
    except json.JSONDecodeError:
        return {"findings": []}

    findings: list[Finding] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        findings.append(
            Finding(
                severity=item.get("severity", "suggestion"),
                file=item.get("file", "unknown"),
                line=str(item.get("line", "unknown")),
                rule=item.get("rule", "general"),
                message=item.get("message", ""),
                suggestion=item.get("suggestion", ""),
                agent="code",
            )
        )

    return {"findings": findings}


def _synthesise_node(state: AgentState) -> dict:
    findings = state["findings"]

    severities = {f["severity"] for f in findings}
    if "critical" in severities:
        verdict = "BLOCK"
    elif severities & {"high", "medium"}:
        verdict = "REQUEST_CHANGES"
    else:
        verdict = "APPROVE"

    comment_body = _format_comment(state["diff"], findings, verdict)
    return {"verdict": verdict, "comment_body": comment_body, "findings_count": len(findings)}


def _post_node(state: AgentState) -> dict:
    cfg = state["config"]
    if cfg.post_comment:
        post_review_comment(
            cfg.github_token,
            cfg.github_repository,
            cfg.pr_number,
            state["comment_body"],
            state["verdict"],
        )
    else:
        print("[dry-run] Would post comment:\n", state["comment_body"])
    return {}


def _format_comment(diff: DiffContext, findings: list[Finding], verdict: str) -> str:
    verdict_emoji = {"APPROVE": "✅", "REQUEST_CHANGES": "⚠️", "BLOCK": "🚫"}.get(verdict, "ℹ️")
    verdict_label = {"APPROVE": "Approved", "REQUEST_CHANGES": "Changes requested", "BLOCK": "Blocked — critical issues"}.get(verdict, verdict)

    lines = [
        f"## {verdict_emoji} PR Review — {verdict_label}",
        "",
        f"**{len(findings)} finding(s)** across {len(diff['files'])} file(s).",
    ]

    if diff["truncated"]:
        lines.append(f"\n> ⚠️ Diff exceeded line limit. Only first {len(diff['files'])} files reviewed.")

    if not findings:
        lines.append("\nNo issues found.")
        return "\n".join(lines)

    severity_order = ["critical", "high", "medium", "low", "suggestion"]
    grouped: dict[str, list[Finding]] = {s: [] for s in severity_order}
    for f in findings:
        grouped.setdefault(f["severity"], []).append(f)

    severity_emoji = {"critical": "🚫", "high": "🔴", "medium": "🟠", "low": "🟡", "suggestion": "💡"}

    for sev in severity_order:
        bucket = grouped[sev]
        if not bucket:
            continue
        emoji = severity_emoji.get(sev, "•")
        lines.append(f"\n### {emoji} {sev.capitalize()} ({len(bucket)})")
        for finding in bucket:
            lines.append(f"\n**`{finding['rule']}`** — {finding['file']}:{finding['line']}")
            lines.append(f"{finding['message']}")
            if finding["suggestion"]:
                lines.append(f"> **Fix:** {finding['suggestion']}")

    lines.append("\n---")
    lines.append("*Reviewed by [springboot-pr-agent](https://github.com/marketplace/actions/springboot-pr-review-agent)*")

    return "\n".join(lines)


def _build_graph() -> StateGraph:
    g = StateGraph(AgentState)
    g.add_node("fetch", _fetch_node)
    g.add_node("review", _review_node)
    g.add_node("synthesise", _synthesise_node)
    g.add_node("post", _post_node)

    g.set_entry_point("fetch")
    g.add_edge("fetch", "review")
    g.add_edge("review", "synthesise")
    g.add_edge("synthesise", "post")
    g.add_edge("post", END)

    return g.compile()


_graph = _build_graph()


def run_review(config: Config) -> dict:
    initial: AgentState = {
        "config": config,
        "diff": DiffContext(repo="", pr_number=0, title="", diff_text="", files=[], truncated=False),
        "java_signals": {},
        "findings": [],
        "verdict": "",
        "comment_body": "",
        "findings_count": 0,
    }
    result = _graph.invoke(initial)
    return {"verdict": result["verdict"], "findings_count": result["findings_count"]}

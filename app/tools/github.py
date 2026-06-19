from typing import TypedDict

from github import Github, GithubException


class DiffContext(TypedDict):
    repo: str
    pr_number: int
    title: str
    diff_text: str
    files: list[str]
    truncated: bool


def fetch_pr_diff(token: str, repo: str, pr_number: int, max_lines: int = 5000) -> DiffContext:
    g = Github(token)
    gh_repo = g.get_repo(repo)
    pr = gh_repo.get_pull(pr_number)

    patches: list[str] = []
    files: list[str] = []
    total_lines = 0
    truncated = False

    for f in pr.get_files():
        files.append(f.filename)
        if f.patch:
            patch_lines = f.patch.count("\n") + 1
            if total_lines + patch_lines > max_lines:
                truncated = True
                break
            patches.append(f"--- {f.filename}\n{f.patch}")
            total_lines += patch_lines

    return DiffContext(
        repo=repo,
        pr_number=pr_number,
        title=pr.title,
        diff_text="\n\n".join(patches),
        files=files,
        truncated=truncated,
    )


def post_review_comment(token: str, repo: str, pr_number: int, body: str, verdict: str) -> None:
    event_map = {
        "APPROVE": "APPROVE",
        "REQUEST_CHANGES": "REQUEST_CHANGES",
        "BLOCK": "REQUEST_CHANGES",
    }
    event = event_map.get(verdict, "COMMENT")

    g = Github(token)
    gh_repo = g.get_repo(repo)
    pr = gh_repo.get_pull(pr_number)
    pr.create_review(body=body, event=event)


def load_review_rules(token: str, repo: str) -> str | None:
    g = Github(token)
    try:
        gh_repo = g.get_repo(repo)
        content = gh_repo.get_contents("REVIEW_RULES.md")
        return content.decoded_content.decode("utf-8")
    except GithubException:
        return None

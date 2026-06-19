import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    github_token: str
    github_repository: str
    pr_number: int
    pr_title: str
    anthropic_api_key: str
    pr_base_sha: str = ""
    pr_head_sha: str = ""
    model_code: str = "claude-haiku-4-5"
    model_synth: str = "claude-sonnet-4-6"
    max_diff_lines: int = 5000
    post_comment: bool = True

    @classmethod
    def from_env(cls) -> "Config":
        missing = [v for v in ("GITHUB_TOKEN", "GITHUB_REPOSITORY", "PR_NUMBER", "PR_TITLE", "ANTHROPIC_API_KEY") if not os.getenv(v)]
        if missing:
            raise EnvironmentError(f"Missing required env vars: {', '.join(missing)}")

        return cls(
            github_token=os.environ["GITHUB_TOKEN"],
            github_repository=os.environ["GITHUB_REPOSITORY"],
            pr_number=int(os.environ["PR_NUMBER"]),
            pr_title=os.environ["PR_TITLE"],
            anthropic_api_key=os.environ["ANTHROPIC_API_KEY"],
            pr_base_sha=os.getenv("PR_BASE_SHA", ""),
            pr_head_sha=os.getenv("PR_HEAD_SHA", ""),
            model_code=os.getenv("MODEL_CODE", "claude-haiku-4-5"),
            model_synth=os.getenv("MODEL_SYNTH", "claude-sonnet-4-6"),
            max_diff_lines=int(os.getenv("MAX_DIFF_LINES", "5000")),
            post_comment=os.getenv("POST_COMMENT", "true").lower() != "false",
        )

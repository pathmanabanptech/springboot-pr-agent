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
    llm_api_key: str
    pr_base_sha: str = ""
    pr_head_sha: str = ""
    model_provider: str = "anthropic"
    model_code: str = "claude-haiku-4-5"
    model_synth: str = "claude-sonnet-4-6"
    max_diff_lines: int = 5000
    post_comment: bool = True

    # backward-compat alias — code that still reads cfg.anthropic_api_key keeps working
    @property
    def anthropic_api_key(self) -> str:
        return self.llm_api_key

    @classmethod
    def from_env(cls) -> "Config":
        missing = [v for v in ("GITHUB_TOKEN", "GITHUB_REPOSITORY", "PR_NUMBER", "PR_TITLE") if not os.getenv(v)]
        if missing:
            raise EnvironmentError(f"Missing required env vars: {', '.join(missing)}")

        # LLM_API_KEY takes priority; fall back to ANTHROPIC_API_KEY for compat
        llm_api_key = os.getenv("LLM_API_KEY") or os.getenv("ANTHROPIC_API_KEY", "")
        if not llm_api_key:
            raise EnvironmentError("Missing required env var: LLM_API_KEY (or ANTHROPIC_API_KEY)")

        return cls(
            github_token=os.environ["GITHUB_TOKEN"],
            github_repository=os.environ["GITHUB_REPOSITORY"],
            pr_number=int(os.environ["PR_NUMBER"]),
            pr_title=os.environ["PR_TITLE"],
            llm_api_key=llm_api_key,
            pr_base_sha=os.getenv("PR_BASE_SHA", ""),
            pr_head_sha=os.getenv("PR_HEAD_SHA", ""),
            model_provider=os.getenv("MODEL_PROVIDER", "anthropic"),
            model_code=os.getenv("MODEL_CODE", "claude-haiku-4-5"),
            model_synth=os.getenv("MODEL_SYNTH", "claude-sonnet-4-6"),
            max_diff_lines=int(os.getenv("MAX_DIFF_LINES", "5000")),
            post_comment=os.getenv("POST_COMMENT", "true").lower() != "false",
        )

import sys
import os

# allow `python action/main.py` from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.config import Config
from app.agents.orchestrator import run_review


def main() -> None:
    config = Config.from_env()
    result = run_review(config)
    print(f"verdict={result['verdict']} findings={result['findings_count']}")
    sys.exit(1 if result["verdict"] == "BLOCK" else 0)


if __name__ == "__main__":
    main()

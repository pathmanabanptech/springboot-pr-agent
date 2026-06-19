from unittest.mock import MagicMock, patch

import pytest

from app.tools.github import fetch_pr_diff, load_review_rules, post_review_comment


def _make_file(filename: str, patch_text: str | None) -> MagicMock:
    f = MagicMock()
    f.filename = filename
    f.patch = patch_text
    return f


# ---------------------------------------------------------------------------
# fetch_pr_diff
# ---------------------------------------------------------------------------

@patch("app.tools.github.Github")
def test_fetch_pr_diff_basic(MockGithub):
    pr = MagicMock()
    pr.title = "Add user service"
    pr.get_files.return_value = [
        _make_file("src/UserService.java", "+@Service\npublic class UserService {}"),
    ]
    MockGithub.return_value.get_repo.return_value.get_pull.return_value = pr

    result = fetch_pr_diff("token", "owner/repo", 42)

    assert result["repo"] == "owner/repo"
    assert result["pr_number"] == 42
    assert result["title"] == "Add user service"
    assert "UserService.java" in result["diff_text"]
    assert "src/UserService.java" in result["files"]
    assert result["truncated"] is False


@patch("app.tools.github.Github")
def test_fetch_pr_diff_truncates_at_max_lines(MockGithub):
    # Each patch has 6 lines; max_lines=5 forces truncation after the first file
    pr = MagicMock()
    pr.title = "Big PR"
    pr.get_files.return_value = [
        _make_file("A.java", "line1\nline2\nline3\nline4\nline5\nline6"),
        _make_file("B.java", "+more code"),
    ]
    MockGithub.return_value.get_repo.return_value.get_pull.return_value = pr

    result = fetch_pr_diff("token", "owner/repo", 1, max_lines=5)

    assert result["truncated"] is True
    assert "B.java" not in result["diff_text"]
    # Both filenames still appear in files list (collected before patch check)
    assert "A.java" in result["files"]


@patch("app.tools.github.Github")
def test_fetch_pr_diff_skips_files_without_patch(MockGithub):
    pr = MagicMock()
    pr.title = "Binary change"
    pr.get_files.return_value = [
        _make_file("image.png", None),
        _make_file("Service.java", "+@Service\npublic class Service {}"),
    ]
    MockGithub.return_value.get_repo.return_value.get_pull.return_value = pr

    result = fetch_pr_diff("token", "owner/repo", 5)

    assert result["truncated"] is False
    assert "image.png" not in result["diff_text"]
    assert "Service.java" in result["diff_text"]


# ---------------------------------------------------------------------------
# post_review_comment
# ---------------------------------------------------------------------------

@patch("app.tools.github.Github")
def test_post_review_comment_approve(MockGithub):
    pr = MagicMock()
    MockGithub.return_value.get_repo.return_value.get_pull.return_value = pr

    post_review_comment("token", "owner/repo", 7, "Looks good!", "APPROVE")

    pr.create_review.assert_called_once_with(body="Looks good!", event="APPROVE")


@patch("app.tools.github.Github")
def test_post_review_comment_block_maps_to_request_changes(MockGithub):
    pr = MagicMock()
    MockGithub.return_value.get_repo.return_value.get_pull.return_value = pr

    post_review_comment("token", "owner/repo", 7, "Critical issue found", "BLOCK")

    pr.create_review.assert_called_once_with(body="Critical issue found", event="REQUEST_CHANGES")


@patch("app.tools.github.Github")
def test_post_review_comment_request_changes(MockGithub):
    pr = MagicMock()
    MockGithub.return_value.get_repo.return_value.get_pull.return_value = pr

    post_review_comment("token", "owner/repo", 7, "Fix these issues", "REQUEST_CHANGES")

    pr.create_review.assert_called_once_with(body="Fix these issues", event="REQUEST_CHANGES")


# ---------------------------------------------------------------------------
# load_review_rules
# ---------------------------------------------------------------------------

@patch("app.tools.github.Github")
def test_load_review_rules_returns_content(MockGithub):
    content = MagicMock()
    content.decoded_content = b"## Naming\n- Service suffix required"
    MockGithub.return_value.get_repo.return_value.get_contents.return_value = content

    result = load_review_rules("token", "owner/repo")

    assert result == "## Naming\n- Service suffix required"


@patch("app.tools.github.Github")
def test_load_review_rules_returns_none_on_404(MockGithub):
    from github import GithubException
    MockGithub.return_value.get_repo.return_value.get_contents.side_effect = GithubException(404, "Not Found")

    result = load_review_rules("token", "owner/repo")

    assert result is None

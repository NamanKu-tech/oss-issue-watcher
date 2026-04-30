import os
import sys
import unittest.mock as mock
import tempfile


def _import():
    """Import check_issues patching the module-level repos.json open."""
    with mock.patch("builtins.open", mock.mock_open(read_data="[]")):
        if "check_issues" in sys.modules:
            del sys.modules["check_issues"]
        import check_issues
    return check_issues


def test_latest_digest_csv_written_when_ai_returns_csv(tmp_path, monkeypatch):
    mod = _import()
    monkeypatch.chdir(tmp_path)

    dummy_csv = (
        "repo,issue_number,title,url,labels,areas,created,score,what_to_do,time_estimate,skill_tags\n"
        "apache/kafka,1,Fix bug,https://github.com/apache/kafka/issues/1,bug,,2026-04-30,8,Edit Foo.java,,Java\n"
    )

    monkeypatch.setattr(mod, "analyze_with_ai", lambda issues: dummy_csv)
    monkeypatch.setattr(mod, "USER_CONFIGS", [{"email": "x@x.com", "name": "X", "max_issues": 5, "difficulty_min": 1, "difficulty_max": 10, "areas": []}])
    monkeypatch.setattr(mod, "WATCHED_REPOS", [{"owner": "apache", "repo": "kafka", "labels": ["good first issue"], "areas": ["Java"]}])
    monkeypatch.setattr(mod, "fetch_issues", lambda *a, **kw: [{
        "id": 99999, "title": "Fix bug", "html_url": "https://github.com/apache/kafka/issues/1",
        "created_at": "2026-04-30T00:00:00Z", "number": 1, "labels": [{"name": "bug"}]
    }])
    monkeypatch.setattr(mod, "send_email", lambda *a, **kw: True)
    monkeypatch.setenv("SMTP_USERNAME", "x@x.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")

    mod.main()

    assert (tmp_path / "latest_digest.csv").exists()
    content = (tmp_path / "latest_digest.csv").read_text()
    assert "apache/kafka" in content
    assert "Fix bug" in content


def test_latest_digest_csv_not_written_when_ai_returns_none(tmp_path, monkeypatch):
    mod = _import()
    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr(mod, "analyze_with_ai", lambda issues: None)
    monkeypatch.setattr(mod, "USER_CONFIGS", [{"email": "x@x.com", "name": "X", "max_issues": 5, "difficulty_min": 1, "difficulty_max": 10, "areas": []}])
    monkeypatch.setattr(mod, "WATCHED_REPOS", [{"owner": "apache", "repo": "kafka", "labels": ["good first issue"], "areas": ["Java"]}])
    monkeypatch.setattr(mod, "fetch_issues", lambda *a, **kw: [{
        "id": 99999, "title": "Fix bug", "html_url": "https://github.com/apache/kafka/issues/1",
        "created_at": "2026-04-30T00:00:00Z", "number": 1, "labels": [{"name": "bug"}]
    }])
    monkeypatch.setattr(mod, "send_email", lambda *a, **kw: True)
    monkeypatch.setenv("SMTP_USERNAME", "x@x.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")

    mod.main()

    assert not (tmp_path / "latest_digest.csv").exists()

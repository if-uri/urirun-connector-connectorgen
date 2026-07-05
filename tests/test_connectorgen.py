from urirun_connector_connectorgen import core
from urirun_reasoner import generation_policy


def _spec(**over):
    s = {"id": "widget", "scheme": "widget", "summary": "x",
         "handlers": [{"route": "thing/query/list", "params": "", "body": 'return _ok(action="x")'}]}
    s.update(over); return s


def test_policy_rejects_existing_scheme():
    v = generation_policy.check(_spec(), served_schemes={"widget"})
    assert not v["ok"] and any("already served" in x for x in v["violations"])


def test_policy_flags_ungated_destructive_verb():
    v = generation_policy.check(_spec(handlers=[{"route": "message/command/delete", "params": "", "body": "return _ok()"}]))
    assert not v["ok"] and any("destructive" in x for x in v["violations"])


def test_policy_accepts_gated_destructive_verb():
    v = generation_policy.check(_spec(handlers=[{"route": "message/command/delete", "gated": True, "params": "", "body": "return _ok()"}]))
    assert v["ok"] and v["gated_routes"] == ["message/command/delete"]


def test_policy_rejects_inline_secret():
    v = generation_policy.check(_spec(handlers=[{"route": "x/query/y", "params": "", "body": 'api_key = "abc123"'}]))
    assert not v["ok"] and any("secret" in x for x in v["violations"])


def test_generate_refuses_inadmissible_spec():
    r = core.spec_generate(spec=_spec(id="BadName"))
    assert r["ok"] is False and r.get("violations")


def test_generate_writes_and_smokes(tmp_path):
    r = core.spec_generate(spec=_spec(), dest=str(tmp_path))
    assert r["ok"] and r["routes"] == ["thing/query/list"]
    assert (tmp_path / "urirun-connector-widget" / "pyproject.toml").is_file()
    assert r["smoke"]["ok"] is True and r["installable"] is True


def test_repo_publish_reports_visibility(monkeypatch, tmp_path):
    (tmp_path / "urirun-connector-x").mkdir()
    import subprocess
    calls = []
    class CP:
        def __init__(s, out="PUBLIC"): s.returncode=0; s.stdout=out; s.stderr=""
    def fake_run(args, **k): calls.append(args[0:3]); return CP()
    monkeypatch.setattr(core.subprocess if hasattr(core,'subprocess') else __import__('subprocess'), "run", fake_run, raising=False)
    import subprocess as sp; monkeypatch.setattr(sp, "run", fake_run)
    r = core.repo_publish(path=str(tmp_path / "urirun-connector-x"))
    assert r["ok"] and r["repo"] == "if-uri/urirun-connector-x"
    assert r["installable"].startswith("git+https://github.com/if-uri/")

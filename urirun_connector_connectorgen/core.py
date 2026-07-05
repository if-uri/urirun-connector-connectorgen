# Author: Tom Sapletta · Part of the ifURI solution.
"""urirun-connector-connectorgen — generate NEW connectors as a URI process.

This is the meta-connector: the autonomy that CREATES connectors instead of waiting for a
human. When the reasoner finds a capability blocked because a scheme has no connector, a
``connector://host/spec/command/generate`` step produces, policy-checks, and smoke-tests a
complete installable connector — no prompt, just the guardrails of the generation policy.

Built to URI_NATIVE_CONNECTOR_CHECKLIST: lazy imports, handlers never raise (envelope);
generation writes files (isolated) and always runs the policy + a smoke import first.
"""
from __future__ import annotations

import os
from typing import Any

import urirun

CONNECTOR_ID = "connectorgen"
conn = urirun.connector(CONNECTOR_ID, scheme="connector")

_DEST_ENV = "URIRUN_CONNECTOR_DEST"     # where generated connectors are written


def _ok(**kw: Any) -> dict[str, Any]:
    return urirun.ok(connector=CONNECTOR_ID, **kw)


def _fail(msg: str, action: str, **extra: Any) -> dict[str, Any]:
    extra.pop("error", None)
    return urirun.fail(msg, connector=CONNECTOR_ID, action=action, **extra)


def _dest() -> str:
    return os.environ.get(_DEST_ENV) or os.path.expanduser("~/.urirun/generated-connectors")


@conn.handler("policy/query/check", isolated=False,
              meta={"label": "Check a connector spec against the generation policy (new scheme, gated verbs, no secrets)"})
def policy_check(spec: dict | None = None, served_schemes: list | None = None) -> dict[str, Any]:
    """The cheap gate before generating: is this spec admissible? New scheme, envelope-safe,
    destructive verbs gated, no inline secrets, clean slugs."""
    if not spec:
        return _fail("spec is required", "policy-check")
    try:
        from urirun_reasoner.generation_policy import check
        return _ok(action="policy-check", **check(spec, served_schemes=set(served_schemes or [])))
    except Exception as exc:  # noqa: BLE001
        return _fail(str(exc), "policy-check")


@conn.handler("spec/command/generate", isolated=True,
              meta={"label": "Generate a NEW connector from a spec (policy-checked, smoke-tested, optionally auto-published)"})
def spec_generate(spec: dict | None = None, served_schemes: list | None = None,
                  dest: str = "", publish: bool = False) -> dict[str, Any]:
    """Autonomously produce a complete, installable connector: enforce the generation
    policy, write the package, smoke-import it, and (publish=true) push it PUBLIC to GitHub
    so any node can install it. Refuses inadmissible specs (the policy IS the permission)."""
    if not spec:
        return _fail("spec is required", "generate")
    try:
        from urirun_reasoner import generation_policy, generator
    except Exception as exc:  # noqa: BLE001
        return _fail(f"needs urirun-reasoner: {exc}", "generate")

    verdict = generation_policy.check(spec, served_schemes=set(served_schemes or []))
    if not verdict["ok"]:
        return _fail("spec violates the generation policy", "generate", violations=verdict["violations"])

    out_dir = dest or _dest()
    try:
        r = generator.generate(spec, out_dir)
    except Exception as exc:  # noqa: BLE001
        return _fail(f"generation failed: {exc}", "generate")

    smoke = _smoke_import(r["path"])
    published = repo_publish(path=r["path"], description=spec.get("summary", "")) if (publish and smoke.get("ok")) else None
    return _ok(action="generate", path=r["path"], routes=r["routes"],
               gated_routes=verdict["gated_routes"], smoke=smoke,
               installable=smoke.get("ok", False), published=published)


@conn.handler("repo/command/publish", isolated=True,
              meta={"label": "Publish a generated connector to GitHub as PUBLIC so any node can install it"})
def repo_publish(path: str = "", org: str = "if-uri", description: str = "") -> dict[str, Any]:
    """git init + push a generated connector to a PUBLIC GitHub repo — so a node can
    ``pip install git+https://github.com/<org>/urirun-connector-<id>``. Idempotent: an
    existing repo is pushed to, not recreated."""
    import subprocess
    if not path or not os.path.isdir(path):
        return _fail(f"no connector at {path!r}", "publish")
    name = os.path.basename(path.rstrip("/"))
    def _sh(args, **kw):
        return subprocess.run(args, capture_output=True, text=True, timeout=120, cwd=path, **kw)
    try:
        if not os.path.isdir(os.path.join(path, ".git")):
            with open(os.path.join(path, ".gitignore"), "w") as fh:
                fh.write("dist/\nbuild/\n*.egg-info/\n__pycache__/\n*.pyc\n.venv/\n")
            _sh(["git", "init", "-q"])
        _sh(["git", "add", "-A"])
        _sh(["git", "-c", "user.name=Tom Softreck", "-c", "user.email=tom@sapletta.com",
             "commit", "-q", "-m", f"{name}: auto-generated + auto-published by connectorgen"])
        cr = _sh(["gh", "repo", "create", f"{org}/{name}", "--public", "--source=.",
                  "--description", description or f"Auto-generated urirun connector ({name})", "--push"])
        if cr.returncode != 0 and "already exists" in (cr.stderr + cr.stdout):
            _sh(["git", "push", "-q"])
        vis = _sh(["gh", "repo", "view", f"{org}/{name}", "--json", "visibility", "-q", ".visibility"])
        return _ok(action="publish", repo=f"{org}/{name}",
                   url=f"https://github.com/{org}/{name}", visibility=vis.stdout.strip() or "?",
                   installable=f"git+https://github.com/{org}/{name}.git")
    except Exception as exc:  # noqa: BLE001
        return _fail(str(exc), "publish")


def _smoke_import(path: str) -> dict[str, Any]:
    """Install the generated connector editable and import it — proof it is well-formed.
    Runs out-of-process so a broken generation can't poison this process."""
    import subprocess
    import sys
    try:
        pip = subprocess.run([sys.executable, "-m", "pip", "install", "-e", path, "-q", "--no-deps"],
                             capture_output=True, text=True, timeout=180)
        if pip.returncode != 0:
            return {"ok": False, "stage": "install", "error": (pip.stderr or "")[-300:]}
        mod = "urirun_connector_" + os.path.basename(path).replace("urirun-connector-", "").replace("-", "_")
        # import from the package dir to dodge the repo-root namespace shadow
        chk = subprocess.run([sys.executable, "-c", f"import {mod}; print('ok')"],
                             capture_output=True, text=True, timeout=60, cwd=path)
        return {"ok": chk.returncode == 0, "stage": "import",
                "detail": (chk.stdout or chk.stderr or "")[-200:]}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def urirun_bindings() -> dict[str, Any]:
    return conn.bindings()


def connector_manifest() -> dict[str, Any]:
    m = urirun.load_manifest(__package__) or {"id": CONNECTOR_ID}
    try:
        from urirun_connectors_toolkit.connector_sdk import manifest_routes
        m["routes"] = manifest_routes(urirun_bindings())
    except Exception:  # noqa: BLE001
        pass
    return m


def main(argv: list[str] | None = None) -> int:
    return conn.cli(argv, manifest_prose=urirun.load_manifest(__package__))


if __name__ == "__main__":
    raise SystemExit(main())

"""Noxfile."""

import glob
import os
import shutil
from pathlib import Path

import nox

nox.needs_version = ">=2025.5.1"

# https://docs.github.com/en/actions/writing-workflows/choosing-what-your-workflow-does/store-information-in-variables#default-environment-variables
CI = os.getenv("CI", "").lower() in ("true", "1", "yes")

# Python versions to run sessions in
PYTHON_LATEST = "3.13"
PYPROJECT = nox.project.load_toml("pyproject.toml")
PYTHON_VERSIONS = nox.project.python_versions(PYPROJECT, max_version=PYTHON_LATEST)

# Use uv as backend
nox.options.default_venv_backend = "uv"

# Default sessions to run if no `-s` specified
nox.options.sessions = ["lint", f"test-{PYTHON_LATEST}"]


def env_kv(key: str, default: str | None) -> dict[str, str | None]:
    """Get the key-value of an environment variable, else default."""
    return {key: os.getenv(key, default)}


def sync_uv(session: nox.Session):
    """Sync UV with all extras."""
    session.run_install(
        "uv",
        "sync",
        "--all-extras",
        "--dev",
        f"--python={session.virtualenv.location}",
        env={"UV_PROJECT_ENVIRONMENT": session.virtualenv.location},
    )


@nox.session()
def docs(session: nox.Session):
    """Build project documentation with pdoc."""
    sync_uv(session)

    # Show in browser if session is interactive
    if session.interactive:
        session.run("pdoc", "-d", "numpy", "src/capistry")
        return

    # Get docs directory (default: "docs")
    docs_dir = session.posargs[0] if session.posargs else "docs"
    docs_path = Path(docs_dir).resolve()

    # Ensure docs path is within project
    if not docs_path.is_relative_to(Path(__file__).parent):
        session.error(f"Invalid docs directory: {docs_dir}")

    # Clean existing docs directory
    if docs_path.exists():
        if docs_path.is_file():
            session.error(f"{docs_path} exists and is not a directory")
        shutil.rmtree(docs_path)

    session.run("pdoc", "-d", "numpy", "src/capistry", "-o", docs_dir)


@nox.session()
def build(session: nox.Session):
    """Build source distribution."""
    sync_uv(session)

    path = Path("dist")
    if path.exists():
        session.log("Cleaning up dist/")
        shutil.rmtree(path)

    session.run("uv", "build", *session.posargs)


@nox.session(name="publish-test", requires=["build"])
def publish_test(session: nox.Session):
    """Publish package to PyPI's Test index."""
    sync_uv(session)
    session.run("uv", "publish", "--index", "testpypi")


@nox.session(name="publish-prod", requires=["build"])
def publish_prod(session: nox.Session):
    """Publish package to PyPI's Production index."""
    sync_uv(session)
    session.run("uv", "publish")


@nox.session(tags=["check"])
def lint(session: nox.Session):
    """Run ruff check & format."""
    sync_uv(session)

    if CI:
        session.run("ruff", "check", ".", *session.posargs)
        session.run("ruff", "format", ".", "--exit-non-zero-on-format", *session.posargs)
    else:
        session.run("ruff", "check", ".", "--fix", *session.posargs)
        session.run("ruff", "format", ".", *session.posargs)

    session.run("codespell", ".")


@nox.session(py=PYTHON_VERSIONS, tags=["check"])
def test(session: nox.Session):
    """Run the test suite."""
    sync_uv(session)

    session.run(
        "pytest",
        "src/tests",
        "-n",
        "logical",
        "--dist",
        "worksteal",
        *session.posargs,
        env={
            **env_kv("HYPOTHESIS_PROFILE", "ci" if CI else "quick"),
            **env_kv("OCP_VSCODE_PYTEST", "1"),
            **env_kv(
                "PYTEST_XDIST_AUTO_NUM_WORKERS",
                None if CI else str(max(1, (os.cpu_count() or 2) // 2)),
            ),
        },
    )


@nox.session(tags=["check"])
def examples(session: nox.Session):
    """Run the example suite."""
    sync_uv(session)

    examples = glob.glob("examples/*/main.py")

    if not examples:
        session.log("No example main.py files found!")
        return

    for ex in examples:
        session.run("python", ex, *session.posargs, env=env_kv("OCP_VSCODE_PYTEST", "1"))

"""Git tools for project synchronization and conflict repair, following chat mode."""
from __future__ import annotations

from collections.abc import Awaitable, Callable

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.services import gitops

GIT_TOOLS = frozenset({"git_status", "git_log", "git_diff", "git_commit", "git_push", "git_sync",
                       "git_conflicts", "git_resolve", "git_remote"})
GIT_MUTATING = frozenset({"git_commit", "git_push", "git_sync", "git_resolve", "git_remote"})
ALWAYS_ASK = frozenset()
GIT_PERMISSION = "repo.git"
MODEL_DIFF = 12_000


class _NoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GitLog(_NoArgs):
    limit: int = Field(default=10, ge=1, le=50)


class GitCommit(_NoArgs):
    message: str = Field(min_length=1, max_length=2000)


class GitPush(_NoArgs):
    branch: str | None = Field(default=None, max_length=200)


class GitResolve(_NoArgs):
    path: str = Field(min_length=1, max_length=4096)
    expected_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    delete: bool = False


class GitConflicts(_NoArgs):
    path: str | None = Field(default=None, max_length=4096)


class GitRemote(_NoArgs):
    url: str = Field(default="", max_length=1000)
    name: str = Field(default="", max_length=100)
    private: bool = True


_SCHEMAS = {"git_status": _NoArgs, "git_log": GitLog, "git_diff": _NoArgs, "git_commit": GitCommit,
            "git_push": GitPush, "git_sync": GitPush, "git_conflicts": GitConflicts, "git_resolve": GitResolve,
            "git_remote": GitRemote}
_DESCRIPTIONS = {
    "git_status": "Git state of this project: branch, uncommitted changes, remote, ahead/behind, last commit.",
    "git_log": "Recent commits of this project (newest first).",
    "git_diff": "Uncommitted changes of this project as a unified diff (new files included).",
    "git_commit": "Commit all current project changes with a clear message (initialises git if needed). "
                  "Use it when the user asks to commit or after finishing a requested change set.",
    "git_push": "Publish requested changes to the configured remote. Automatically syncs remote commits first. "
                "If it reports conflicts, call git_conflicts, repair files, git_resolve each, git_commit and retry. "
                "Commit uncommitted work first. Follow chat mode; Auto executes without extra confirmation.",
    "git_sync": "Fetch and merge the current remote branch, preserving local commits and a backup ref. "
                "Commit local changes first. On conflicts use git_conflicts, read_file/write_file to combine "
                "both sides according to the task, git_resolve each file, then git_commit and git_push. "
                "Never blindly discard either side; verify the combined code with available checks.",
    "git_conflicts": "List unresolved merge files with base, local (ours) and remote (theirs) versions. "
                     "Use optional path to focus on one conflict if output is truncated, read_file for "
                     "the working copy and write_file to repair it.",
    "git_resolve": "Stage a repaired conflict file, using its current SHA-256 from read_file. "
                   "All conflict markers must be removed. For an intentional deletion first delete_file "
                   "then call with delete=true. Finish all files and git_commit to complete the merge.",
    "git_remote": "Attach this project's origin. Pass an existing https URL, or omit url to create a "
                  "GitHub repository with the token saved in Код → Git (name defaults to the project "
                  "folder, private defaults to true) and attach it. Then git_commit if needed and git_push. "
                  "Never tell the user to run git remote or git push in a terminal.",
}


def can_use(permissions: list[str] | None) -> bool:
    return permissions is None or GIT_PERMISSION in permissions


def specs(mode: str) -> list[dict]:
    names = [n for n in _SCHEMAS if not (mode in ("plan", "review") and n in GIT_MUTATING)]
    return [{"type": "function", "function": {"name": n, "description": _DESCRIPTIONS[n],
                                              "parameters": _SCHEMAS[n].model_json_schema()}} for n in names]


def label(name: str, arguments: dict) -> str:
    if name == "git_commit":
        return f"git commit — {str(arguments.get('message') or '')[:200]}"
    if name == "git_push":
        return f"git push {arguments.get('branch') or ''}".strip()
    return name.replace("_", " ")


class GitAgent:
    """Git одного проекта от имени пользователя; токен хостинга — через credential()."""

    def __init__(self, root: str, author: str, email: str,
                 credential: Callable[[str | None], Awaitable[tuple[str | None, str | None]]], *, publish_branch=None) -> None:
        self.root = root
        self.author = author
        self.email = email
        self.credential = credential
        self.publish_branch = publish_branch

    async def call(self, name: str, arguments: dict) -> dict:
        schema = _SCHEMAS.get(name)
        if schema is None:
            return {"error": "Неизвестный инструмент"}
        try:
            args = schema.model_validate(arguments or {})
            if name in ("git_push", "git_sync") and self.publish_branch is not None:
                if args.branch is not None and args.branch != self.publish_branch:
                    return {"error": "Рабочая копия публикуется только в свою отдельную ветку: " + self.publish_branch}
                args.branch = self.publish_branch
        except ValidationError as exc:
            fields = ", ".join(".".join(map(str, e["loc"])) or e["msg"] for e in exc.errors())
            return {"error": f"Некорректные аргументы инструмента: {fields}"}
        try:
            if name == "git_status":
                state = await gitops.status(self.root)
                if state.get("initialized"):
                    state["changes"] = state["changes"][:100]
                return state
            if name == "git_log":
                return {"commits": await gitops.log(self.root, args.limit)}
            if name == "git_diff":
                data = await gitops.diff(self.root)
                text = data["diff"]
                cut = len(text) > MODEL_DIFF
                return {"diff": text[:MODEL_DIFF] + ("\n…[дифф обрезан]" if cut else ""),
                        "truncated": cut or data["truncated"]}
            if name == "git_commit":
                done = await gitops.commit(self.root, args.message, self.author, self.email)
                return {"commit": done}
            if name == "git_conflicts":
                return await gitops.conflicts(self.root, args.path)
            if name == "git_resolve":
                return await gitops.resolve(self.root, args.path, args.expected_sha256, args.delete)
            if name == "git_sync":
                remote = (await gitops.status(self.root)).get("remote")
                username, token = await self.credential(remote)
                return await gitops.synchronize(self.root, token, username, args.branch, self.author, self.email)
            if name == "git_push":
                remote = (await gitops.status(self.root)).get("remote")
                username, token = await self.credential(remote)
                done = await gitops.push(self.root, token, username, args.branch, self.author, self.email)
                return {"branch": done["branch"], "output": done["output"][-1500:]}
            if name == "git_remote":
                from pathlib import Path
                if not gitops.is_repo(self.root):
                    await gitops.init(self.root)
                if args.url:
                    return await gitops.set_remote(self.root, args.url)
                _, token = await self.credential("https://github.com/")
                if not token:
                    return {"error": "В Код → Git нет токена github.com. Добавьте его, и я создам репозиторий и отправлю код."}
                created = await gitops.create_github_repo(token, args.name or Path(self.root).name, args.private)
                state = await gitops.set_remote(self.root, created["clone_url"])
                return {**state, "created": created["created"], "html_url": created["html_url"]}
        except gitops.GitError as exc:
            return {"error": str(exc)}
        return {"error": "Неизвестный инструмент"}

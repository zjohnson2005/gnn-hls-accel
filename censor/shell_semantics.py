"""Reversibility classification from FULL command strings.

The verb alphabet is not a classifier and must never be used as one. In this
corpus, `sed` reads on one turn and writes in place on the next; `awk` reads
until it is followed by `>`; `git diff` reads while `git commit` does not. The
OA-01 atlas even labels a turn whose only command is `rm head.tmp tail.tmp ...`
as step_type_semantic="inspect".

So: scan the raw string, tracking quote state, honouring heredocs, and decide
from observed EFFECTS (redirects, in-place flags, deletions, repo-state
mutations, network egress) rather than from the leading token.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import IntEnum

SUBMIT_SENTINEL = "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"


class Reversibility(IntEnum):
    """Ordered by severity so a turn can take the max over its commands."""

    READ_ONLY = 0
    RECOVERABLE = 1
    IRREVERSIBLE = 2
    AMBIGUOUS = 3  # not a severity; handled explicitly at aggregation


# Verbs that mutate nothing on their own. A redirect can still make them write,
# which is why this set is only consulted AFTER effect scanning.
READ_VERBS = {
    "ls", "cat", "head", "tail", "grep", "egrep", "fgrep", "rg", "find", "awk",
    "sed", "diff", "wc", "pwd", "echo", "printf", "file", "stat", "which",
    "type", "tree", "sort", "uniq", "cut", "tr", "basename", "dirname",
    "readlink", "realpath", "du", "df", "date", "env", "true", "false", "test",
    "[", "nl", "od", "xxd", "md5sum", "sha1sum", "sha256sum", "column", "less",
    "more", "comm", "join", "paste", "seq", "yes", "sleep", "time", "expr",
}

# Read-only git subcommands.
GIT_READ = {
    "diff", "log", "status", "show", "branch", "blame", "ls-files", "rev-parse",
    "describe", "cat-file", "config", "remote", "shortlog", "grep", "tag",
}
# Git subcommands that change index/worktree/history and can destroy work.
GIT_DESTRUCTIVE = {
    "checkout", "reset", "clean", "stash", "commit", "revert", "rebase",
    "merge", "cherry-pick", "restore", "switch", "am", "apply", "push", "pull",
    "fetch", "clone", "rm", "mv", "init",
}
GIT_RECOVERABLE = {"add"}

DELETE_VERBS = {"rm", "rmdir", "unlink", "shred", "truncate"}
WRITE_VERBS = {"cp", "mv", "mkdir", "touch", "ln", "install", "tee", "dd",
               "chmod", "chown", "patch", "tar", "unzip", "zip", "gzip",
               "gunzip", "split", "apply_patch"}
NETWORK_VERBS = {"curl", "wget", "pip", "pip3", "apt", "apt-get", "yum", "dnf",
                 "conda", "npm", "yarn", "ssh", "scp", "rsync", "nc", "netcat",
                 "telnet", "ftp", "git-lfs"}
# Arbitrary-effect interpreters and interactive editors: not classifiable from
# the command line alone.
AMBIGUOUS_VERBS = {"python", "python3", "py", "perl", "ruby", "node", "bash",
                   "sh", "zsh", "xargs", "eval", "exec", "source", ".", "make",
                   "nano", "vi", "vim", "emacs", "ed", "gdb", "tox", "nox"}
TEST_VERBS = {"pytest", "unittest", "nosetests", "coverage"}

# In-place edit flags, keyed by verb.
INPLACE_FLAGS = {
    "sed": ("-i",),
    "perl": ("-i",),
    "ruby": ("-i",),
    "gawk": ("-i", "inplace"),
}


@dataclass
class Effects:
    """What a single command string was observed to do."""

    segments: list[str] = field(default_factory=list)
    verbs: list[str] = field(default_factory=list)
    redirect_targets: list[str] = field(default_factory=list)
    appends: list[str] = field(default_factory=list)
    heredoc_delims: list[str] = field(default_factory=list)
    inplace: list[str] = field(default_factory=list)
    deletes: list[str] = field(default_factory=list)
    writes: list[str] = field(default_factory=list)
    repo_state: list[str] = field(default_factory=list)
    network: list[str] = field(default_factory=list)
    ambiguous: list[str] = field(default_factory=list)
    tests: list[str] = field(default_factory=list)
    submit: bool = False


_OPERATORS = ("&&", "||", "|", ";", "\n")


def _scan(cmd: str) -> Effects:
    """Split into pipeline segments and collect redirects, honouring quotes."""
    eff = Effects()
    i = 0
    n = len(cmd)
    seg: list[str] = []
    in_s = in_d = False
    pending_heredoc: str | None = None

    def flush() -> None:
        s = "".join(seg).strip()
        if s:
            eff.segments.append(s)
        seg.clear()

    while i < n:
        c = cmd[i]

        # Inside a heredoc body: skip until the delimiter line. The body is data,
        # not commands -- parsing it would invent effects that never happened.
        if pending_heredoc is not None:
            line_end = cmd.find("\n", i)
            if line_end == -1:
                line_end = n
            line = cmd[i:line_end]
            if line.strip() == pending_heredoc:
                pending_heredoc = None
            i = line_end + 1
            continue

        if c == "\\" and not in_s and i + 1 < n:
            seg.append(cmd[i:i + 2])
            i += 2
            continue
        if c == "'" and not in_d:
            in_s = not in_s
            seg.append(c)
            i += 1
            continue
        if c == '"' and not in_s:
            in_d = not in_d
            seg.append(c)
            i += 1
            continue
        if in_s or in_d:
            seg.append(c)
            i += 1
            continue

        # Heredoc start.
        if cmd.startswith("<<", i) and not cmd.startswith("<<<", i):
            j = i + 2
            if j < n and cmd[j] == "-":
                j += 1
            while j < n and cmd[j] == " ":
                j += 1
            m = re.match(r"""['"]?([A-Za-z_][A-Za-z0-9_]*)['"]?""", cmd[j:])
            if m:
                eff.heredoc_delims.append(m.group(1))
                # Body starts after this line.
                line_end = cmd.find("\n", j)
                pending_heredoc = m.group(1)
                seg.append(cmd[i:line_end if line_end != -1 else n])
                i = (line_end + 1) if line_end != -1 else n
                continue

        # Redirects. `2>&1` is a dup, not a file write.
        if c == ">":
            append = cmd.startswith(">>", i)
            j = i + (2 if append else 1)
            if j < n and cmd[j] == "&":
                seg.append(cmd[i:j + 2])
                i = j + 2
                continue
            while j < n and cmd[j] in " \t":
                j += 1
            m = re.match(r"""[^\s|;&<>]+""", cmd[j:])
            target = m.group(0) if m else "?"
            (eff.appends if append else eff.redirect_targets).append(target)
            seg.append(" ")
            i = j + (len(target) if m else 0)
            continue

        matched = None
        for op in _OPERATORS:
            if cmd.startswith(op, i):
                matched = op
                break
        if matched:
            flush()
            i += len(matched)
            continue

        seg.append(c)
        i += 1

    flush()
    return eff


def _tokens(segment: str) -> list[str]:
    out: list[str] = []
    cur: list[str] = []
    in_s = in_d = False
    i = 0
    while i < len(segment):
        c = segment[i]
        if c == "\\" and i + 1 < len(segment) and not in_s:
            cur.append(segment[i + 1])
            i += 2
            continue
        if c == "'" and not in_d:
            in_s = not in_s
            i += 1
            continue
        if c == '"' and not in_s:
            in_d = not in_d
            i += 1
            continue
        if c.isspace() and not in_s and not in_d:
            if cur:
                out.append("".join(cur))
                cur = []
            i += 1
            continue
        cur.append(c)
        i += 1
    if cur:
        out.append("".join(cur))
    return out


def analyze(cmd: str) -> Effects:
    """Full-string effect analysis of one bash invocation."""
    eff = _scan(cmd)
    if SUBMIT_SENTINEL in cmd:
        eff.submit = True

    for seg in eff.segments:
        toks = _tokens(seg)
        # Strip leading VAR=value assignments and `sudo`/`env`.
        k = 0
        while k < len(toks) and (re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", toks[k])
                                 or toks[k] in {"sudo", "nohup", "command"}):
            k += 1
        if k >= len(toks):
            continue
        verb = toks[k].rsplit("/", 1)[-1]
        args = toks[k + 1:]
        eff.verbs.append(verb)

        if verb == "env" and args:
            verb = args[0]
            args = args[1:]

        flags = [a for a in args if a.startswith("-")]
        positional = [a for a in args if not a.startswith("-")]

        # In-place edit flags (sed -i, perl -i, sed -i.bak, combined -ni).
        ip = INPLACE_FLAGS.get(verb)
        if ip and any(
            f == ip[0] or f.startswith(ip[0])
            or (f.startswith("-") and not f.startswith("--") and "i" in f[1:])
            for f in flags
        ):
            eff.inplace.append(seg)
            continue

        if verb in NETWORK_VERBS:
            eff.network.append(seg)
            continue
        if verb in DELETE_VERBS:
            eff.deletes.append(seg)
            continue
        if verb == "git":
            sub = next((a for a in args if not a.startswith("-")), "")
            if sub in GIT_DESTRUCTIVE:
                eff.repo_state.append(seg)
            elif sub in GIT_RECOVERABLE:
                eff.writes.append(seg)
            elif sub not in GIT_READ:
                eff.ambiguous.append(seg)
            continue
        if verb in WRITE_VERBS:
            # `mv` removes the source as well as creating the destination.
            (eff.deletes if verb == "mv" else eff.writes).append(seg)
            continue
        if verb in TEST_VERBS:
            eff.tests.append(seg)
            continue
        if verb in AMBIGUOUS_VERBS:
            # `python -m pytest` is a test run, not arbitrary code.
            if verb.startswith("py") and "pytest" in args:
                eff.tests.append(seg)
            elif verb in {"python", "python3", "py"} and "-m" in args and any(
                a in {"unittest", "pytest", "compileall", "json.tool"} for a in args
            ):
                eff.tests.append(seg)
            else:
                eff.ambiguous.append(seg)
            continue
        if verb in READ_VERBS:
            continue
        eff.ambiguous.append(seg)
        _ = positional
    return eff


def classify(cmd: str) -> tuple[str, str, Effects]:
    """Return (class, rationale, effects) for one full command string."""
    eff = analyze(cmd)

    if eff.submit:
        return ("IRREVERSIBLE", "submits final answer (task-terminating, external)", eff)
    if eff.network:
        return ("IRREVERSIBLE", f"network egress: {eff.network[0][:80]}", eff)
    if eff.deletes:
        return ("IRREVERSIBLE", f"deletes/moves content: {eff.deletes[0][:80]}", eff)
    if eff.repo_state:
        return ("IRREVERSIBLE", f"mutates git state: {eff.repo_state[0][:80]}", eff)
    if eff.ambiguous:
        return ("AMBIGUOUS", f"arbitrary-effect or unknown verb: {eff.ambiguous[0][:80]}", eff)
    if eff.inplace:
        return ("RECOVERABLE", f"in-place edit under VCS: {eff.inplace[0][:80]}", eff)
    if eff.redirect_targets or eff.appends:
        tgt = (eff.redirect_targets + eff.appends)[0]
        return ("RECOVERABLE", f"writes file via redirect -> {tgt}", eff)
    if eff.writes:
        return ("RECOVERABLE", f"creates/copies file: {eff.writes[0][:80]}", eff)
    if eff.tests:
        return ("RECOVERABLE", f"test execution (may write caches/artifacts): {eff.tests[0][:80]}", eff)
    return ("READ_ONLY", "no observed write, delete, repo-state or network effect", eff)


SEVERITY = {"READ_ONLY": 0, "RECOVERABLE": 1, "IRREVERSIBLE": 2}


def classify_turn(commands: list[str]) -> tuple[str, str]:
    """Aggregate over a turn's commands: worst class wins, AMBIGUOUS is sticky
    unless something strictly worse is present."""
    if not commands:
        return ("NO_COMMAND", "turn issued no shell command")
    classes = [classify(c) for c in commands]
    if any(c[0] == "IRREVERSIBLE" for c in classes):
        w = next(c for c in classes if c[0] == "IRREVERSIBLE")
        return ("IRREVERSIBLE", w[1])
    if any(c[0] == "AMBIGUOUS" for c in classes):
        w = next(c for c in classes if c[0] == "AMBIGUOUS")
        return ("AMBIGUOUS", w[1])
    worst = max(classes, key=lambda c: SEVERITY[c[0]])
    return (worst[0], worst[1])

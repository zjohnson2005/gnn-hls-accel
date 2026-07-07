"""Concrete task suite: every session executes a specific named task.

Tasks are basic, everyday questions, but each task archetype stresses a
different structural mechanism of the serving harness, which is what the
experiment analysis groups by:

  SH search_heavy       repeated independent searches
  CH code_heavy         local snippet execution
  RH rag_heavy          large retrieval results
  RE reasoning_heavy    few tools, long think turns
  LH long_horizon       state grows within one session (context copy cost)
  FO fanout             many parallel calls in one turn (dispatch burst)
  CN chain              tool output feeds next tool input (handoff cost)
  SW swarm              parent spawns sub-agents (repeated ORCH_SETUP)
  SO structured_output  emit + validate growing JSON every turn (encode)
  AH api_heavy          mock remote APIs (HTTP_CLIENT envelopes, I/O wait)
  MX mixed cross-tool   every transition type in one session

Turn model: a turn is zero or more ToolCalls (zero = reasoning-only).
Multiple calls in one turn form a fan-out burst whose completions land
back-to-back. pipe_result=True feeds the previous tool result into this
call's arguments (chained handoff). structured_emit turns re-emit and
validate the full accumulated JSON artifact. subagent_goals spawn child
sessions with their own task graphs.

Task assignment is deterministic: session i with seed s runs
tasks_for_profile(profile)[(s + i) % len]. The full task script is
recorded in every run artifact.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ToolCall:
    tool: str  # search | code_exec | retrieve | calculator | api
    query: str = ""
    pipe_result: bool = False  # feed previous tool result into this call


@dataclass(frozen=True)
class TurnSpec:
    calls: tuple[ToolCall, ...] = ()
    structured_emit: bool = False
    subagent_goals: tuple[str, ...] = ()

    def summary(self) -> str:
        if self.subagent_goals:
            return f"spawn sub-agents: {', '.join(self.subagent_goals)}"
        parts = []
        if not self.calls:
            parts.append("reasoning only")
        elif len(self.calls) == 1:
            c = self.calls[0]
            pipe = " (piped from previous result)" if c.pipe_result else ""
            q = c.query.replace("\n", " ").strip()[:100]
            parts.append(f"{c.tool} <- {q}{pipe}")
        else:
            inner = "; ".join(
                f"{c.tool}: {c.query.replace(chr(10), ' ').strip()[:40]}" for c in self.calls
            )
            parts.append(f"fan-out {len(self.calls)} calls [{inner}]")
        if self.structured_emit:
            parts.append("emit + validate structured JSON")
        return "; ".join(parts)


def T(tool: str, query: str = "", pipe: bool = False) -> TurnSpec:
    return TurnSpec(calls=(ToolCall(tool, query, pipe),))


def R() -> TurnSpec:
    return TurnSpec()


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    profile: str
    goal: str
    turns: tuple[TurnSpec, ...]

    def tool_counts_per_turn(self) -> list[int]:
        return [len(t.calls) for t in self.turns]

    def describe(self) -> dict:
        return {
            "task_id": self.task_id,
            "profile": self.profile,
            "goal": self.goal,
            "turns": [t.summary() for t in self.turns],
        }


# Code snippets. Bounded, deterministic, real compute.
SNIPPET_PRIMES = """
limit = 20000
sieve = [True] * limit
sieve[0] = sieve[1] = False
for i in range(2, int(limit ** 0.5) + 1):
    if sieve[i]:
        for j in range(i * i, limit, i):
            sieve[j] = False
result = sum(i for i, p in enumerate(sieve) if p)
"""

SNIPPET_FIB = """
a, b = 0, 1
for _ in range(50000):
    a, b = b, (a + b) % 1000000007
result = a
"""

SNIPPET_COMPOUND_INTEREST = """
balance = 1000.0
rate = 0.05
for year in range(30):
    balance = balance * (1 + rate)
result = int(balance * 100) / 100
"""

SNIPPET_WORDCOUNT = """
text = ("the quick brown fox jumps over the lazy dog and runs away " * 800).split()
counts = {}
for w in text:
    counts[w] = counts.get(w, 0) + 1
result = max(counts.values())
"""

SNIPPET_MEDIAN = """
xs = [(i * 2654435761) % 100003 for i in range(30000)]
xs.sort()
result = xs[len(xs) // 2]
"""

# CN-01 step 3: prev holds the piped Fahrenheit conversion result.
SNIPPET_OVEN_CHECK = """
boiling_f = 212
oven_f = 200
result = 1 if oven_f >= boiling_f else 0
"""

# MX-01: budget loop; prev holds the piped ingredient retrieval excerpt.
SNIPPET_BUDGET = """
kids = 10
snacks = [("pancake mix", 3.5), ("syrup", 4.0), ("berries", 6.0), ("juice", 2.5)]
total = 0.0
for name, price in snacks:
    total += price
result = int(total * 100 + kids) / 100
"""


TASKS: tuple[TaskSpec, ...] = (
    # ------------------------------------------------------------ search_heavy
    TaskSpec(
        task_id="SH-01",
        profile="search_heavy",
        goal="What causes different kinds of weather? Collect mentions of "
        "rain, storms, and temperature changes and summarize the patterns.",
        turns=(
            T("search", "rain storm"),
            T("search", "temperature cold warm"),
            T("search", "wind forecast"),
            T("search", "snow season"),
            T("search", "climate humidity"),
            T("search", "cloud sun"),
            T("calculator", "(72 - 32) * 5 / 9"),
            T("search", "storm wind rain"),
            T("search", "season climate"),
            R(),
        ),
    ),
    TaskSpec(
        task_id="SH-02",
        profile="search_heavy",
        goal="Put together a short overview of space topics: find what the "
        "corpus says about planets, the moon, eclipses, and telescopes.",
        turns=(
            T("search", "planet orbit"),
            T("search", "moon eclipse"),
            T("search", "solar eclipse"),
            T("search", "telescope star"),
            T("search", "rocket astronaut"),
            T("retrieve", "which planets can be seen without a telescope"),
            T("search", "mars earth"),
            T("search", "gravity light"),
            T("search", "galaxy star"),
            T("search", "orbit gravity"),
            R(),
        ),
    ),
    # -------------------------------------------------------------- code_heavy
    TaskSpec(
        task_id="CH-01",
        profile="code_heavy",
        goal="What is the sum of all prime numbers below 20000? Verify with "
        "a second computation and sanity-check the magnitude.",
        turns=(
            T("code_exec", SNIPPET_PRIMES),
            T("code_exec", SNIPPET_MEDIAN),
            T("calculator", "21171191 / 1000000"),
            T("code_exec", SNIPPET_FIB),
            R(),
        ),
    ),
    TaskSpec(
        task_id="CH-02",
        profile="code_heavy",
        goal="If I save 1000 dollars at 5 percent interest for 30 years, how "
        "much do I have? Also check a word-frequency count and a median.",
        turns=(
            T("code_exec", SNIPPET_COMPOUND_INTEREST),
            T("code_exec", SNIPPET_WORDCOUNT),
            T("code_exec", SNIPPET_MEDIAN),
            T("search", "bank interest save"),
            T("calculator", "1000 * 1.05 ** 30"),
            R(),
        ),
    ),
    # --------------------------------------------------------------- rag_heavy
    TaskSpec(
        task_id="RH-01",
        profile="rag_heavy",
        goal="Answer five basic nature questions using retrieval: how plants "
        "grow, the water cycle, rivers and oceans, forests, and birds.",
        turns=(
            T("retrieve", "how do plants grow from soil and water"),
            T("retrieve", "what is the water cycle rain river ocean"),
            T("retrieve", "why do rivers flow into the ocean"),
            T("retrieve", "what animals live in a forest"),
            T("retrieve", "where do birds go in winter"),
            T("search", "tree leaf forest"),
            R(),
        ),
    ),
    TaskSpec(
        task_id="RH-02",
        profile="rag_heavy",
        goal="Build a simple guide to home baking by retrieving passages "
        "about bread, ingredients, and oven technique.",
        turns=(
            T("retrieve", "how to bake bread with flour and butter"),
            T("retrieve", "what temperature should the oven be for baking"),
            T("retrieve", "how much sugar and salt goes in a recipe"),
            T("calculator", "350 / 2 + 25"),
            T("retrieve", "difference between baking with butter and oil"),
            T("retrieve", "how long should bread rest before cutting"),
            T("retrieve", "simple dinner recipes with vegetables and cheese"),
            R(),
        ),
    ),
    # --------------------------------------------------------- reasoning_heavy
    TaskSpec(
        task_id="RE-01",
        profile="reasoning_heavy",
        goal="A train leaves at 9am going 80 km per hour and another leaves "
        "at 10am going 100 km per hour on the same route. Reason through "
        "when the second catches the first, and verify the arithmetic.",
        turns=(
            R(),
            R(),
            T("calculator", "80 / (100 - 80)"),
            R(),
        ),
    ),
    TaskSpec(
        task_id="RE-02",
        profile="reasoning_heavy",
        goal="Is it better to sleep eight hours or exercise an extra hour? "
        "Reason through the trade-offs, checking one fact in the corpus.",
        turns=(
            R(),
            T("search", "sleep exercise energy"),
            R(),
            R(),
        ),
    ),
    # -------------------------------------------------------- long_horizon
    TaskSpec(
        task_id="LH-01",
        profile="long_horizon",
        goal="Help me plan a vegetable garden for the whole year, month by "
        "month. One retrieval per month; the growing plan accumulates in "
        "context, so state copies and token counts grow within the session.",
        turns=(
            T("retrieve", "what vegetables grow in january winter"),
            T("retrieve", "what to plant in february cold soil"),
            T("retrieve", "what vegetables grow in early spring march"),
            T("retrieve", "when to plant tomatoes in april"),
            T("retrieve", "what to plant in may after last frost"),
            T("retrieve", "which vegetables handle summer heat in june"),
            T("retrieve", "watering schedule for july vegetable garden"),
            T("retrieve", "what to harvest and replant in august"),
            T("retrieve", "what vegetables grow in september fall"),
            T("retrieve", "which crops survive october frost"),
            T("retrieve", "preparing garden soil in november"),
            T("retrieve", "what can grow in december indoors"),
            R(),
        ),
    ),
    TaskSpec(
        task_id="LH-02",
        profile="long_horizon",
        goal="Teach me basic cooking, one lesson at a time, and quiz me as "
        "we go. Alternates retrieval, quiz-composition reasoning, and a "
        "calculator check on a scaled recipe. Long and chatty; state "
        "accumulates every turn.",
        turns=(
            T("retrieve", "how to boil an egg step by step"),
            R(),
            T("calculator", "2 * 3 / 4"),
            T("retrieve", "what does simmer mean in cooking"),
            R(),
            T("calculator", "1.5 * 2 / 3"),
            T("retrieve", "how to chop an onion safely"),
            R(),
            T("calculator", "3 * 1 / 2"),
            T("retrieve", "how do I know when pasta is done"),
            R(),
            R(),
        ),
    ),
    # -------------------------------------------------------------- fanout
    TaskSpec(
        task_id="FO-01",
        profile="fanout",
        goal="Compare the weather, best food, and main attractions of Paris, "
        "Tokyo, and Cairo. Nine searches fan out in one turn; their "
        "completions land nearly simultaneously (dispatch burst), then one "
        "merge turn.",
        turns=(
            TurnSpec(
                calls=(
                    ToolCall("search", "paris weather forecast rain"),
                    ToolCall("search", "paris food recipe cheese"),
                    ToolCall("search", "paris museum castle history"),
                    ToolCall("search", "tokyo weather season wind"),
                    ToolCall("search", "tokyo food fish dinner"),
                    ToolCall("search", "tokyo city station bridge"),
                    ToolCall("search", "cairo weather sun warm"),
                    ToolCall("search", "cairo food bread market"),
                    ToolCall("search", "cairo ancient museum empire"),
                )
            ),
            R(),
        ),
    ),
    # --------------------------------------------------------------- chain
    TaskSpec(
        task_id="CN-01",
        profile="chain",
        goal="Find the boiling point of water at sea level, convert it to "
        "Fahrenheit, then tell me if an oven at 200 degrees F could boil "
        "water. Strict three-step chain: each tool's result is the next "
        "tool's argument (pair-wise handoff cost).",
        turns=(
            T("retrieve", "boiling point of water at sea level"),
            T("calculator", "100 * 9 / 5 + 32", pipe=True),
            T("code_exec", SNIPPET_OVEN_CHECK, pipe=True),
            R(),
        ),
    ),
    # --------------------------------------------------------------- swarm
    TaskSpec(
        task_id="SW-01",
        profile="swarm",
        goal="Give me a short report on healthy living: one section each on "
        "food, sleep, and exercise. Parent spawns three sub-agents, each "
        "with its own task graph (repeated ORCH_SETUP), waits, and merges.",
        turns=(
            TurnSpec(subagent_goals=("food", "sleep", "exercise")),
            R(),
        ),
    ),
    # ---------------------------------------------------- structured_output
    TaskSpec(
        task_id="SO-01",
        profile="structured_output",
        goal="Make me a shopping list for a pancake breakfast, with item, "
        "quantity, and aisle for each entry. Every turn re-emits and "
        "validates the full corrected JSON list (encode-side stress).",
        turns=(
            T("retrieve", "pancake ingredients flour sugar butter"),
            T("retrieve", "grocery store aisle layout fruit vegetable"),
            TurnSpec(structured_emit=True),
            TurnSpec(structured_emit=True),
            TurnSpec(structured_emit=True),
            TurnSpec(structured_emit=True),
            R(),
        ),
    ),
    # ------------------------------------------------------------ api_heavy
    TaskSpec(
        task_id="AH-01",
        profile="api_heavy",
        goal="What time is it right now in London, New York, and Sydney, and "
        "what is 100 dollars in each local currency? Six mock remote-API "
        "calls (near-zero local compute, all envelopes and I/O wait), one "
        "calculator per conversion.",
        turns=(
            TurnSpec(
                calls=(
                    ToolCall("api", "GET /v1/timezone?city=london"),
                    ToolCall("api", "GET /v1/timezone?city=new_york"),
                    ToolCall("api", "GET /v1/timezone?city=sydney"),
                )
            ),
            TurnSpec(
                calls=(
                    ToolCall("api", "GET /v1/exchange?from=usd&to=gbp"),
                    ToolCall("api", "GET /v1/exchange?from=usd&to=usd"),
                    ToolCall("api", "GET /v1/exchange?from=usd&to=aud"),
                )
            ),
            T("calculator", "100 * 0.79"),
            T("calculator", "100 * 1.00"),
            T("calculator", "100 * 1.52"),
            R(),
        ),
    ),
    # ------------------------------------------------------- mixed cross-tool
    TaskSpec(
        task_id="MX-01",
        profile="mixed",
        goal="Plan a birthday party for ten kids: theme ideas, a snack "
        "budget, and a schedule. Crosses every tool in one session: "
        "searches, a large retrieval feeding code_exec, a calculator "
        "check, and a structured JSON schedule at the end.",
        turns=(
            T("search", "party theme fun kids"),
            T("search", "snack fruit juice dinner"),
            T("retrieve", "easy snack recipes for a group of children"),
            T("code_exec", SNIPPET_BUDGET, pipe=True),
            T("calculator", "160.10 / 10", pipe=True),
            TurnSpec(structured_emit=True),
            R(),
        ),
    ),
)


# Sub-agent mini-tasks for SW-01: each child does two searches and one
# retrieval on its section, with its own OrchEngine graph.
SUBTASKS: dict[str, TaskSpec] = {
    "food": TaskSpec(
        task_id="SW-01.food",
        profile="swarm",
        goal="Section: healthy food basics.",
        turns=(
            T("search", "vegetable fruit healthy"),
            T("search", "sugar salt diet"),
            T("retrieve", "what makes a balanced healthy meal"),
            R(),
        ),
    ),
    "sleep": TaskSpec(
        task_id="SW-01.sleep",
        profile="swarm",
        goal="Section: sleep basics.",
        turns=(
            T("search", "sleep rest brain"),
            T("search", "sleep energy healthy"),
            T("retrieve", "how many hours of sleep do adults need"),
            R(),
        ),
    ),
    "exercise": TaskSpec(
        task_id="SW-01.exercise",
        profile="swarm",
        goal="Section: exercise basics.",
        turns=(
            T("search", "exercise muscle heart"),
            T("search", "walk run energy"),
            T("retrieve", "simple exercise routine for beginners"),
            R(),
        ),
    ),
}


def tasks_for_profile(profile: str) -> tuple[TaskSpec, ...]:
    if profile == "mixed":
        return TASKS
    subset = tuple(t for t in TASKS if t.profile == profile)
    return subset if subset else TASKS


def assign_task(profile: str, seed: int, session_index: int) -> TaskSpec:
    pool = tasks_for_profile(profile)
    return pool[(seed + session_index) % len(pool)]


def task_by_id(task_id: str) -> TaskSpec:
    for task in TASKS:
        if task.task_id == task_id:
            return task
    raise KeyError(f"unknown task_id: {task_id!r}")


# Tasks that invoke search in the baseline real-agent run (mixed seed 0).
DEFAULT_LOCALITY_ABLATION_TASKS: tuple[str, ...] = (
    "SH-01",
    "SH-02",
    "CH-02",
    "RE-02",
    "RH-01",
)


def suite_digest() -> str:
    import hashlib

    def turn_blob(t: TurnSpec) -> str:
        calls = ",".join(f"{c.tool}:{c.query}:{c.pipe_result}" for c in t.calls)
        return f"{calls}|{t.structured_emit}|{','.join(t.subagent_goals)}"

    blob = "|".join(
        f"{t.task_id}:{t.goal}:{';'.join(turn_blob(x) for x in t.turns)}"
        for t in TASKS + tuple(SUBTASKS.values())
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]

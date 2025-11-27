from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from math import log1p
from typing import Any, Dict, List, Optional, Set, Tuple

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator

# Strategy weights (sum ~ 1.0). Bigger differences => visibly different scores.
StrategyWeights = Dict[str, float]
STRATEGY_WEIGHTS: Dict[str, StrategyWeights] = {
    "fastest_wins": {"urgency": 0.15, "importance": 0.15, "quickwin": 0.60, "blocker": 0.10},
    "high_impact": {"urgency": 0.15, "importance": 0.65, "quickwin": 0.05, "blocker": 0.15},
    "deadline_driven": {"urgency": 0.75, "importance": 0.20, "quickwin": 0.03, "blocker": 0.02},
    "smart_balance": {"urgency": 0.40, "importance": 0.35, "quickwin": 0.15, "blocker": 0.10},
}
DEFAULT_STRATEGY = "smart_balance"
DEFAULT_SUGGEST_LIMIT = 3
INDIA_HOLIDAYS_FIXED = {
    (1, 1),
    (1, 26),
    (5, 1),
    (8, 15),
    (10, 2),
    (12, 25),
}


@dataclass(frozen=True)
class NormalizedTask:
    """Internal representation for scoring logic."""

    id: int
    title: str
    due_date: Optional[date]
    estimated_hours: Optional[float]
    importance: Optional[int]  # 1..10
    dependencies: List[int]


# -------------------------
# Normalization helpers
# -------------------------
def _parse_date(value: Any) -> Optional[date]:
    if value in (None, "", []):
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)  # YYYY-MM-DD
        except ValueError:
            return None
    return None


def _parse_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        v = float(value)
        return None if v <= 0 else v
    except Exception:
        return None


def _clamp_int(value: Any, lo: int, hi: int) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        v = int(value)
        return max(lo, min(hi, v))
    except Exception:
        return None


def normalize_tasks(raw_tasks: List[Dict[str, Any]]) -> Tuple[List[NormalizedTask], List[str]]:
    """Validate and coerce user-provided tasks into a consistent shape."""
    warnings: List[str] = []
    tasks: List[NormalizedTask] = []

    for idx, t in enumerate(raw_tasks):
        # id
        tid_raw = t.get("id", idx + 1)
        try:
            tid = int(tid_raw)
        except Exception:
            tid = idx + 1
            warnings.append(f"Task at index {idx}: invalid id '{tid_raw}' -> auto-assigned {tid}")

        # title
        title = str(t.get("title", "")).strip() or f"Untitled Task {tid}"

        # due_date
        due = _parse_date(t.get("due_date"))
        if t.get("due_date") not in (None, "", []) and due is None:
            warnings.append(f"Task {tid}: invalid due_date -> treated as missing")

        # hours
        hours = _parse_float(t.get("estimated_hours"))
        if t.get("estimated_hours") not in (None, "", []) and hours is None:
            warnings.append(
                f"Task {tid}: estimated_hours must be a positive number -> treated as missing"
            )

        # importance
        importance = _clamp_int(t.get("importance"), 1, 10)
        if t.get("importance") not in (None, "", []) and importance is None:
            warnings.append(f"Task {tid}: invalid importance -> treated as missing")

        # dependencies
        deps_raw = t.get("dependencies") or []
        deps: List[int] = []
        if not isinstance(deps_raw, list):
            warnings.append(f"Task {tid}: dependencies is not a list -> ignored")
            deps_raw = []
        for d in deps_raw:
            try:
                deps.append(int(d))
            except Exception:
                warnings.append(f"Task {tid}: dependency '{d}' invalid -> ignored")

        tasks.append(
            NormalizedTask(
                id=tid,
                title=title,
                due_date=due,
                estimated_hours=hours,
                importance=importance,
                dependencies=deps,
            )
        )

    return tasks, warnings


# -------------------------
# Graph utilities
# -------------------------
def _build_graph(tasks: List[NormalizedTask]) -> Tuple[Dict[int, NormalizedTask], Dict[int, List[int]], Dict[int, List[int]]]:
    tasks_by_id = {t.id: t for t in tasks}

    # forward edges: task -> its dependencies
    forward: Dict[int, List[int]] = {t.id: [d for d in t.dependencies if d in tasks_by_id] for t in tasks}

    # reverse edges: dep -> tasks that depend on dep
    reverse: Dict[int, List[int]] = {t.id: [] for t in tasks}
    for tid, deps in forward.items():
        for dep in deps:
            reverse[dep].append(tid)

    return tasks_by_id, forward, reverse


def detect_cycles(tasks_by_id: Dict[int, NormalizedTask]) -> List[List[int]]:
    """Return cycles in the dependency graph using DFS."""
    state: Dict[int, int] = {}  # 0=unvisited, 1=visiting, 2=visited
    stack: List[int] = []
    cycles: List[List[int]] = []

    def dfs(u: int) -> None:
        state[u] = 1
        stack.append(u)
        for v in tasks_by_id[u].dependencies:
            if v not in tasks_by_id:
                continue
            if state.get(v, 0) == 0:
                dfs(v)
            elif state.get(v) == 1 and v in stack:
                i = stack.index(v)
                cycles.append(stack[i:] + [v])
        stack.pop()
        state[u] = 2

    for tid in tasks_by_id:
        if state.get(tid, 0) == 0:
            dfs(tid)

    return cycles


def _cycle_nodes(cycles: List[List[int]]) -> Set[int]:
    s: Set[int] = set()
    for c in cycles:
        for x in c:
            s.add(x)
    return s


def _downstream_block_count(task_id: int, reverse: Dict[int, List[int]]) -> int:
    """Count tasks that (directly or transitively) depend on task_id."""
    seen: Set[int] = set()
    stack = list(reverse.get(task_id, []))
    while stack:
        u = stack.pop()
        if u in seen:
            continue
        seen.add(u)
        stack.extend(reverse.get(u, []))
    return len(seen)


def _is_non_working_day(candidate: date) -> bool:
    return candidate.weekday() >= 5 or (candidate.month, candidate.day) in INDIA_HOLIDAYS_FIXED


def _working_days_until(due: date, *, today: Optional[date] = None) -> int:
    today = today or date.today()
    if due < today:
        return -1
    days = 0
    cursor = today
    while cursor < due:
        if not _is_non_working_day(cursor):
            days += 1
        cursor += timedelta(days=1)
    return days


# -------------------------
# Scoring components (0..1)
# -------------------------
def _urgency(due: Optional[date], *, today: Optional[date] = None) -> float:
    """
    Continuous urgency:
    - overdue -> 1.0
    - due soon -> high
    - far away -> low
    - missing -> neutral-low
    """
    today = today or date.today()
    if due is None:
        return 0.25

    working_days = _working_days_until(due, today=today)
    if working_days < 0:
        return 1.0

    k = 5.0
    return 1.0 / (1.0 + (working_days / k))


def _importance(imp: Optional[int]) -> float:
    # normalize 1..10 to 0..1 (missing defaults to 5)
    v = imp if imp is not None else 5
    return (v - 1) / 9.0


def _quickwin(hours: Optional[float], max_hours: float) -> float:
    """
    Quick win score (higher is better):
    small hours => close to 1
    large hours => closer to 0
    Uses log scaling so 1..2 hrs gets rewarded, but not insanely.
    """
    if hours is None:
        hours = 4.0  # neutral assumption
    if max_hours <= 0:
        return 0.6
    # log normalize
    x = log1p(hours) / log1p(max_hours)
    return max(0.0, min(1.0, 1.0 - x))


def _blocker_score(block_count: int, cap: int = 8) -> float:
    """
    Blocks-other-tasks score:
    0 dependents -> low
    many downstream dependents -> high, capped.
    """
    return max(0.0, min(1.0, block_count / float(cap)))


# -------------------------
# Main scoring
# -------------------------
def score_tasks(
    tasks: List[NormalizedTask], *, strategy: str = DEFAULT_STRATEGY, today: Optional[date] = None
) -> Dict[str, Any]:
    """
    Compute score for each task according to the selected strategy.

    Returns a dictionary containing scored tasks (sorted), detected cycles, and
    the strategy used.
    """
    strategy_key = (strategy or DEFAULT_STRATEGY).strip().lower()
    weights = STRATEGY_WEIGHTS.get(strategy_key, STRATEGY_WEIGHTS[DEFAULT_STRATEGY])

    tasks_by_id, _forward, reverse = _build_graph(tasks)
    cycles = detect_cycles(tasks_by_id)
    cycle_set = _cycle_nodes(cycles)

    # for quickwin normalization
    max_hours = max([t.estimated_hours or 0 for t in tasks] + [1.0])

    scored: List[Dict[str, Any]] = []

    for t in tasks:
        u = _urgency(t.due_date, today=today)
        im = _importance(t.importance)
        qw = _quickwin(t.estimated_hours, max_hours=max_hours)

        downstream = _downstream_block_count(t.id, reverse)
        bl = _blocker_score(downstream)

        base = (
            weights["urgency"] * u
            + weights["importance"] * im
            + weights["quickwin"] * qw
            + weights["blocker"] * bl
        )

        # penalize tasks in dependency cycles (they’re risky/blocked)
        # 15% reduction if part of any cycle
        cycle_penalty = 0.15 if t.id in cycle_set else 0.0
        final = base * (1.0 - cycle_penalty)

        scored.append(
            {
                "id": t.id,
                "title": t.title,
                "due_date": t.due_date.isoformat() if t.due_date else None,
                "estimated_hours": t.estimated_hours,
                "importance": t.importance if t.importance is not None else 5,
                "dependencies": t.dependencies,
                "dependents": downstream,
                # scaled for UI
                "score": round(final * 100, 2),
                # richer explanation (easy to debug strategies)
                "explanation": (
                    f"U={round(u * 100)}%, I={round(im * 100)}%, QW={round(qw * 100)}%, "
                    f"Block={downstream} ({round(bl * 100)}%), "
                    f"cycle_penalty={int(cycle_penalty * 100)}% (strategy={strategy_key})"
                ),
            }
        )

    # Sort: score desc, then earlier due date, then higher importance
    def _sort_key(x: Dict[str, Any]) -> Tuple[float, str, int]:
        due = x["due_date"] or "9999-12-31"
        return (-x["score"], due, -(x["importance"] or 5))

    scored.sort(key=_sort_key)

    return {
        "tasks": scored,
        "cycles": cycles,
        "strategy_used": strategy_key,
    }


def _reason_for_task(task: Dict[str, Any]) -> str:
    parts = [f"Priority {task['score']}/100"]
    due_str = task.get("due_date")
    due_date_value = None
    if due_str:
        try:
            due_date_value = date.fromisoformat(due_str)
        except ValueError:
            due_date_value = None
    if due_date_value:
        workdays = _working_days_until(due_date_value)
        if workdays < 0:
            parts.append(f"overdue since {due_date_value.isoformat()}")
        else:
            parts.append(
                f"due in {workdays} working day(s) (weekends and India holidays skipped)"
            )
    if task.get("importance"):
        parts.append(f"importance {task['importance']}/10")
    if task.get("estimated_hours") is not None:
        parts.append(f"~{task['estimated_hours']}h effort")
    dependents = task.get("dependents") or 0
    if dependents:
        parts.append(f"unblocks {dependents} downstream task(s)")
    if task.get("dependencies"):
        parts.append(f"needs {len(task['dependencies'])} prerequisite task(s)")
    detail = task.get("explanation", "")
    if detail:
        parts.append(f"details: {detail}")
    return "; ".join([p for p in parts if p])


# -------------------------
# API layer
# -------------------------
class TaskPayload(BaseModel):
    title: Optional[str] = Field(None, description="Task title")
    due_date: Optional[str] = Field(None, description="ISO date string YYYY-MM-DD")
    estimated_hours: Optional[float] = Field(None, ge=0, description="Estimated effort in hours")
    importance: Optional[int] = Field(None, ge=1, le=10, description="Importance 1-10")
    dependencies: Optional[List[int]] = Field(default_factory=list, description="IDs this task depends on")
    id: Optional[int] = Field(None, description="Optional unique identifier")

    @validator("dependencies", pre=True, always=True)
    def ensure_list(cls, value: Any) -> List[int]:  # type: ignore[override]
        if value in (None, ""):
            return []
        if not isinstance(value, list):
            raise ValueError("dependencies must be a list of ids")
        return value

    class Config:
        schema_extra = {
            "example": {
                "id": 42,
                "title": "Fix login bug",
                "due_date": "2025-11-30",
                "estimated_hours": 3,
                "importance": 8,
                "dependencies": [1, 2],
            }
        }


class AnalyzeRequest(BaseModel):
    tasks: List[TaskPayload]
    strategy: Optional[str] = Field(DEFAULT_STRATEGY, description="Which weighting strategy to use")
    today: Optional[date] = Field(None, description="Override today's date for testing")

    @validator("strategy")
    def validate_strategy(cls, value: Optional[str]) -> str:  # type: ignore[override]
        if value is None:
            return DEFAULT_STRATEGY
        value = value.strip().lower()
        if value not in STRATEGY_WEIGHTS:
            raise ValueError(f"strategy must be one of {sorted(STRATEGY_WEIGHTS)}")
        return value


class SuggestionResponse(BaseModel):
    id: int
    title: str
    score: float
    due_date: Optional[str]
    importance: int
    estimated_hours: Optional[float]
    dependents: int = Field(0, description="How many tasks are unblocked by completing this one")
    dependencies: List[int] = Field(default_factory=list)
    explanation: str


app = FastAPI(title="Task Priority API", version="1.0.0")


@app.post("/api/tasks/analyze/")
def analyze_tasks(payload: AnalyzeRequest = Body(...)) -> JSONResponse:
    raw_tasks = [task.dict() for task in payload.tasks]
    tasks, warnings = normalize_tasks(raw_tasks)

    scored = score_tasks(tasks, strategy=payload.strategy or DEFAULT_STRATEGY, today=payload.today)

    response: Dict[str, Any] = {
        **scored,
        "warnings": warnings,
    }
    if scored["cycles"]:
        response["warnings"].append("Dependency cycles detected; scores include a penalty.")

    return JSONResponse(response)


@app.get("/api/tasks/suggest/", response_model=List[SuggestionResponse])
def suggest_tasks(
    tasks: str = Query(..., description="JSON list of task objects"),
    strategy: str = Query(DEFAULT_STRATEGY, description="Weighting strategy"),
    limit: int = Query(DEFAULT_SUGGEST_LIMIT, ge=1, le=20, description="How many suggestions to return"),
) -> List[SuggestionResponse]:
    try:
        parsed_tasks = json.loads(tasks)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid tasks JSON: {exc}")

    if not isinstance(parsed_tasks, list):
        raise HTTPException(status_code=400, detail="Tasks payload must be a JSON array")

    normalized, warnings = normalize_tasks(parsed_tasks)
    scored = score_tasks(normalized, strategy=strategy)
    sorted_tasks = scored["tasks"][:limit]

    if warnings:
        # Expose warnings via header so clients can surface them.
        raise HTTPException(status_code=422, detail={"warnings": warnings})

    suggestions = [
        SuggestionResponse(
            id=t["id"],
            title=t["title"],
            score=t["score"],
            due_date=t.get("due_date"),
            importance=t.get("importance", 5),
            estimated_hours=t.get("estimated_hours"),
            dependents=t.get("dependents", 0),
            dependencies=t.get("dependencies", []),
            explanation=_reason_for_task(t),
        )
        for t in sorted_tasks
    ]
    return suggestions


@app.get("/health")
def healthcheck() -> Dict[str, str]:
    return {"status": "ok"}


__all__ = [
    "app",
    "normalize_tasks",
    "score_tasks",
    "detect_cycles",
    "STRATEGY_WEIGHTS",
    "DEFAULT_STRATEGY",
]
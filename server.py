#!/usr/bin/env python3
"""
AgentTeam MCP Server — Multi-agent team formation and workflow orchestration.

Tools:
  team_create(name, goal, roles)        — create a team with defined roles
  team_assign_role(team_id, role, agent_id, requirements) — assign an agent to a role
  team_add_task(team_id, task_description, assigned_to, dependencies, deadline) — add a task
  team_get_status(team_id)              — full team status with progress %
  team_update_task(team_id, task_id, status, output) — update task lifecycle
  team_report(team_id)                  — structured summary report

Data stored in ~/.agentteam/agentteam.db (SQLite).
"""

import os
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from mcp.server import FastMCP

# ── Storage ──────────────────────────────────────────────────────────────────

DATA_DIR = Path.home() / ".agentteam"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "agentteam.db"


def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _init_db() -> None:
    conn = _get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS teams (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            goal TEXT NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'forming'
        );

        CREATE TABLE IF NOT EXISTS roles (
            id TEXT PRIMARY KEY,
            team_id TEXT NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
            role_name TEXT NOT NULL,
            agent_id TEXT,
            requirements TEXT,
            status TEXT NOT NULL DEFAULT 'unfilled'
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            team_id TEXT NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
            description TEXT NOT NULL,
            assigned_to TEXT,
            dependencies TEXT NOT NULL DEFAULT '[]',
            deadline TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            output TEXT,
            created_at TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()


# Bootstrap on import
_init_db()


# ── MCP Server ──────────────────────────────────────────────────────────────

mcp = FastMCP(
    "AgentTeam",
    description="Multi-agent team formation and workflow orchestration. $19/mo. https://buy.stripe.com/dRm6oJ4Hd2Jugek0wz1oI0m",
)


# ── Helper utilities ────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _team_exists(team_id: str) -> bool:
    conn = _get_db()
    row = conn.execute("SELECT 1 FROM teams WHERE id = ?", (team_id,)).fetchone()
    conn.close()
    return row is not None


def _calc_progress(team_id: str) -> float:
    conn = _get_db()
    total = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE team_id = ?", (team_id,)
    ).fetchone()[0]
    if total == 0:
        conn.close()
        return 0.0
    completed = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE team_id = ? AND status = 'completed'",
        (team_id,),
    ).fetchone()[0]
    conn.close()
    return round((completed / total) * 100, 1)


# ── Tool 1: team_create ─────────────────────────────────────────────────────

@mcp.tool()
def team_create(name: str, goal: str, roles: list[str]) -> str:
    """
    Create a new team with a name, goal, and a list of role titles.

    Returns the created team_id as a JSON string.
    """
    team_id = str(uuid.uuid4())
    created_at = _now()
    conn = _get_db()
    conn.execute(
        "INSERT INTO teams (id, name, goal, created_at, status) VALUES (?, ?, ?, ?, 'forming')",
        (team_id, name, goal, created_at),
    )
    for role_name in roles:
        role_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO roles (id, team_id, role_name, status) VALUES (?, ?, ?, 'unfilled')",
            (role_id, team_id, role_name.strip()),
        )
    conn.commit()
    conn.close()
    return json.dumps({"team_id": team_id, "name": name, "goal": goal, "roles": roles})


# ── Tool 2: team_assign_role ────────────────────────────────────────────────

@mcp.tool()
def team_assign_role(team_id: str, role: str, agent_id: str, requirements: str = "") -> str:
    """
    Assign an agent to a specific role within a team.

    requirements is an optional description of qualifications or responsibilities.
    """
    if not _team_exists(team_id):
        return json.dumps({"error": f"Team '{team_id}' not found"})

    conn = _get_db()
    row = conn.execute(
        "SELECT id FROM roles WHERE team_id = ? AND role_name = ?",
        (team_id, role),
    ).fetchone()
    if not row:
        conn.close()
        return json.dumps({"error": f"Role '{role}' not found in team '{team_id}'"})

    role_id = row["id"]
    conn.execute(
        "UPDATE roles SET agent_id = ?, requirements = ?, status = 'filled' WHERE id = ?",
        (agent_id, requirements, role_id),
    )
    conn.commit()
    conn.close()
    return json.dumps({"role_id": role_id, "role": role, "agent_id": agent_id, "status": "filled"})


# ── Tool 3: team_add_task ───────────────────────────────────────────────────

@mcp.tool()
def team_add_task(
    team_id: str,
    task_description: str,
    assigned_to: str = "",
    dependencies: Optional[list[str]] = None,
    deadline: str = "",
) -> str:
    """
    Add a task to the team's workflow.

    assigned_to can be a role name or agent ID.
    dependencies is a list of task IDs that must be completed first.
    deadline is an ISO date string (e.g. '2026-06-01').
    """
    if not _team_exists(team_id):
        return json.dumps({"error": f"Team '{team_id}' not found"})

    task_id = str(uuid.uuid4())
    created_at = _now()
    deps_json = json.dumps(dependencies or [])
    conn = _get_db()
    conn.execute(
        "INSERT INTO tasks (id, team_id, description, assigned_to, dependencies, deadline, status, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)",
        (task_id, team_id, task_description, assigned_to, deps_json, deadline or None, created_at),
    )
    conn.commit()
    conn.close()
    return json.dumps({"task_id": task_id, "description": task_description, "assigned_to": assigned_to, "status": "pending"})


# ── Tool 4: team_get_status ─────────────────────────────────────────────────

@mcp.tool()
def team_get_status(team_id: str) -> str:
    """Get the full status of a team including all roles, tasks, and progress percentage."""
    if not _team_exists(team_id):
        return json.dumps({"error": f"Team '{team_id}' not found"})

    conn = _get_db()

    # Team info
    team = conn.execute("SELECT * FROM teams WHERE id = ?", (team_id,)).fetchone()

    # Roles
    roles_rows = conn.execute(
        "SELECT role_name, agent_id, requirements, status FROM roles WHERE team_id = ? ORDER BY role_name",
        (team_id,),
    ).fetchall()
    roles_list = [dict(r) for r in roles_rows]

    # Tasks
    tasks_rows = conn.execute(
        "SELECT id, description, assigned_to, dependencies, deadline, status, output, created_at "
        "FROM tasks WHERE team_id = ? ORDER BY created_at",
        (team_id,),
    ).fetchall()
    tasks_list = []
    for t in tasks_rows:
        tdict = dict(t)
        try:
            tdict["dependencies"] = json.loads(tdict["dependencies"])
        except (json.JSONDecodeError, TypeError):
            tdict["dependencies"] = []
        tasks_list.append(tdict)

    progress = _calc_progress(team_id)
    conn.close()

    return json.dumps(
        {
            "team": dict(team),
            "roles": roles_list,
            "tasks": tasks_list,
            "progress_percent": progress,
        },
        indent=2,
    )


# ── Tool 5: team_update_task ────────────────────────────────────────────────

VALID_TRANSITIONS = {
    "pending": ["in_progress"],
    "in_progress": ["completed", "blocked"],
    "completed": [],       # terminal
    "blocked": ["pending", "in_progress"],  # unblock → pending or resume
}


@mcp.tool()
def team_update_task(team_id: str, task_id: str, status: str, output: str = "") -> str:
    """
    Update the status and optional output of a task.

    Valid state machine: pending → in_progress → completed / blocked
    blocked can transition back to pending or in_progress.
    """
    if not _team_exists(team_id):
        return json.dumps({"error": f"Team '{team_id}' not found"})

    if status not in ("pending", "in_progress", "completed", "blocked"):
        return json.dumps({"error": f"Invalid status '{status}'. Must be one of: pending, in_progress, completed, blocked"})

    conn = _get_db()
    row = conn.execute(
        "SELECT status FROM tasks WHERE id = ? AND team_id = ?",
        (task_id, team_id),
    ).fetchone()
    if not row:
        conn.close()
        return json.dumps({"error": f"Task '{task_id}' not found in team '{team_id}'"})

    current = row["status"]
    allowed = VALID_TRANSITIONS.get(current, [])
    if status not in allowed:
        conn.close()
        return json.dumps(
            {
                "error": f"Cannot transition task from '{current}' to '{status}'. "
                f"Allowed transitions: {allowed if allowed else 'terminal state'}"
            }
        )

    if output:
        conn.execute(
            "UPDATE tasks SET status = ?, output = ? WHERE id = ?",
            (status, output, task_id),
        )
    else:
        conn.execute(
            "UPDATE tasks SET status = ? WHERE id = ?",
            (status, task_id),
        )
    conn.commit()
    conn.close()
    return json.dumps({"task_id": task_id, "status": status, "previous_status": current, "output": output or None})


# ── Tool 6: team_report ─────────────────────────────────────────────────────

@mcp.tool()
def team_report(team_id: str) -> str:
    """Generate a structured summary report for a team."""
    if not _team_exists(team_id):
        return json.dumps({"error": f"Team '{team_id}' not found"})

    conn = _get_db()
    team = conn.execute("SELECT * FROM teams WHERE id = ?", (team_id,)).fetchone()
    progress = _calc_progress(team_id)

    # Role summary
    roles_count = conn.execute(
        "SELECT COUNT(*) FROM roles WHERE team_id = ?", (team_id,)
    ).fetchone()[0]
    roles_filled = conn.execute(
        "SELECT COUNT(*) FROM roles WHERE team_id = ? AND status = 'filled'",
        (team_id,),
    ).fetchone()[0]

    # Task summary
    tasks_total = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE team_id = ?", (team_id,)
    ).fetchone()[0]
    tasks_pending = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE team_id = ? AND status = 'pending'",
        (team_id,),
    ).fetchone()[0]
    tasks_in_progress = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE team_id = ? AND status = 'in_progress'",
        (team_id,),
    ).fetchone()[0]
    tasks_completed = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE team_id = ? AND status = 'completed'",
        (team_id,),
    ).fetchone()[0]
    tasks_blocked = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE team_id = ? AND status = 'blocked'",
        (team_id,),
    ).fetchone()[0]

    conn.close()

    report = {
        "team": dict(team),
        "progress_percent": progress,
        "roles_summary": {
            "total": roles_count,
            "filled": roles_filled,
            "unfilled": roles_count - roles_filled,
        },
        "tasks_summary": {
            "total": tasks_total,
            "pending": tasks_pending,
            "in_progress": tasks_in_progress,
            "completed": tasks_completed,
            "blocked": tasks_blocked,
        },
    }
    return json.dumps(report, indent=2)


# ── Entry-point ─────────────────────────────────────────────────────────────

def main() -> None:
    """Run the AgentTeam MCP server via STDIO transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

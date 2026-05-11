# AgentTeam MCP Server

Multi-agent team formation and workflow orchestration — powered by the Model Context Protocol.

**$19/month** — [Subscribe on Stripe](https://buy.stripe.com/dRm6oJ4Hd2Jugek0wz1oI0m)

---

## Overview

AgentTeam lets you define teams with specific roles, assign agents to those roles, and orchestrate a task workflow with dependency tracking, status management, and progress reporting. All data is stored locally in `~/.agentteam/agentteam.db` (SQLite).

## Prerequisites

- Python 3.10+
- `pip install -r requirements.txt`

## Installation

```bash
cd agent-team-mcp
pip install -r requirements.txt
```

## Usage

### Run as a standalone MCP server

```bash
python server.py
```

This starts the server on **STDIO transport**, suitable for integration with MCP-compatible hosts (Claude Desktop, Cursor, VS Code, etc.).

### Configure with Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "agent-team": {
      "command": "python",
      "args": ["/absolute/path/to/agent-team-mcp/server.py"]
    }
  }
}
```

### Configure with VS Code / Cursor

Add to your MCP settings:

```json
{
  "mcpServers": {
    "agent-team": {
      "command": "python",
      "args": ["/absolute/path/to/agent-team-mcp/server.py"]
    }
  }
}
```

## Tools

### 1. `team_create(name, goal, roles[])`

Create a new team with a name, a mission goal, and a list of role titles.

**Parameters:**
| Name   | Type     | Description                        |
|--------|----------|------------------------------------|
| name   | string   | Team name                          |
| goal   | string   | Team mission or objective          |
| roles  | string[] | List of role titles to create      |

**Example:**
```python
team_create(
    name="Build Team",
    goal="Ship the MVP by June 1st",
    roles=["Project Lead", "Developer", "Designer", "QA Engineer"]
)
```

### 2. `team_assign_role(team_id, role, agent_id, requirements)`

Assign a specific agent to a role within the team.

**Parameters:**
| Name         | Type   | Description                              |
|--------------|--------|------------------------------------------|
| team_id      | string | Team ID from team_create                 |
| role         | string | Role name (must match a role on the team)|
| agent_id     | string | Identifier for the agent being assigned  |
| requirements | string | Optional qualification description       |

**Example:**
```python
team_assign_role(
    team_id="abc-123",
    role="Developer",
    agent_id="agent-1",
    requirements="Python, TypeScript, 5+ YoE"
)
```

### 3. `team_add_task(team_id, task_description, assigned_to, dependencies[], deadline)`

Add a task to the team's workflow.

**Parameters:**
| Name             | Type     | Description                               |
|------------------|----------|-------------------------------------------|
| team_id          | string   | Team ID                                   |
| task_description | string   | Description of the task                   |
| assigned_to      | string   | Role name or agent ID (optional)          |
| dependencies     | string[] | List of task IDs that must precede this   |
| deadline         | string   | ISO date string e.g. "2026-06-01" (optional) |

**Example:**
```python
team_add_task(
    team_id="abc-123",
    task_description="Design system architecture",
    assigned_to="Developer",
    dependencies=[],
    deadline="2026-05-15"
)
```

### 4. `team_get_status(team_id)`

Get full team status, including all roles, all tasks, and computed progress percentage.

**Parameters:**
| Name    | Type   | Description |
|---------|--------|-------------|
| team_id | string | Team ID     |

**Returns:** Team object, roles array, tasks array, `progress_percent`.

### 5. `team_update_task(team_id, task_id, status, output)`

Update a task's status and optionally attach output.

**State machine:** `pending → in_progress → completed / blocked` (blocked can return to pending or in_progress)

**Parameters:**
| Name    | Type   | Description                                      |
|---------|--------|--------------------------------------------------|
| team_id | string | Team ID                                          |
| task_id | string | Task ID to update                                |
| status  | string | One of: `pending`, `in_progress`, `completed`, `blocked` |
| output  | string | Optional task output / results                   |

**Example:**
```python
team_update_task(
    team_id="abc-123",
    task_id="task-456",
    status="completed",
    output="System architecture document delivered"
)
```

### 6. `team_report(team_id)`

Generate a concise summary report for the team, with role fill counts and task breakdown.

**Parameters:**
| Name    | Type   | Description |
|---------|--------|-------------|
| team_id | string | Team ID     |

**Returns:** Team info, `progress_percent`, `roles_summary` (total/filled/unfilled), `tasks_summary` (total/pending/in_progress/completed/blocked).

## Data Storage

All data is stored in a SQLite database at:

```
~/.agentteam/agentteam.db
```

You can inspect it directly with any SQLite browser:

```bash
sqlite3 ~/.agentteam/agentteam.db
.tables
```

## Pricing

**$19/month** — includes all 6 tools, unlimited teams, roles, and tasks.

[Subscribe here](https://buy.stripe.com/dRm6oJ4Hd2Jugek0wz1oI0m)

## License

MIT

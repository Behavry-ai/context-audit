# Behavry Context Audit

<!-- mcp-name: ai.behavry/context-audit -->

**Local CLI that measures the context-window cost of your MCP servers** — token counts per server and per tool, verb classification, and projected savings from schema compression.

Every MCP server you connect injects its full `tools/list` schema into the model's context at the start of every session. That cost is paid before the agent does any work, on every turn, whether or not a single tool is ever called. Most people have never measured it.

```
context-audit
    ↓ reads MCP client config (Claude Desktop, Cursor, VS Code, Windsurf, Claude Code)
    ↓ connects to each server, calls tools/list
    ↓ counts schema tokens, classifies tool verbs
Context load assessment (terminal / markdown / html / json)
```

## Why

- **You cannot budget what you cannot measure.** A 40-tool server can be 8k tokens of permanent overhead.
- **Schema cost is per-session, not per-call.** Ten servers with modest catalogs add up before the first prompt.
- **Tool count is a security surface too.** Destructive tools consume tokens *and* sit in the model's reachable action space even when your agents only read.

## Install

```bash
pip install behavry-context-audit
```

Exact token counts require `tiktoken` (cl100k_base, via `gpt-4` encoding). Without it the tool falls back to a 4-characters-per-token approximation and labels the report `token_method: estimate`.

```bash
pip install 'behavry-context-audit[exact]'
```

The command installs as both `context-audit` and `behavry-context-audit`. Use the latter if the shorter name collides with another tool on your `PATH`.

## Worked example

Two stock MCP servers, defined in an ordinary `mcpServers` config:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
    },
    "memory": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-memory"]
    }
  }
}
```

```bash
context-audit scan --config mcp.json
```

```
╭───────────────────────────────────────────────────────────────╮
│ BEHAVRY CONTEXT LOAD ASSESSMENT                               │
│ Generated: 2026-09-18T20:36:46.020925+00:00                   │
│ Token method: tiktoken                                        │
╰───────────────────────────────────────────────────────────────╯

SUMMARY
────────────────────────────────────────
  Total MCP servers scanned:           2
  Total tools discovered:             23
  Total schema tokens loaded:      5,041
  Estimated monthly token cost:   $      15  (at $3.0/1M input tokens)
  Risk score:                     MEDIUM

PER-SERVER BREAKDOWN
┏━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┓
┃Server               ┃ Tools ┃ Tokens ┃ % of Total ┃ Largest Tool         ┃
┡━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━┩
│filesystem           │    14 │  2,756 │      54.7% │ read_media_file (278)│
│memory               │     9 │  2,285 │      45.3% │ search_nodes (311)   │
└─────────────────────┴───────┴────────┴────────────┴──────────────────────┘

WASTE ANALYSIS
────────────────────────────────────────
  Destructive tools exposed:           3  (13.0%)
    └─ delete, destroy, purge, remove, execute operations
  Write tools exposed:                10  (43.5%)
    └─ create, update, modify operations loaded into every session
  High-token tools (>2,000):           0  (0.0%)
    └─ consuming 0 tokens (0.0% of total)

RISK EXPOSURE
────────────────────────────────────────
  Tools with destructive semantics visible to all agents:

  ⚠  memory:delete_entities  (161 tokens)
  ⚠  memory:delete_observations  (203 tokens)
  ⚠  memory:delete_relations  (218 tokens)

COMPRESSION SIMULATION
────────────────────────────────────────
┏━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━┓
┃Verbosity Level    ┃ Tokens ┃ Savings ┃ Monthly Cost┃
┡━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━┩
│Full (current)     │  5,041 │       — │          $15│
│Compact            │  3,024 │   40.0% │           $9│
│Minimal            │  1,260 │   75.0% │           $4│
│Policy Filtered*   │  1,730 │   65.7% │           $5│
└───────────────────┴────────┴─────────┴─────────────┘

  * Policy-filtered: read-only agent profile, destructive tools
    hidden, compact verbosity on remaining tools.
```

Two servers most people consider small are 5,041 tokens of every session.

## Commands

### `scan`

```bash
context-audit scan --discover                      # find configs on this machine
context-audit scan --config ~/.cursor/mcp.json     # a specific config file
context-audit scan --server https://host/mcp       # an HTTP server directly (repeatable)
context-audit scan --config mcp.json --verbose     # per-tool token breakdown
```

| Option | Default | Effect |
|--------|---------|--------|
| `--config PATH` | — | MCP config file to read |
| `--server URL` | — | Scan an HTTP MCP server directly; repeatable |
| `--discover` | off | Search known config paths on this system |
| `--format` | `terminal` | `terminal`, `markdown`, `html`, `json` |
| `--output PATH` | stdout | Write the report to a file |
| `--model-price` | `3.0` | USD per 1M input tokens, for the cost estimate |
| `--sessions` | `1000` | Assumed sessions/month, for the cost estimate |
| `--timeout` | `30` | Per-server connection timeout, seconds |
| `--verbose` | off | Per-tool token breakdown |

`--discover` looks for `claude_desktop_config.json` (both macOS and XDG paths), `~/.cursor/mcp.json`, `.vscode/mcp.json`, `~/.windsurf/mcp_config.json`, `~/.codeium/windsurf/mcp_config.json`, `.mcp.json`, and `~/.claude/mcp.json`.

### `ci`

Exits `1` when a threshold is exceeded, `2` on a config error. Prints the JSON report on stdout and the verdict on stderr.

```bash
context-audit ci --config .mcp.json --max-tokens 50000 --max-destructive 10
```

```
⛔ CI CHECK FAILED:
  • Total tokens 5,041 exceeds max 4,000
  • Destructive tools 3 exceeds max 2
```

### `compare`

Diffs two JSON reports — total tokens, tool count, destructive count.

```bash
context-audit scan --config mcp.json --format json --output before.json
# add or remove a server
context-audit scan --config mcp.json --format json --output after.json
context-audit compare before.json after.json
```

```
┏━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━━━━━━━┓
┃ Metric            ┃ Before ┃ After ┃           Delta ┃
┡━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━━━━━━━┩
│ Total tokens      │  5,041 │ 2,285 │ -2,756 (-54.7%) │
│ Total tools       │     23 │     9 │             -14 │
│ Destructive tools │      3 │     3 │               0 │
└───────────────────┴────────┴───────┴─────────────────┘
```

## JSON output

`--format json` emits `meta`, `summary`, `servers`, `waste_analysis`, `compression`, and `tools`.

```json
{
  "meta": {
    "tool": "behavry-context-audit",
    "version": "0.1.0",
    "timestamp": "2026-09-18T20:36:57.914259+00:00",
    "token_method": "tiktoken"
  },
  "summary": {
    "total_servers": 2,
    "total_tools": 23,
    "total_tokens": 5041,
    "monthly_cost_estimate": 15.12,
    "waste_percentage": 42.8,
    "risk_score": "medium",
    "model_price_per_million": 3.0,
    "sessions_per_month": 1000
  }
}
```

## How it works

**Transports.** stdio servers are spawned as subprocesses (`command` + `args` + `env`) and driven over JSON-RPC on stdin/stdout; HTTP servers receive `initialize` then `tools/list` as JSON-RPC POSTs. Servers are scanned concurrently. A server that fails is reported inline and does not abort the run.

**Token counting.** Each tool's full `tools/list` entry is serialized as compact JSON and counted. With `tiktoken` installed, counts use the `gpt-4` encoding; otherwise a character-based approximation.

**Classification.** Tools are bucketed into `read` / `write` / `delete` / `execute` / `unknown` by matching name segments against a fixed verb list (`get`, `list`, `create`, `delete`, `deploy`, …). `delete` and `execute` count as destructive; `write`, `delete`, and `execute` count as writes. This is name-based heuristics, not behavioral analysis — a tool called `run_report` classifies as `execute`.

**Risk score.** A threshold function over destructive-tool count and total tokens: `critical` above 10 destructive tools or 100k tokens, `high` above 5 or 75k, `medium` above 2 or 50k, else `low`.

**Compression simulation.** Projections, not measurements. `compact` and `minimal` apply fixed ratios (60% and 25% of current tokens) derived from typical description-to-schema proportions. `policy_filtered` sums the actual token counts of read-only tools and applies the compact ratio to that subset.

## What it does not do

- **Does not modify anything.** No config is written, no server is reconfigured, no tool is ever called — only `initialize` and `tools/list`.
- **Does not measure runtime token usage.** It measures the schema cost of tool definitions. Tool *results*, system prompts, and conversation history are out of scope.
- **Does not read session transcripts or logs.** It reads MCP server configs and live server catalogs.
- **Does not actually compress schemas.** The compression table is a projection. Applying it is the job of a gateway, not this tool.
- **Does not analyze tool behavior.** Classification is name-pattern matching. A destructively named read-only tool is miscounted, and vice versa.
- **Does not handle OAuth or authenticated HTTP servers.** `--server` sends unauthenticated JSON-RPC; servers requiring auth headers will error.
- **Does not count resources or prompts.** Only `tools/list`.
- **Does not read `.env` or inject secrets.** stdio servers inherit your environment plus whatever `env` the config declares.

## Development

```bash
poetry install --with dev --extras exact
poetry run pytest
poetry run ruff check .
```

## License

Apache-2.0. Copyright Behavry Inc. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

# travel-agent-ai

AI-powered travel planning via [Claude](https://www.anthropic.com/claude) tool calls.
Given a free-text trip description the agent:

- Fetches **real weather forecasts** from [wttr.in](https://wttr.in) (no API key needed)
- Looks up **mock flight options** with structured pricing data
- Generates a **day-by-day itinerary**, **packing list**, **budget breakdown**, and **local tips**
- Optionally saves everything as a formatted **Markdown file**

---

## Installation

```bash
# From source
pip install -e .

# Or install dependencies directly
pip install anthropic click rich httpx
```

## Requirements

- Python 3.11+
- An [Anthropic API key](https://console.anthropic.com/) in the `ANTHROPIC_API_KEY` environment variable

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

---

## Usage

### Command line

```bash
# Basic — streams the plan to the terminal
travel-agent plan "5 days in Tokyo in October, budget \$2000"

# Save to a Markdown file
travel-agent plan "5 days in Tokyo in October, budget \$2000" --output itinerary.md

# Longer trip, different model, no streaming
travel-agent plan "10 days touring Italy, budget \$4000" \
    --output italy.md \
    --model claude-opus-4-6 \
    --no-stream

# Help
travel-agent plan --help
```

### Python API

```python
from travel_agent import TravelAgent

agent = TravelAgent()  # uses ANTHROPIC_API_KEY from env

# Stream to stdout while collecting the full plan
plan = agent.plan(
    "5 days in Tokyo in October, budget $2000",
    output_path="itinerary.md",
    on_text=lambda delta: print(delta, end="", flush=True),
)
print(plan)  # complete Markdown string
```

---

## How it works

```
User prompt
    │
    ▼
Claude (claude-sonnet-4-6)
    │
    ├─ tool: get_weather(city, date)      ──▶ wttr.in JSON API
    ├─ tool: search_flights(origin, dest) ──▶ mock structured data
    └─ tool: write_file(path, content)    ──▶ local filesystem
    │
    ▼
Markdown travel plan
```

The agent runs an **agentic loop** — it calls tools as needed, observes the results, and continues until it has produced a complete plan. The loop terminates on `stop_reason == "end_turn"`.

---

## Tools

| Tool | Description |
|---|---|
| `get_weather(city, date)` | Fetches a 3-day forecast from wttr.in (free, no key). |
| `search_flights(origin, destination, date)` | Returns mock structured flight options with airline, price, and schedule. |
| `write_file(path, content)` | Saves a string to a local file (creates directories as needed). |

---

## Project layout

```
travel_agent/
    __init__.py   — package entry point
    agent.py      — TravelAgent class, tool definitions, agentic loop
    weather.py    — WeatherClient (wttr.in)
    cli.py        — Click CLI with Rich output
pyproject.toml
README.md
```

---

## Development

```bash
pip install -e '.[dev]'
ruff check .
mypy travel_agent/
pytest
```

## License

MIT
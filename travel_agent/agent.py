"""Core TravelAgent powered by Claude via the Anthropic SDK."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import anthropic

from .weather import WeatherClient

# ---------------------------------------------------------------------------
# Mock flight data
# ---------------------------------------------------------------------------

_MOCK_FLIGHTS: dict[str, list[dict[str, Any]]] = {
    "default": [
        {
            "airline": "Pacific Air",
            "flight_number": "PA 204",
            "departure": "08:00",
            "arrival": "14:30",
            "duration": "6h 30m",
            "price_usd": 780,
            "cabin": "Economy",
            "stops": 0,
        },
        {
            "airline": "Global Wings",
            "flight_number": "GW 512",
            "departure": "11:45",
            "arrival": "19:20",
            "duration": "7h 35m",
            "price_usd": 620,
            "cabin": "Economy",
            "stops": 1,
            "layover": "Seoul (ICN) — 1h",
        },
        {
            "airline": "Sky Connect",
            "flight_number": "SC 88",
            "departure": "22:00",
            "arrival": "06:15+1",
            "duration": "8h 15m",
            "price_usd": 540,
            "cabin": "Economy",
            "stops": 0,
        },
    ]
}


def _search_flights(
    origin: str, destination: str, date: str
) -> list[dict[str, Any]]:
    """Return mock structured flight data."""
    key = f"{origin.upper()}-{destination.upper()}"
    flights = _MOCK_FLIGHTS.get(key, _MOCK_FLIGHTS["default"])
    # Annotate each result with the query context.
    return [
        {"origin": origin, "destination": destination, "date": date, **f}
        for f in flights
    ]


def _write_file(path: str, content: str) -> str:
    """Write *content* to *path*, creating parent directories as needed."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"File written: {path} ({len(content)} characters)"


# ---------------------------------------------------------------------------
# Tool definitions (Claude JSON schema format)
# ---------------------------------------------------------------------------

TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_weather",
        "description": (
            "Fetch a weather forecast for a city and date from wttr.in. "
            "Use this to get temperature, conditions, and humidity so you can "
            "provide accurate packing and activity recommendations."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "City name, e.g. 'Tokyo' or 'Paris, France'.",
                },
                "date": {
                    "type": "string",
                    "description": "Date in YYYY-MM-DD format, or a relative description like 'October' for monthly averages.",
                },
            },
            "required": ["city", "date"],
        },
    },
    {
        "name": "search_flights",
        "description": (
            "Search for available flights between two cities on a given date. "
            "Returns mock structured data with airline, price, departure/arrival "
            "times, and stop information. Use to provide realistic budget estimates."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "origin": {
                    "type": "string",
                    "description": "Origin city or IATA airport code, e.g. 'New York' or 'JFK'.",
                },
                "destination": {
                    "type": "string",
                    "description": "Destination city or IATA airport code.",
                },
                "date": {
                    "type": "string",
                    "description": "Travel date in YYYY-MM-DD format.",
                },
            },
            "required": ["origin", "destination", "date"],
        },
    },
    {
        "name": "write_file",
        "description": (
            "Write text content to a file on disk. "
            "Use this to save the final itinerary, packing list, or budget breakdown "
            "as a Markdown file."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative or absolute file path, e.g. 'itinerary.md'.",
                },
                "content": {
                    "type": "string",
                    "description": "Full text content to write to the file.",
                },
            },
            "required": ["path", "content"],
        },
    },
]


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are an expert AI travel planner. When a user describes a trip, you:

1. Use `get_weather` to fetch real forecast data for the destination and travel period.
2. Use `search_flights` to look up flight options and realistic prices.
3. Produce a comprehensive travel plan that includes:
   - **Day-by-day itinerary** with morning, afternoon, and evening activities.
   - **Packing list** tailored to the weather, activities, and trip duration.
   - **Budget breakdown** in USD covering flights, accommodation, food, activities, and transport.
   - **Local tips** (currency, customs, transport cards, language basics, safety notes).
4. If an `--output` path is requested, use `write_file` to save the plan as a well-formatted Markdown document.

Always ground your recommendations in the actual weather data and flight prices you retrieve.
Be specific: name real neighborhoods, attractions, restaurants, and transport options.
Format the output in clean, readable Markdown with headers and bullet points.
"""


# ---------------------------------------------------------------------------
# TravelAgent class
# ---------------------------------------------------------------------------


class TravelAgent:
    """Plan a trip end-to-end using Claude and real/mock data sources."""

    def __init__(self, api_key: str | None = None, model: str = "claude-sonnet-4-6") -> None:
        self._client = anthropic.Anthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY")
        )
        self._model = model
        self._weather = WeatherClient()

    # ------------------------------------------------------------------
    # Tool dispatch
    # ------------------------------------------------------------------

    def _dispatch_tool(self, name: str, tool_input: dict[str, Any]) -> str:
        """Execute a tool by name and return a plain-text result."""
        if name == "get_weather":
            city: str = tool_input["city"]
            date: str = tool_input["date"]
            try:
                data = self._weather.fetch(city, date)
                return json.dumps(data, indent=2)
            except Exception as exc:  # noqa: BLE001
                return f"Weather fetch failed: {exc}"

        if name == "search_flights":
            flights = _search_flights(
                origin=tool_input["origin"],
                destination=tool_input["destination"],
                date=tool_input["date"],
            )
            return json.dumps(flights, indent=2)

        if name == "write_file":
            return _write_file(
                path=tool_input["path"],
                content=tool_input["content"],
            )

        return f"Unknown tool: {name}"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def plan(
        self,
        trip_description: str,
        output_path: str | None = None,
        on_text: Any = None,
    ) -> str:
        """Generate a full travel plan for *trip_description*.

        Parameters
        ----------
        trip_description:
            Free-form description of the desired trip, e.g.
            "5 days in Tokyo in October, budget $2000".
        output_path:
            Optional file path to save the plan as Markdown.
        on_text:
            Optional callable invoked with each streamed text delta.
            Useful for CLI progress display.

        Returns
        -------
        str
            The complete travel plan as a Markdown string.
        """
        user_content = trip_description
        if output_path:
            user_content += f"\n\nPlease save the final plan to `{output_path}`."

        messages: list[dict[str, Any]] = [
            {"role": "user", "content": user_content}
        ]

        final_text = ""

        # Agentic loop: keep going until Claude stops calling tools.
        while True:
            with self._client.messages.stream(
                model=self._model,
                max_tokens=8192,
                system=SYSTEM_PROMPT,
                tools=TOOLS,  # type: ignore[arg-type]
                messages=messages,  # type: ignore[arg-type]
            ) as stream:
                for text_delta in stream.text_stream:
                    if on_text:
                        on_text(text_delta)
                    final_text += text_delta

                response = stream.get_final_message()

            # Append the assistant turn to the history.
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                break

            if response.stop_reason != "tool_use":
                # Unexpected stop — surface the reason and stop.
                break

            # Execute every tool the model requested.
            tool_results: list[dict[str, Any]] = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                result_str = self._dispatch_tool(block.name, dict(block.input))
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_str,
                    }
                )

            messages.append({"role": "user", "content": tool_results})

        return final_text
"""WeatherClient — fetch forecast data from wttr.in (no API key required)."""

from __future__ import annotations

from typing import Any

import httpx

# wttr.in JSON v2 endpoint.
_BASE_URL = "https://wttr.in"


class WeatherClient:
    """Thin wrapper around the free wttr.in JSON API."""

    def __init__(self, timeout: float = 10.0) -> None:
        self._client = httpx.Client(
            timeout=timeout,
            headers={"User-Agent": "travel-agent-ai/1.0"},
            follow_redirects=True,
        )

    def fetch(self, city: str, date: str) -> dict[str, Any]:  # noqa: ARG002
        """Return a weather summary for *city*.

        The *date* parameter is accepted for interface compatibility; wttr.in
        returns a 3-day window that we summarise here. For trip-planning
        purposes we return averages and a qualitative description.

        Parameters
        ----------
        city:
            City name (and optional country), e.g. "Tokyo" or "Paris, France".
        date:
            Target date (YYYY-MM-DD) or relative description (e.g. "October").
            Not directly used in the wttr.in query — contextual only.

        Returns
        -------
        dict
            Structured weather data suitable for prompt injection.
        """
        url = f"{_BASE_URL}/{city}"
        params = {"format": "j1"}  # JSON v1 — most widely supported

        response = self._client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        return self._parse(city, date, data)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse(self, city: str, date: str, raw: dict[str, Any]) -> dict[str, Any]:
        """Extract a clean summary from the raw wttr.in JSON v1 response."""
        current = raw.get("current_condition", [{}])[0]
        weather_days: list[dict[str, Any]] = raw.get("weather", [])

        def _safe_int(val: Any, default: int = 0) -> int:
            try:
                return int(val)
            except (TypeError, ValueError):
                return default

        # Current conditions.
        temp_c = _safe_int(current.get("temp_C"))
        temp_f = _safe_int(current.get("temp_F"))
        feels_like_c = _safe_int(current.get("FeelsLikeC"))
        humidity = _safe_int(current.get("humidity"))
        weather_desc_list: list[dict[str, Any]] = current.get("weatherDesc", [])
        description = (
            weather_desc_list[0].get("value", "unknown")
            if weather_desc_list
            else "unknown"
        )
        wind_kmph = _safe_int(current.get("windspeedKmph"))

        # Forecast summary (up to 3 days).
        forecast: list[dict[str, Any]] = []
        for day in weather_days[:3]:
            hourly = day.get("hourly", [{}])
            desc_raw: list[dict[str, Any]] = hourly[0].get("weatherDesc", [])
            day_desc = desc_raw[0].get("value", "unknown") if desc_raw else "unknown"
            forecast.append(
                {
                    "date": day.get("date", ""),
                    "max_temp_c": _safe_int(day.get("maxtempC")),
                    "min_temp_c": _safe_int(day.get("mintempC")),
                    "max_temp_f": _safe_int(day.get("maxtempF")),
                    "min_temp_f": _safe_int(day.get("mintempF")),
                    "avg_humidity": _safe_int(day.get("hourly", [{}])[0].get("humidity")),
                    "description": day_desc,
                    "uv_index": _safe_int(day.get("uvIndex")),
                    "sunrise": day.get("astronomy", [{}])[0].get("sunrise", ""),
                    "sunset": day.get("astronomy", [{}])[0].get("sunset", ""),
                }
            )

        return {
            "city": city,
            "requested_date": date,
            "current": {
                "temp_c": temp_c,
                "temp_f": temp_f,
                "feels_like_c": feels_like_c,
                "humidity_pct": humidity,
                "description": description,
                "wind_kmph": wind_kmph,
            },
            "forecast_3day": forecast,
            "note": (
                "Forecast window is limited to 3 days from today; "
                "use monthly averages for longer-horizon planning."
            ),
        }
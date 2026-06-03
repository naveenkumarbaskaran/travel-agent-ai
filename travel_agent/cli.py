"""Command-line interface for travel-agent-ai."""

from __future__ import annotations

import sys

import click
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from .agent import TravelAgent

console = Console()


@click.command()
@click.argument("trip_description")
@click.option(
    "--output",
    "-o",
    default=None,
    metavar="FILE",
    help="Save the itinerary to FILE (Markdown). E.g. itinerary.md",
)
@click.option(
    "--model",
    default="claude-sonnet-4-6",
    show_default=True,
    help="Anthropic model to use.",
)
@click.option(
    "--stream/--no-stream",
    default=True,
    show_default=True,
    help="Stream model output to the terminal in real time.",
)
def main(
    trip_description: str,
    output: str | None,
    model: str,
    stream: bool,
) -> None:
    """Generate a travel plan for TRIP_DESCRIPTION.

    \b
    Examples:
      travel-agent plan "5 days in Tokyo in October, budget $2000"
      travel-agent plan "10 days in Italy, $4000" --output italy.md
    """
    console.print(
        Panel.fit(
            f"[bold cyan]Travel Agent AI[/bold cyan]\n[dim]{trip_description}[/dim]",
            border_style="cyan",
        )
    )

    agent = TravelAgent(model=model)

    if stream:
        # Stream text deltas directly to the terminal while gathering the full plan.
        accumulated: list[str] = []
        console.print()

        def _on_text(delta: str) -> None:
            accumulated.append(delta)
            console.print(delta, end="", highlight=False)

        try:
            plan = agent.plan(
                trip_description,
                output_path=output,
                on_text=_on_text,
            )
        except Exception as exc:  # noqa: BLE001
            console.print(f"\n[red]Error: {exc}[/red]")
            sys.exit(1)

        console.print("\n")
    else:
        # Non-streaming: show a spinner while planning, then render Markdown.
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
            console=console,
        ) as progress:
            progress.add_task("Planning your trip…", total=None)
            try:
                plan = agent.plan(trip_description, output_path=output)
            except Exception as exc:  # noqa: BLE001
                console.print(f"[red]Error: {exc}[/red]")
                sys.exit(1)

        console.print(Markdown(plan))

    if output:
        console.print(f"\n[green]Plan saved to[/green] [bold]{output}[/bold]")
    else:
        console.print(
            "[dim]Tip: add --output itinerary.md to save as a Markdown file.[/dim]"
        )
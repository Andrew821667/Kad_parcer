"""CLI commands for KAD parser."""

import typer
from rich.console import Console

app = typer.Typer(name="kad-parser", help="KAD Arbitr parser CLI")
console = Console()


@app.command()
def version() -> None:
    """Show version."""
    console.print("[bold green]KAD Parser v0.1.0[/bold green]")


@app.command()
def scrape(case_number: str) -> None:
    """Scrape case by number.

    Args:
        case_number: Case number to scrape
    """
    console.print(f"[yellow]Scraping case: {case_number}[/yellow]")
    # TODO: Implement actual scraping
    console.print("[green]✓ Done[/green]")


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", help="Host to bind"),
    port: int = typer.Option(8000, help="Port to bind"),
) -> None:
    """Start API server.

    Args:
        host: Host to bind
        port: Port to bind
    """
    import uvicorn

    console.print(f"[yellow]Starting server on {host}:{port}[/yellow]")
    uvicorn.run("src.api.app:app", host=host, port=port, reload=True)


if __name__ == "__main__":
    app()

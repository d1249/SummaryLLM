import typer
import sys
from digest_core.run import run_digest

app = typer.Typer(add_completion=False)

@app.command()
def run(
    from_date: str = typer.Option("today", "--from-date", help="Date to process (YYYY-MM-DD or 'today')"),
    sources: str = typer.Option("ews", "--sources", help="Comma-separated source types (e.g., 'ews')"),
    out: str = typer.Option("./out", "--out", help="Output directory path"),
    model: str = typer.Option("corp/gpt-4o-mini", "--model", help="LLM model identifier"),
    window: str = typer.Option("calendar_day", "--window", help="Time window: calendar_day or rolling_24h"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Run ingest+normalize only, skip LLM/assemble")
):
    """Run daily digest job."""
    try:
        if dry_run:
            typer.echo("Dry-run mode: ingest+normalize only")
            # TODO: Implement dry-run mode
            typer.echo("Dry-run not yet implemented")
            sys.exit(2)
        
        run_digest(from_date, sources.split(","), out, model)
        sys.exit(0)  # Success
    except KeyboardInterrupt:
        typer.echo("\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        sys.exit(1)  # Error

if __name__ == "__main__":
    app()

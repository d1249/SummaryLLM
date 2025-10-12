import typer
import sys
import subprocess
import os
from pathlib import Path
from digest_core.run import run_digest, run_digest_dry_run
from digest_core.observability.logs import setup_logging

app = typer.Typer(add_completion=False)

@app.command()
def run(
    from_date: str = typer.Option("today", "--from-date", help="Date to process (YYYY-MM-DD or 'today')"),
    sources: str = typer.Option("ews", "--sources", help="Comma-separated source types (e.g., 'ews')"),
    out: str = typer.Option("./out", "--out", help="Output directory path"),
    model: str = typer.Option("Qwen/Qwen3-30B-A3B-Instruct-2507", "--model", help="LLM model identifier"),
    window: str = typer.Option("calendar_day", "--window", help="Time window: calendar_day or rolling_24h"),
    state: str = typer.Option(None, "--state", help="State directory path (overrides config for SyncState)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Run ingest+normalize only, skip LLM/assemble"),
    collect_logs: bool = typer.Option(False, "--collect-logs", help="Automatically collect diagnostics after run"),
    log_file: str = typer.Option(None, "--log-file", help="Specify log file path"),
    log_level: str = typer.Option("INFO", "--log-level", help="Log level (DEBUG, INFO, WARNING, ERROR)")
):
    """Run daily digest job."""
    try:
        # Setup logging
        setup_logging(log_level=log_level, log_file=log_file)
        
        if dry_run:
            typer.echo("Dry-run mode: ingest+normalize only")
            run_digest_dry_run(from_date, sources.split(","), out, model, window, state)
            exit_code = 2  # Partial success code
        else:
            run_digest(from_date, sources.split(","), out, model, window, state)
            exit_code = 0  # Success
        
        # Collect diagnostics if requested
        if collect_logs:
            typer.echo("Collecting diagnostics...")
            try:
                script_dir = Path(__file__).parent.parent.parent / "scripts"
                collect_script = script_dir / "collect_diagnostics.sh"
                if collect_script.exists():
                    subprocess.run([str(collect_script)], check=True)
                    typer.echo("✓ Diagnostics collected successfully")
                else:
                    typer.echo("⚠ Diagnostics script not found", err=True)
            except Exception as e:
                typer.echo(f"⚠ Failed to collect diagnostics: {e}", err=True)
        
        sys.exit(exit_code)
    except KeyboardInterrupt:
        typer.echo("\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        sys.exit(1)  # Error

@app.command()
def diagnose():
    """Run comprehensive diagnostics and collect system information."""
    try:
        typer.echo("Running SummaryLLM diagnostics...")
        
        # Find scripts directory
        script_dir = Path(__file__).parent.parent.parent / "scripts"
        
        # Run environment diagnostics
        env_script = script_dir / "print_env.sh"
        if env_script.exists():
            typer.echo("Running environment diagnostics...")
            result = subprocess.run([str(env_script)], capture_output=True, text=True)
            typer.echo(result.stdout)
            if result.stderr:
                typer.echo(result.stderr, err=True)
        else:
            typer.echo("⚠ Environment diagnostics script not found", err=True)
        
        # Collect comprehensive diagnostics
        collect_script = script_dir / "collect_diagnostics.sh"
        if collect_script.exists():
            typer.echo("Collecting comprehensive diagnostics...")
            result = subprocess.run([str(collect_script)], capture_output=True, text=True)
            typer.echo(result.stdout)
            if result.stderr:
                typer.echo(result.stderr, err=True)
        else:
            typer.echo("⚠ Diagnostics collection script not found", err=True)
        
        typer.echo("✓ Diagnostics completed")
        
    except Exception as e:
        typer.echo(f"Error running diagnostics: {e}", err=True)
        sys.exit(1)

if __name__ == "__main__":
    app()

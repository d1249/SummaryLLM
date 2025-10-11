import typer
from digest_core.run import run_digest  # Cursor создаст позже
app = typer.Typer(add_completion=False)

@app.command()
def run(from_date: str = "today", sources: str = "ews", out: str = "./out",
        model: str = "corp/gpt-4o-mini"):
    """Run daily digest job."""
    run_digest(from_date, sources.split(","), out, model)

if __name__ == "__main__":
    app()

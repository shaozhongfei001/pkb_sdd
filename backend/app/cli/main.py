import typer

app = typer.Typer(help="Personal KB CLI. Implement commands according to specs.")

@app.command()
def scan(path: str):
    typer.echo(f"scan placeholder: {path}")

@app.command("build-parse-queue")
def build_parse_queue():
    typer.echo("build-parse-queue placeholder")

@app.command("parse")
def parse(limit: int = 10):
    typer.echo(f"parse placeholder limit={limit}")

if __name__ == "__main__":
    app()

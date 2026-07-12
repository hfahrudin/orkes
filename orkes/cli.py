import click
import uvicorn

@click.group()
def cli():
    pass

@cli.command()
@click.option("--host", default="127.0.0.1", help="Host address for the server.")
@click.option("--port", default=5001, type=int, help="Port for the server.")
@click.option("--reload", is_flag=True, help="Enable auto-reloading of the server on code changes (for development).")
def server(host, port, reload):
    """
    Run the Orkes server dashboard.
    """
    print(f"Serving Orkes Dashboard on http://{host}:{port}")
    uvicorn.run(
        "orkes.server.app:create_app",
        factory=True,
        host=host,
        port=port,
        reload=reload
    )

def main():
    cli()

if __name__ == "__main__":
    main()


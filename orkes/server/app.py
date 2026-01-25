from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

def create_app():
    app = FastAPI(
        title="Orkes Dashboard",
        description="Dashboard for Orkes LLM orchestration framework",
        version="0.1.0",
    )

    # Mount static files (CSS, JS, images, etc.)
    # The path is relative to the directory where this file is run from
    static_dir = Path(__file__).parent / "static"
    if not static_dir.exists():
        static_dir.mkdir()
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # Serve the index.html from the templates directory
    # The path is relative to the directory where this file is run from
    templates_dir = Path(__file__).parent / "templates"
    if not templates_dir.exists():
        templates_dir.mkdir()

    @app.get("/", response_class=HTMLResponse)
    async def read_root():
        index_html_path = templates_dir / "index.html"
        if not index_html_path.exists():
            return HTMLResponse(content="<h1>Index.html not found!</h1>", status_code=404)
        with open(index_html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())

    @app.get("/dashboard", response_class=HTMLResponse)
    async def read_dashboard():
        dashboard_html_path = templates_dir / "dashboard"
        if not dashboard_html_path.exists():
            return HTMLResponse(content="<h1>dashboard.html not found!</h1>", status_code=404)
        with open(dashboard_html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())

    @app.get("/settings", response_class=HTMLResponse)
    async def read_settings():
        settings_html_path = templates_dir / "settings.html"
        if not settings_html_path.exists():
            return HTMLResponse(content="<h1>settings.html not found!</h1>", status_code=404)
        with open(settings_html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())

    @app.get("/traces", response_class=HTMLResponse)
    async def read_traces():
        traces_html_path = templates_dir / "traces.html"
        if not traces_html_path.exists():
            return HTMLResponse(content="<h1>traces.html not found!</h1>", status_code=404)
        with open(traces_html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())

    return app

if __name__ == "__main__":
    import uvicorn
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8000)

from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi import Request
from fastapi.responses import JSONResponse
import os
from typing import List
import json

# Define the path for the settings file
SETTINGS_FILE = Path(__file__).parent / "settings.json"

def load_settings():
    if SETTINGS_FILE.exists():
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"root_folder": ""}

def save_settings(settings):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=4)

# Load settings on startup
app_settings = load_settings()

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

    @app.get("/api/settings/root-folder", response_class=JSONResponse)
    async def get_root_folder():
        return JSONResponse(content={"root_folder": app_settings["root_folder"]})

    @app.post("/api/settings/root-folder")
    async def save_root_folder(request: Request):
        data = await request.json()
        app_settings["root_folder"] = data.get("root_folder")
        save_settings(app_settings)
        return JSONResponse(content={"status": "success"})

    @app.get("/api/list-directories", response_class=JSONResponse)
    async def list_directories(path: str = "."):
        try:
            base_path = app_settings.get("root_folder") or "."
            base_path_abs = os.path.abspath(base_path)

            # If the provided path is ".", use the base path. Otherwise, resolve the provided path.
            if path == ".":
                resolved_path = base_path_abs
            else:
                # Security check: prevent ".." from going above the base_path
                # We resolve the path sent by the client relative to the base path
                # to ensure it's a sub-directory
                resolved_path = os.path.abspath(os.path.join(base_path_abs, path))

            # Security check to prevent directory traversal
            if not resolved_path.startswith(base_path_abs):
                return JSONResponse(content={"error": "Access denied."}, status_code=403)

            if not os.path.isdir(resolved_path):
                return JSONResponse(content={"error": f"Invalid path: {resolved_path}"}, status_code=400)

            directories = []
            for d in os.listdir(resolved_path):
                full_path = os.path.join(resolved_path, d)
                if os.path.isdir(full_path):
                    relative_path = os.path.relpath(full_path, base_path_abs)
                    directories.append(relative_path.replace('\\', '/')) # Normalize for web paths
            
            return JSONResponse(content={"directories": sorted(directories)})
        except Exception as e:
            return JSONResponse(content={"error": str(e)}, status_code=500)

    @app.get("/", response_class=HTMLResponse)
    async def read_root():
        index_html_path = templates_dir / "index.html"
        if not index_html_path.exists():
            return HTMLResponse(content="<h1>Index.html not found!</h1>", status_code=404)
        with open(index_html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())

    @app.get("/dashboard", response_class=HTMLResponse)
    async def read_dashboard():
        dashboard_html_path = templates_dir / "dashboard.html"
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

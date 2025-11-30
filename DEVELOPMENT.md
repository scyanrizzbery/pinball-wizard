# Development Guide

This project is set up for a modern, automated development workflow using Docker and Vite.

## Quick Start

1.  **Start the environment:**
    ```bash
    docker compose up
    ```

2.  **Access the Application:**
    *   **Frontend (Hot Reloading):** [http://localhost:5173](http://localhost:5173)
        *   Use this URL for development.
        *   Changes to Vue files will reflect immediately (HMR).
        *   API requests are automatically proxied to the backend.
    *   **Backend (Static Build):** [http://localhost:5000](http://localhost:5000)
        *   Use this URL to see the production build (requires `npm run build`).

## How it Works

*   **Frontend Service (`frontend`)**:
    *   Runs `npm run dev` inside the container.
    *   Exposes port `5173`.
    *   Mounts your local `frontend` directory, so file changes are detected instantly.
    *   Proxies `/api` and `/socket.io` requests to the `pbwizard` backend service.

*   **Backend Service (`pbwizard`)**:
    *   Runs the Flask application on port `5000`.
    *   Serves the *built* frontend assets from `frontend/dist` (only relevant if accessing port 5000).

## Common Tasks

### Installing New npm Packages
Since the `node_modules` are inside the container, use `docker compose exec`:

```bash
docker compose exec frontend npm install <package-name>
```

### Rebuilding the Frontend (for Production/Backend View)
If you want to update what is served at `http://localhost:5000`:

```bash
docker compose exec frontend npm run build
```
*Note: You do NOT need to do this for normal development at port 5173.*

# DMS Project Knowledge Base

## 1. Project Overview
- **Framework:** FastAPI
- **Database Modeler:** SQLModel
- **Database Setup:** SQLite (currently), planning to move to MySQL/MariaDB for better performance on cPanel.

## 2. Server & Deployment
- **Hosting:** cPanel (LiteSpeed / CloudLinux)
- **Deployment Method:** GitHub Actions (`.github/workflows/dms_automation.yml`) -> `ssh-deploy`
- **Application Server:** Passenger (WSGI) using `a2wsgi` to translate ASGI to WSGI.
- **Why no Uvicorn background daemon?** CloudLinux LVE limits monitor background processes and kill Uvicorn with `Signal 15 (SIGTERM)` after a while. Passenger is the only native, stable way to run apps on shared cPanel.

## 3. Critical Fixes Applied
- **Passenger Deadlocks (Signal 15 on Requests):** Fixed by implementing **Lazy Loading** in `passenger_wsgi.py`. The ASGI app is only imported and `uvloop` is strictly disabled upon the first request.
- **LiteSpeed Admin Panel Proxy Issue (127.0.0.1 redirect):** Fixed by building a `RealHostMiddleware` in `app/main.py`. It forces the `Host` header and URL scheme based on the `PRODUCTION_HOST` environment variable, ensuring redirects go to `demo.esabaq.com/admin/`.
- **Static & Media Files Slow Load:** Bypassed Passenger entirely for `/static/` and `/media/` directories by adding an `.htaccess` file inside those folders with `PassengerEnabled off`. This lets LiteSpeed serve them directly with browser caching, massively speeding up the site.

## 4. Operational Rules for Development
- Always use `git add` and `git commit` via AI.
- **NEVER** use `git push` via AI. The User is the only one who pushes to the GitHub repository.
- No `git pull` is needed on the server because GitHub actions automatically push the code via Rsync.

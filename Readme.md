# PRALAYX Threat Actor De-anonymization Platform

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![SQLite](https://img.shields.io/badge/Database-SQLite-003B57.svg)](https://www.sqlite.org/)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)]()

> Central web investigation workspace and correlation platform for de-anonymizing dark web onion services, tracking threat actors, and mapping OPSEC misconfigurations.

---

## 📋 Table of Contents
- [Overview](#overview)
- [Architecture & System Design](#architecture--system-design)
- [Repository Structure](#repository-structure)
- [Key Features](#key-features)
- [Environment Requirements](#environment-requirements)
- [Installation & Setup](#installation--setup)
- [Running the Platform](#running-the-platform)
  - [Windows Native (PowerShell)](#windows-native-powershell)
  - [WSL / Ubuntu Linux](#wsl--ubuntu-linux)
- [API Documentation](#api-documentation)
- [Web Interface Pages](#web-interface-pages)
- [Tor SOCKS Bridge](#tor-socks-bridge)
- [Database Seeding & Demo Case](#database-seeding--demo-case)

---

## 🔍 Overview

The **PRALAYX Platform** coordinates dark web crawling, OSINT threat intelligence, AI stylometry analysis, and relationship correlation into a web interface. It allows security analysts and law enforcement to monitor onion sites, correlate clear-web leaks (TLS certificates, exposed `/server-status` endpoints, default banners), detect candidate pseudonymous handle continuity, and visualize intelligence correlation graphs.

---

## 🏗️ Architecture & System Design

```
                     +-----------------------------------+
                     |      Web UI (HTML5/CSS3/JS)       |
                     |  (Dark/Light Theme, D3/Cytoscape) |
                     +-----------------+-----------------+
                                       | HTTP REST
                                       v
                     +-----------------+-----------------+
                     |     FastAPI Backend Server        |
                     |         (app/main.py)             |
                     +---+-------------+-------------+---+
                         |             |             |
        +----------------+             |             +----------------+
        v                              v                              v
+---------------+             +----------------+             +---------------+
| Dark Web      |             | Tor SOCKS      |             | Persona       |
| Crawler       |             | Proxy Bridge   |             | Microservice  |
| Runner        |             | (127.0.0.1:    |             | (127.0.0.1:   |
| (app/crawler_ |             |  9050)         |             |  8010)        |
|  runner.py)   |             +-------+--------+             +---------------+
+-------+-------+                     |
        |                             v
        v                     +---------------+
+---------------+             | WSL Tor       |
| SQLite DB     |             | Service       |
| (data/        |             | (/usr/sbin/   |
|  pralayx.db)  |             |  tor)         |
+---------------+             +---------------+
```

---

## 📁 Repository Structure

```
platform/
├── app/
│   ├── __init__.py           # App package initialization
│   ├── main.py               # FastAPI server entry point and REST API routes
│   ├── database.py           # SQLite database connector and helper methods
│   ├── crawler_runner.py     # Execution engine for DarkWeb-Deanonymization crawler
│   ├── engine_runner.py      # Job timer, progress counter, and process tracking
│   ├── persona_adapter.py    # Integration adapter for Persona microservice (:8010)
│   ├── tor_bridge.py         # Windows-to-WSL Tor SOCKS5 proxy daemon (:9050)
│   ├── reports.py            # PDF/HTML/JSON report generation logic
│   ├── seed_demo.py          # Pre-populates canonical INV-DEMO-2026 case data
│   ├── analysis.py           # Analytical routines and OPSEC scoring algorithms
│   ├── tracking.py           # Watchlist and alert monitoring helpers
│   └── config.py             # System parameters and file path configurations
├── shared/
│   ├── schema_sqlite.sql     # Canonical SQLite database schema (sih_* tables)
│   └── schema_postgress.sql  # Optional PostgreSQL schema migration script
├── web/
│   ├── index.html            # Dashboard workspace
│   ├── investigations.html   # Active cases registry & process progress timers
│   ├── correlation.html      # Relationship graph visualization page
│   ├── crawl.html            # Dark web crawling controller page
│   ├── investigation.html    # Detailed case workspace page
│   ├── monitoring.html       # Actor watchlist & real-time monitoring
│   ├── osint.html            # OSINT provider scan launcher
│   ├── analysis.html         # Stylometry & handle continuity analysis page
│   ├── reports.html          # Reports generator & export page
│   ├── settings.html         # Platform configuration settings
│   ├── terminal.html         # Interactive CLI console interface
│   ├── app.css               # Dynamic CSS styling with Light/Dark Theme overrides
│   └── app.js                # Front-end API client, theme switcher, polling logic
├── data/                     # Local database storage (pralayx.db)
├── logs/                     # Session and crawler runtime execution logs
├── .env                      # Environment variable configurations
├── .gitignore                # Git ignore rules for cache and database files
└── requirements.txt          # Python dependencies
```

---

## ✨ Key Features

- **Multi-Page Web Workspace**: 11 dedicated HTML interfaces equipped with a native sidebar and light/dark theme switcher (`☀️ Day Mode` / `🌙 Night Mode`).
- **Tor Onion Crawling & Bridging**: Built-in Windows-to-WSL proxy bridge (`tor_bridge.py`) routing SOCKS5 traffic through Tor.
- **Real-Time Job Execution Timers**: Live tracking of background jobs with process names, progress percentage bars, elapsed time counters, and estimated completion timers (`~X seconds remaining`).
- **Interactive Correlation Graph**: Visualizes relationship edges (`onion_service`, `domain`, `ip`, `email`, `crypto_wallet`, `pgp_key`, `handle`) using D3/Cytoscape.
- **AI Stylometry & Handle Migration**: Integrates with the Persona engine to detect candidate handle continuity (e.g. `DarkViper_2024` ➔ `AetherSec_2026`).
- **Demonstration Case `INV-DEMO-2026`**: Pre-seeded evidence-backed case featuring exposed Apache server-status, clearnet TLS certificate leaks, default SSH banners, and descriptor inconsistencies.

---

## 🔧 Environment Requirements

- **Operating System**: Windows 10/11 (WSL2 Ubuntu optional for Tor routing) or Linux/macOS.
- **Python Version**: Python 3.10+ (Python 3.12 tested).
- **Tor Service**: WSL Ubuntu Tor daemon or standalone Tor SOCKS proxy on `127.0.0.1:9050`.

---

## 🚀 Installation & Setup

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/raaj7z/platform.git
   cd platform
   ```

2. **Create a Virtual Environment**:
   - **Windows (PowerShell)**:
     ```powershell
     python -m venv venv
     .\venv\Scripts\Activate.ps1
     ```
   - **Linux / WSL**:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

---

## 🏃 Running the Platform

### Windows Native (PowerShell)

1. **Seed the Demonstration Investigation**:
   ```powershell
   python app/seed_demo.py
   ```

2. **Start the Tor Proxy Bridge (Optional for Dark Web Crawling)**:
   ```powershell
   python app/tor_bridge.py
   ```

3. **Launch the FastAPI Platform Server**:
   ```powershell
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```

4. **Access the Web Interface**:
   Open your browser to: `http://127.0.0.1:8000/web/index.html`

### WSL / Ubuntu Linux

```bash
# Start WSL Tor service
sudo service tor start

# Run FastAPI server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 📡 API Documentation

FastAPI automatically serves interactive OpenAPI documentation:
- **Swagger UI**: `http://127.0.0.1:8000/docs`
- **ReDoc**: `http://127.0.0.1:8000/redoc`

### Core Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/investigations` | List all registered investigations |
| `GET` | `/api/investigations/{id}` | Get detailed investigation payload (findings, relationships, actor) |
| `POST` | `/api/investigations` | Create a new investigation case |
| `GET` | `/api/jobs` | Retrieve all background execution jobs with timer statistics |
| `GET` | `/api/jobs/{job_id}` | Retrieve specific job status, elapsed time, and remaining time |
| `GET` | `/api/persona/synthetic-demo` | Fetch synthetic candidate pseudonymous continuity demo payload |
| `POST` | `/api/crawl` | Launch a dark web onion crawl job |

---

## 🧅 Tor SOCKS Bridge

When running on Windows where Tor operates inside WSL (Ubuntu), `app/tor_bridge.py` acts as a SOCKS5 proxy daemon listening on `127.0.0.1:9050` and forwarding TCP traffic into WSL Tor.

```powershell
# Start bridge standalone
python app/tor_bridge.py
```

---

## 📜 License

Proprietary — Internal Threat Actor De-anonymization Workspace.

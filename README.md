IST Fenix Auto Enroller
=======================

Desktop Python app for searching, planning, and enrolling in IST courses on FenixEdu. It combines an API client, a Tkinter GUI, and Selenium automation to build schedules and complete enrollment.

<img width="1911" height="1043" alt="image" src="https://github.com/user-attachments/assets/927d7267-1a6b-463e-9e31-279fe9e2126b" />

<img width="1915" height="1038" alt="image" src="https://github.com/user-attachments/assets/ac8772dd-6b26-456b-b310-6891c79034ff" />

Highlights
----------
- Search courses by name, code, or acronym
- Auto-detect shift types from schedule data
- Build unified schedules for multiple courses
- Time conflict detection
- Selenium-based automatic enrollment
- Persisted configuration (config.json)

Quick start
-----------
1. Ensure Python 3 is installed.
2. Install dependencies.
3. Run the app.

    python3 main.py

Releases
--------
Prebuilt binaries are published on GitHub Releases for tagged versions (v*).

- Windows: ist-fenix-auto-enroller.exe
- Linux: ist-fenix-auto-enroller

Release workflow: [.github/workflows/release-builds.yml](.github/workflows/release-builds.yml)

Nix
---
If you use Nix, you can run the app directly or enter a development shell with all dependencies.

Run without entering a shell:

    nix run

Development shell:

    nix develop
    python3 main.py

Windows executable
------------------
If you want to build locally, use PyInstaller to create a Windows .exe. GitHub Actions also builds Windows binaries for each release.

How it works
------------
1. Select a degree.
2. Search and choose courses.
3. Review available shifts and detect conflicts.
4. Enter your FenixEdu credentials.
5. Enroll using the automated flow.

Project structure
-----------------
- main.py        Entry point
- config.json    Persisted configuration
- src/api.py     Fenix API client
- src/bot.py     Selenium automation
- src/gui/       Tkinter UI components
- src/utils.py   Utilities for shift detection and scheduling

Configuration
-------------
Default settings are stored in config.json. Update it manually or let the app persist changes.

Notes
-----
- This project automates a web flow and may break if FenixEdu changes its UI.
- Use at your own discretion and verify results before final submission.

Credits
-------
- https://github.com/joanasesinando/gerador-horarios-ist

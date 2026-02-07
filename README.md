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

How to install
--------------
Choose one of the options below.

Option A - GitHub Releases (recommended)
1. Download the latest release for your OS.
2. Extract the archive.
3. Run the executable.

Latest release: https://github.com/ang3lo-azevedo/ist-fenix-auto-enroller/releases

Option B - Python source
1. Clone this repository.
2. Install dependencies.
3. Run the app.

    python3 -m pip install -r requirements.txt
    python3 main.py

Option C - Nix
1. Run directly or enter a dev shell.

    nix run
    # or
    nix develop
    python3 main.py

How to use
----------
1. Select your degree, semester, and period.
2. Search and select the courses you want.
3. Click [Build] Build Schedule and pick shifts.
4. Add shifts to the enrollment queue.
5. Login and start enrollment.

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

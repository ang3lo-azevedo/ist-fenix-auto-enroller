IST Fenix Auto Enroller
=======================

Desktop Python app for searching, planning and enrolling in IST courses on FenixEdu. It combines an API client, a Tkinter GUI and Selenium automation to build schedules and complete enrollment.

<img width="1911" height="1043" alt="image" src="https://github.com/user-attachments/assets/927d7267-1a6b-463e-9e31-279fe9e2126b" />

<img width="1915" height="1038" alt="image" src="https://github.com/user-attachments/assets/ac8772dd-6b26-456b-b310-6891c79034ff" />

Highlights
----------
- Search courses by name, code, or acronym
- Auto-detect shift types from schedule data
- Build unified schedules for multiple courses
- Time conflict detection
- Selenium-based automatic enrollment
- Dry-run mode to preview what would be enrolled without submitting
- Persisted configuration (config.json)

How to install
--------------
Choose one of the options below.

Option A - GitHub Releases (recommended)
1. Download the latest release for your OS.
2. Extract the archive.
3. On Linux, make the file executable, then run it.
	Example (replace with the actual file name):
	```sh
	chmod +x ist-fenix-auto-enroller
	./ist-fenix-auto-enroller
	```
4. On macOS/Windows, run the executable normally.

Latest release: https://github.com/ang3lo-azevedo/ist-fenix-auto-enroller/releases

Option B - Nix (recommended on NixOS)
The flake works on `x86_64-linux` and `aarch64-linux`.

Run it directly, without installing:
```sh
nix run github:ang3lo-azevedo/ist-fenix-auto-enroller
```

Install it into your user profile (adds the "IST Fénix Auto Enroller"
application menu entry with an icon):
```sh
nix profile install github:ang3lo-azevedo/ist-fenix-auto-enroller
```

Install it system-wide in a NixOS configuration via the overlay:
```nix
{
  inputs.ist-fenix-auto-enroller.url = "github:ang3lo-azevedo/ist-fenix-auto-enroller";

  # in your NixOS module:
  nixpkgs.overlays = [ inputs.ist-fenix-auto-enroller.overlays.default ];
  environment.systemPackages = [ pkgs.ist-fenix-auto-enroller ];
}
```

Or work on it from a checkout:
```sh
nix run          # run the app
nix develop      # dev shell with chromium + chromedriver, then: python3 main.py
```

Chromium and chromedriver are bundled by the flake, so no separate browser
setup is needed.

Option C - Python source
1. Clone this repository.
2. Install dependencies.
3. Run the app.
```sh
python3 -m pip install selenium requests beautifulsoup4
python3 main.py
```

How to use
----------
1. Select your current semester, year and degree.
2. Search and select the courses you want.
3. Click [Build] Build Schedule and pick the shifts from both periods.
4. Add shifts to the enrollment queue.
5. Login.
6. Optionally click [Test] Dry Run to preview which shifts the bot would
   enroll in, without submitting anything.
7. Start enrollment (or schedule it for a specific time with the timed button).

Project structure
-----------------
- main.py        Entry point
- config.json    Persisted configuration
- flake.nix      Nix package, dev shell, overlay and desktop entry
- assets/        Application icon
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
- https://github.com/joanasesinando/gerador-horarios-ist (used to check Fenix API usage)
- Thanks to the contributor who provided snapshots of the enrollment pages.

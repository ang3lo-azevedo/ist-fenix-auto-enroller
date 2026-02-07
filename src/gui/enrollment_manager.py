from tkinter import messagebox, simpledialog
import json
import os
from pathlib import Path
import threading
import time
from datetime import datetime, timedelta


class EnrollmentManagerMixin:
    """Mixin for enrollment management functionality"""

    def _notify_enrollment_wait(self, start_dt, window_text=None):
        def _show():
            when = start_dt.strftime("%d/%m/%Y %H:%M") if start_dt else "unknown"
            text = window_text or f"Enrollment period closed. Waiting until {when}."
            self.log(text, "WARNING")
            messagebox.showinfo(
                "Enrollment closed",
                f"{text}\n\nThe app will wait and continue automatically."
            )
        self.root.after(0, _show)

    def _is_writable_path(self, path: Path) -> bool:
        try:
            if path.exists():
                return os.access(path, os.W_OK)
            return os.access(path.parent, os.W_OK)
        except Exception:
            return False

    def _search_project_root_in_home(self, max_depth: int = 4):
        home = Path.home().resolve()
        markers = {"src/gui/main_window.py", "main.py"}

        def is_project_root(p: Path) -> bool:
            return any((p / marker).exists() for marker in markers)

        if is_project_root(home):
            return home

        for root, dirs, files in os.walk(home):
            root_path = Path(root)
            try:
                depth = len(root_path.relative_to(home).parts)
            except Exception:
                depth = max_depth + 1

            if depth > max_depth:
                dirs[:] = []
                continue

            dirs[:] = [
                d for d in dirs
                if not d.startswith(".") and d not in {".git", "node_modules", "__pycache__"}
            ]

            if is_project_root(root_path):
                return root_path

        return None

    def _find_project_root(self):
        """Find project root by walking up from CWD for known markers."""
        markers = {"src/gui/main_window.py", "main.py", "flake.nix", "README.md"}
        def is_nix_store(path: Path) -> bool:
            try:
                return str(path).startswith("/nix/store/")
            except Exception:
                return False

        env_root = os.environ.get("FENIX_PROJECT_ROOT")
        if env_root:
            root_path = Path(env_root).resolve()
            if root_path.exists() and not is_nix_store(root_path):
                return root_path

        env_pwd = os.environ.get("PWD")
        candidates = []
        if env_pwd:
            candidates.append(Path(env_pwd).resolve())
        candidates.append(Path.cwd().resolve())

        for base in candidates:
            if is_nix_store(base):
                continue
            for parent in [base, *base.parents]:
                if any((parent / marker).exists() for marker in markers):
                    return parent

        return candidates[0]

    def _get_config_path(self):
        """Return config path in the project root."""
        project_root = self._find_project_root()
        config_path = project_root / "config.json"
        if self._is_writable_path(config_path):
            return config_path

        fallback_root = self._search_project_root_in_home()
        if fallback_root:
            fallback_path = fallback_root / "config.json"
            if self._is_writable_path(fallback_path):
                return fallback_path

        return config_path
    
    def remove_enrollment(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Select an enrollment")
            return
        
        idx = self.tree.index(selected[0])
        self.tree.delete(selected[0])
        removed = self.enrollments.pop(idx)
        self.log(f"Removed: {removed['course']}")
        
    def save_config(self):
        try:
            config_path = self._get_config_path()
            selected_courses = [
                str(course_id) for course_id, entry in self.course_vars.items()
                if entry.get("var") and entry["var"].get()
            ]
            with open(config_path, "w") as f:
                json.dump({
                    "enrollments": self.enrollments,
                    "degree_id": self.get_selected_degree_id(),
                    "lang": self.lang_combo.get() or "pt-PT",
                    "period": self.period_combo.get() if hasattr(self, "period_combo") else "",
                    "selected_courses": selected_courses,
                    "selected_shifts": self.selected_shifts
                }, f, indent=2)
            self.log(f"Config saved: {config_path}", "SUCCESS")
        except Exception as e:
            self.log(f"Save failed: {e}", "ERROR")
            
    def load_config(self):
        try:
            config_path = self._get_config_path()
            with open(config_path, "r") as f:
                data = json.load(f)
                if data.get("degree_id"):
                    self._saved_degree_id = data.get("degree_id")
                    self.log(f"Loaded saved degree_id from config: {self._saved_degree_id}", "DEBUG")
                if data.get("lang"):
                    self.lang_combo.set(data.get("lang"))
                if data.get("period"):
                    self.default_period = data.get("period")
                self.saved_selected_course_ids = {str(cid) for cid in data.get("selected_courses", [])}
                self.selected_shifts = data.get("selected_shifts", {})
                self.enrollments = data.get("enrollments", [])
                for idx, e in enumerate(self.enrollments):
                    row_tag = "evenrow" if idx % 2 == 0 else "oddrow"
                    self.tree.insert(
                        "", "end",
                        values=(e["course"], e.get("shift_type", ""), e.get("shift_name", "")),
                        tags=(row_tag,)
                    )
                if self.enrollments:
                    self.log(f"Loaded {len(self.enrollments)} enrollments")
                self.log(f"Config loaded from: {config_path}", "DEBUG")
        except:
            pass
            
    def schedule_enrollment(self):
        if not self.enrollments:
            messagebox.showwarning("Warning", "Add enrollments")
            return
        
        time_str = simpledialog.askstring("Schedule", "Time (HH:MM:SS):\nExample: 14:30:00")
        if not time_str:
            return
        
        try:
            target_time = datetime.strptime(time_str, "%H:%M:%S").time()
        except:
            messagebox.showerror("Error", "Invalid format (use HH:MM:SS)")
            return
        
        self.enroll_btn.configure(state="disabled")
        self.timed_btn.configure(state="disabled")
        self.log(f"Waiting for {time_str} to start enrollment...")
        
        def schedule_thread():
            while True:
                now = datetime.now().time()
                if now >= target_time:
                    self.root.after(0, self.start_enrollment)
                    break
                time.sleep(0.1)
        
        threading.Thread(target=schedule_thread, daemon=True).start()
        
    def start_enrollment(self):
        if not self.enrollments:
            messagebox.showwarning("Warning", "Add enrollments")
            return
        
        if not self.bot:
            messagebox.showerror("Error", "Must login first before enrolling")
            return

        if not self.bot.logged_in:
            if getattr(self, "is_logged_in", False):
                self.bot.logged_in = True
            elif not self.bot.check_logged_in():
                messagebox.showerror("Error", "Must login first before enrolling")
                return

        self._enroll_cancelled = False

        if self.bot:
            self.bot.start_capture()
        
        self.enroll_btn.configure(state="disabled")
        self.timed_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.log("Starting enrollment...", "WARNING")
        
        def enroll_thread():
            try:
                # Browser already logged in from login() call
                self.root.after(0, lambda: self.log("Navigating to enrollments..."))
                self.bot.on_enrollment_wait = self._notify_enrollment_wait
                if not self.bot.navigate_to_enrollments():
                    self.root.after(0, lambda: self.log("Failed to navigate to enrollments", "ERROR"))
                    return
                
                enrolled = 0
                remaining = [e for e in self.enrollments]
                total = len(remaining)

                overall_deadline = datetime.now() + timedelta(minutes=20)
                per_shift_window = 60
                per_shift_interval = 10

                while remaining and datetime.now() < overall_deadline:
                    if self._enroll_cancelled:
                        self.root.after(0, lambda: self.log("Enrollment cancelled", "WARNING"))
                        return

                    for enrollment in list(remaining):
                        if self._enroll_cancelled:
                            self.root.after(0, lambda: self.log("Enrollment cancelled", "WARNING"))
                            return

                        course = enrollment["course"]
                        shift_type = enrollment["shift_type"]
                        shift_name = enrollment.get("shift_name", "")

                        if not shift_name:
                            self.root.after(0, lambda c=course, t=shift_type: 
                                          self.log(f"✗ Missing shift selection for {c} ({t}). Skipping.", "ERROR"))
                            remaining.remove(enrollment)
                            continue

                        self.root.after(0, lambda c=course, t=shift_type:
                                      self.log(f"Searching for {c} ({t})..."))

                        if self.bot.find_and_enroll_shift(
                            course,
                            shift_type,
                            shift_name,
                            retry_window_seconds=per_shift_window,
                            retry_interval_seconds=per_shift_interval
                        ):
                            enrolled += 1
                            remaining.remove(enrollment)
                            self.root.after(0, lambda c=course:
                                          self.log(f"✓ Enrolled in {c}", "SUCCESS"))

                    if remaining and datetime.now() < overall_deadline:
                        self.root.after(0, lambda: self.log(
                            f"Round robin retry: {len(remaining)} shifts still pending...", "WARNING"
                        ))

                msg = f"Done! {enrolled}/{total} enrolled"
                if remaining:
                    msg = f"Done! {enrolled}/{total} enrolled (pending: {len(remaining)})"
                self.root.after(0, lambda: self.log(msg, "SUCCESS"))
                self.root.after(0, lambda: messagebox.showinfo("Complete", msg))
                
            except Exception as e:
                self.root.after(0, lambda: self.log(f"Error: {e}", "ERROR"))
            finally:
                self.root.after(0, lambda: self.enroll_btn.configure(state="normal"))
                self.root.after(0, lambda: self.timed_btn.configure(state="normal"))
                self.root.after(0, lambda: self.cancel_btn.configure(state="disabled"))
        
        threading.Thread(target=enroll_thread, daemon=True).start()

    def cancel_enrollment(self):
        self._enroll_cancelled = True
        self.log("Cancellation requested", "WARNING")
    
    def login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        
        if not username or not password:
            messagebox.showerror("Error", "Enter credentials")
            return
        
        self.login_btn.configure(state="disabled", text="Logging in...")
        self.log(f"Logging in as {username}...")
        
        def login_thread():
            try:
                # Initialize bot and perform login first
                from ..bot import FenixBot
                self.bot = FenixBot(username, password, headless=False)
                
                self.root.after(0, lambda: self.log("Initializing browser..."))
                self.bot.init_driver()
                
                self.root.after(0, lambda: self.log("Attempting login to Fenix..."))
                if not self.bot.login():
                    self.root.after(0, lambda: self.log("Login failed - Invalid credentials. Please check username and password.", "ERROR"))
                    self.root.after(0, lambda: self.login_btn.configure(state="normal", text="Login"))
                    self.root.after(0, lambda: self.status_label.configure(text="● Login Failed ✗", foreground="#ef5350"))
                    self.root.after(0, lambda: self.username_entry.delete(0, "end"))
                    self.root.after(0, lambda: self.password_entry.delete(0, "end"))
                    self.root.after(0, lambda: messagebox.showerror("Login Failed", 
                        "Invalid credentials. Please check your username and password and try again."))
                    try:
                        self.bot.close()
                    except Exception:
                        pass
                    self.bot = None
                    return
                
                self.root.after(0, lambda: self.log("Login successful!", "SUCCESS"))
                
                # Now setup API with language and academic term
                lang = self.lang_combo.get() or "pt-PT"
                term = self.academic_term
                self.api.set_lang(lang)
                self.api.set_academic_term(term)
                
                # Load degrees and courses
                self.root.after(0, lambda: self.log("Loading degrees..."))
                self.load_degrees_async()
                
                self.root.after(0, self.on_login_success)
            except Exception as e:
                self.root.after(0, self.on_login_failed, str(e))
        
        threading.Thread(target=login_thread, daemon=True).start()
    
    def on_login_success(self):
        self.is_logged_in = True
        self.status_label.configure(text="● Logged in ✓", foreground="green")
        self.login_btn.configure(state="disabled", text="Logged In")
        self.enroll_btn.configure(state="normal")
        self.timed_btn.configure(state="normal")
        self.log("Login successful!", "SUCCESS")
        
    def on_login_failed(self, error: str):
        self.login_btn.configure(state="normal", text="Login")
        self.log(f"Login failed: {error}", "ERROR")
        messagebox.showerror("Login Failed", error)

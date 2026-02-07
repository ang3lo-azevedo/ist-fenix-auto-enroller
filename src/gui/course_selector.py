import tkinter as tk
from tkinter import messagebox
import threading
from datetime import datetime


class CourseSelectorMixin:
    """Mixin for course selection functionality"""

    def _get_courses_cache_key(self, degree_id: str, lang: str):
        return (str(degree_id or ""), lang)

    def _reset_course_cache(self):
        self.all_degree_courses = []
        self._courses_cache_key = None

    def _get_selected_semester(self):
        return self.semester_combo.get()

    def _get_selected_period(self):
        return self.period_combo.get()

    def _normalize_campus_name(self, name: str) -> str:
        value = (name or "").strip()
        lower = value.lower()
        if "alameda" in lower:
            return "Alameda"
        if "tagus" in lower:
            return "Taguspark"
        return value

    def _degree_implied_campus(self) -> str:
        acronym = (getattr(self, "selected_degree_acronym", "") or "").upper()
        if acronym.endswith("-A"):
            return "Alameda"
        if acronym.endswith("-T"):
            return "Taguspark"
        return ""

    def _course_matches_degree_campus(self, course, implied_campus: str) -> bool:
        if not implied_campus:
            return True
        campuses = set()
        for name in course.get("campus") or []:
            normalized = self._normalize_campus_name(name)
            if normalized:
                campuses.add(normalized)
        return implied_campus in campuses

    def _set_courses_loading(self, is_loading: bool):
        if not hasattr(self, "courses_loading_frame"):
            return
        if is_loading:
            try:
                self.clear_course_widgets()
                self.courses_canvas.yview_moveto(0)
                self.courses_loading_frame.pack(fill="x", pady=(16, 10), padx=6)
                self.courses_loading_bar.start(10)
            except Exception:
                pass
        else:
            try:
                self.courses_loading_bar.stop()
                self.courses_loading_frame.pack_forget()
            except Exception:
                pass

    def on_semester_selected(self):
        semester = self._get_selected_semester()
        degree_id = self.get_selected_degree_id()
        lang = self.lang_combo.get() or "pt-PT"
        cache_key = self._get_courses_cache_key(degree_id, lang)
        
        self.log(f"on_semester_selected: semester={semester}, degree_id={degree_id}, lang={lang}", "DEBUG")

        self.update_period_options()
        
        if not degree_id:
            self.log("No degree selected, skipping course load", "WARNING")
            messagebox.showwarning("Warning", "Select a degree first")
            return
        
        if lang != self.last_lang:
            self._reset_course_cache()
            self.last_lang = lang
        
        self.api.set_lang(lang)
        self.api.set_academic_term(self.academic_term)
        self.log(f"Loading courses for {semester} ({self.academic_term})...")
        
        if self.all_degree_courses and getattr(self, "_courses_cache_key", None) == cache_key:
            self.log(f"Using cached courses, filtering for {semester}", "DEBUG")
            self.filter_courses_by_semester()
            return

        self._set_courses_loading(True)
        
        def load_thread():
            try:
                # API now returns enriched courses with semester_hint and period_hint
                self.log(f"Fetching courses for degree {degree_id}", "DEBUG")
                courses = self.api.get_degree_courses(
                    degree_id,
                    self.academic_term,
                    enrich=True,
                    degree_acronym=getattr(self, "selected_degree_acronym", "")
                )
                self.log(f"Fetched {len(courses)} courses", "DEBUG")
                def apply_courses():
                    self._courses_cache_key = cache_key
                    self.display_available_courses(courses)
                    self._set_courses_loading(False)

                self.root.after(0, apply_courses)
            except Exception as e:
                self.root.after(0, lambda: (self.log(f"Error loading courses: {e}", "ERROR"), self._set_courses_loading(False)))
        
        threading.Thread(target=load_thread, daemon=True).start()

    def apply_current_semester_default(self):
        if self.default_semester:
            self.semester_combo.set(self.default_semester)
            self.update_period_options()
            return
        month = datetime.now().month
        if 2 <= month <= 7:
            self.semester_combo.set("2nd Semester")
        else:
            self.semester_combo.set("1st Semester")
        self.update_period_options()

    def update_period_options(self):
        semester = self._get_selected_semester()
        if semester == "2nd Semester":
            options = ["P3", "P4"]
            default = "P3"
        else:
            options = ["P1", "P2"]
            default = "P1"

        self.period_combo.configure(values=options)
        saved = getattr(self, "default_period", "")
        if saved in options:
            self.period_combo.set(saved)
        else:
            self.period_combo.set(default)
    
    def display_available_courses(self, courses):
        current_selected = {cid for cid, entry in self.course_vars.items() if entry["var"].get()}
        self._current_selected_cache = set(current_selected)
        self.clear_course_widgets()
        self.available_courses = []
        self.all_degree_courses = []
        self.course_vars = {}
        semester = self.semester_combo.get()
        period_filter = self._get_selected_period()
        saved_selected = getattr(self, "saved_selected_course_ids", set())
        implied_campus = self._degree_implied_campus()
        
        if not courses:
            self.log("No courses found for this degree and semester", "WARNING")
            return
        
        self.log(f"Found {len(courses)} courses", "SUCCESS")
        
        # Render selected courses first (current selection and saved)
        def is_selected_course(course):
            course_id = str(course.get("id") or course.get("code") or course.get("name"))
            if course_id in current_selected:
                return True
            return course_id in saved_selected

        sorted_courses = sorted(
            courses,
            key=lambda c: not is_selected_course(c)
        )

        for course in sorted_courses:
            # Courses are already enriched by the API with semester_hint and period_hint
            course_id = course.get("id")
            if not course_id:
                continue
            
            name = course.get("name", "Unknown")
            code = course.get("code", "")
            
            # Store in all_degree_courses for search filtering
            self.all_degree_courses.append(course)
            
            # Now check if the course matches the selected semester
            if not self.course_matches_semester(course, semester):
                continue

            if not self.course_matches_period(course, period_filter, allow_missing=False):
                continue

            if not self._course_matches_degree_campus(course, implied_campus):
                continue

            
            self.available_courses.append(course)
            self.render_course_checkbox(course)
        
        self.search_var.set("")
        self.update_selected_count()
        # Fallback: if period filter yields nothing, allow missing period info
        if period_filter and len(self.available_courses) == 0:
            self.clear_course_widgets()
            self.available_courses = []
            for course in sorted_courses:
                if not self.course_matches_semester(course, semester):
                    continue
                if not self.course_matches_period(course, period_filter, allow_missing=True):
                    continue
                if not self._course_matches_degree_campus(course, implied_campus):
                    continue
                self.available_courses.append(course)
                self.render_course_checkbox(course)
            self.update_selected_count()
            self.log(f"Displayed {len(self.available_courses)} courses for {semester} (fallback)")
            return

        self.log(f"Displayed {len(self.available_courses)} courses for {semester}")
    
    def filter_courses_by_semester(self):
        """Re-filter cached courses when semester selection changes"""
        current_selected = {cid for cid, entry in self.course_vars.items() if entry["var"].get()}
        self._current_selected_cache = set(current_selected)
        self.clear_course_widgets()
        self.available_courses = []
        self.course_vars = {}
        semester = self._get_selected_semester()
        period_filter = self._get_selected_period()
        saved_selected = getattr(self, "saved_selected_course_ids", set())
        implied_campus = self._degree_implied_campus()

        filtered = [c for c in self.all_degree_courses if self.course_matches_semester(c, semester) and self.course_matches_period(c, period_filter, allow_missing=False) and self._course_matches_degree_campus(c, implied_campus)]
        filtered = sorted(
            filtered,
            key=lambda c: not (str(c.get("id") or c.get("code") or c.get("name")) in current_selected or str(c.get("id") or c.get("code") or c.get("name")) in saved_selected)
        )
        
        for course in filtered:
            self.available_courses.append(course)
            self.render_course_checkbox(course)
        
        self.search_var.set("")
        self.update_selected_count()
        if period_filter and len(self.available_courses) == 0:
            self.clear_course_widgets()
            self.available_courses = []
            filtered = [c for c in self.all_degree_courses if self.course_matches_semester(c, semester) and self.course_matches_period(c, period_filter, allow_missing=True) and self._course_matches_degree_campus(c, implied_campus)]
            filtered = sorted(
                filtered,
                key=lambda c: not (str(c.get("id") or c.get("code") or c.get("name")) in current_selected or str(c.get("id") or c.get("code") or c.get("name")) in saved_selected)
            )
            for course in filtered:
                self.available_courses.append(course)
                self.render_course_checkbox(course)
            self.update_selected_count()
            self.log(f"Filtered to {len(self.available_courses)} courses for {semester} (fallback)")
            return

        self.log(f"Filtered to {len(self.available_courses)} courses for {semester}")
    
    def filter_courses_display(self):
        query = self.search_var.get().strip().lower()
        current_selected = {cid for cid, entry in self.course_vars.items() if entry["var"].get()}
        self._current_selected_cache = set(current_selected)
        self.clear_course_widgets()
        self.available_courses = []
        semester = self._get_selected_semester()
        period_filter = self._get_selected_period()
        saved_selected = getattr(self, "saved_selected_course_ids", set())
        implied_campus = self._degree_implied_campus()

        filtered = []
        
        for course in self.all_degree_courses:
            name = course.get("name", "").lower()
            code = (course.get("acronym") or course.get("code") or "").lower()
            
            if not self.course_matches_semester(course, semester):
                continue
            
            # Apply period filter
            if not self.course_matches_period(course, period_filter, allow_missing=False):
                continue

            if not self._course_matches_degree_campus(course, implied_campus):
                continue


            if not query or query in name or query in code:
                filtered.append(course)

        filtered = sorted(
            filtered,
            key=lambda c: not (str(c.get("id") or c.get("code") or c.get("name")) in current_selected or str(c.get("id") or c.get("code") or c.get("name")) in saved_selected)
        )

        for course in filtered:
            self.available_courses.append(course)
            self.render_course_checkbox(course)
        self.update_selected_count()

        if period_filter and len(self.available_courses) == 0:
            self.clear_course_widgets()
            self.available_courses = []
            filtered = []
            for course in self.all_degree_courses:
                name = course.get("name", "").lower()
                code = (course.get("acronym") or course.get("code") or "").lower()
                if not self.course_matches_semester(course, semester):
                    continue
                if not self.course_matches_period(course, period_filter, allow_missing=True):
                    continue
                if not self._course_matches_degree_campus(course, implied_campus):
                    continue
                if not query or query in name or query in code:
                    filtered.append(course)

            filtered = sorted(
                filtered,
                key=lambda c: not (str(c.get("id") or c.get("code") or c.get("name")) in current_selected or str(c.get("id") or c.get("code") or c.get("name")) in saved_selected)
            )

            for course in filtered:
                self.available_courses.append(course)
                self.render_course_checkbox(course)
            self.update_selected_count()
    
    def clear_search(self):
        self.search_var.set("")
        self.filter_courses_display()

    def update_selected_count(self):
        count = sum(1 for entry in self.course_vars.values() if entry["var"].get())
        self.selected_count_var.set(f"Selected: {count}")


    def select_all_courses(self):
        for entry in self.course_vars.values():
            entry["var"].set(True)
        self.update_selected_count()

    def clear_course_selection(self):
        for entry in self.course_vars.values():
            entry["var"].set(False)
        self.update_selected_count()

    def course_matches_semester(self, course, semester):
        semester_hint = course.get("semester_hint")
        if semester_hint in {"1", "2"}:
            return (semester == "1st Semester" and semester_hint == "1") or (semester == "2nd Semester" and semester_hint == "2")
        period = course.get("period_hint")
        if period in {"P1", "P2", "P3", "P4"}:
            if semester == "1st Semester":
                return period in {"P1", "P2"}
            if semester == "2nd Semester":
                return period in {"P3", "P4"}
        return True

    def course_matches_period(self, course, period_filter, allow_missing: bool = False):
        course_period = course.get("period_hint", "") or ""
        if not period_filter:
            return True

        periods = []
        raw = str(course_period).upper()
        for p in ["P1", "P2", "P3", "P4"]:
            if p in raw:
                periods.append(p)

        # Try courseLoads if period_hint is missing
        if not periods:
            for load in course.get("courseLoads") or []:
                if not isinstance(load, dict):
                    continue
                for key in ["executionPeriod", "period", "semester", "academicTerm", "term"]:
                    val = load.get(key)
                    if not isinstance(val, str):
                        continue
                    v = val.upper()
                    for p in ["P1", "P2", "P3", "P4"]:
                        if p in v and p not in periods:
                            periods.append(p)
                    if "SEM" in v or v.startswith("S"):
                        semester = self.semester_combo.get()
                        if semester == "1st Semester":
                            periods.extend(["P1", "P2"])
                        elif semester == "2nd Semester":
                            periods.extend(["P3", "P4"])

        # If still no period info
        if not periods:
            return True if allow_missing else False

        return period_filter in set(periods)

    def on_build_schedule_clicked(self):
        selected_courses = []
        semester = self._get_selected_semester()
        period_filter = self._get_selected_period()
        for entry in self.course_vars.values():
            if entry["var"].get():
                course = entry["course"]
                if not self.course_matches_semester(course, semester):
                    continue
                if not self.course_matches_period(course, period_filter, allow_missing=False):
                    continue
                selected_courses.append(course)
        
        if not selected_courses:
            messagebox.showwarning("Warning", "Select at least one course")
            return
        
        self.open_multi_schedule_picker_with_courses(selected_courses)

    def clear_course_widgets(self):
        for widget in self.course_widgets:
            try:
                widget.destroy()
            except:
                pass
        self.course_widgets.clear()
        self.available_courses = []
    
    def render_course_checkbox(self, course):
        course_id = str(course.get("id") or course.get("code") or course.get("name"))
        if course_id not in self.course_vars:
            preselected = course_id in getattr(self, "saved_selected_course_ids", set()) or course_id in getattr(self, "_current_selected_cache", set())
            var = tk.BooleanVar(value=preselected)
            self.course_vars[course_id] = {"var": var, "course": course}
        var = self.course_vars[course_id]["var"]
        
        shifts_count = len(course.get("shifts", []))
        code = course.get("acronym") or course.get("code") or ""
        label = f"{code} - {course.get('name', 'Unknown')}  |  Shifts: {shifts_count}"

        # Card-like row container for modern dark UI
        row = tk.Frame(self.courses_container, bg=self.BG_TERTIARY, highlightthickness=0, bd=0, relief="flat")
        row.pack(fill="x", padx=6, pady=4)

        cb = tk.Checkbutton(
            row,
            text=label,
            variable=var,
            bg=self.BG_TERTIARY,
            fg=self.FG_PRIMARY,
            activebackground=self.BG_SECONDARY,
            activeforeground=self.FG_PRIMARY,
            selectcolor=self.BG_SECONDARY,
            anchor="w",
            justify="left",
            relief="flat",
            bd=0,
            highlightthickness=0,
            padx=8,
            pady=6,
            font=("Segoe UI", 10),
            command=self.update_selected_count
        )
        cb.pack(fill="x")
        self.course_widgets.append(row)

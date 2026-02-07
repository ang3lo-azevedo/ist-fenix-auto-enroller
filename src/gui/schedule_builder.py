import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from ..utils import normalize_shift_type, get_shift_campus


class ScheduleBuilderMixin:
    """Mixin for schedule building functionality"""
    
    def open_multi_schedule_picker_with_courses(self, selected_courses):
        """Open visual schedule builder with time grid"""
        if not selected_courses:
            return

        win = tk.Toplevel(self.root)
        win.title("Build Schedule - Visual Time Grid")
        win.geometry("1200x800")

        # Dark theme colors (fallbacks if not defined on main UI)
        bg_primary = getattr(self, "BG_PRIMARY", "#0a0a0a")
        bg_secondary = getattr(self, "BG_SECONDARY", "#1a1a1a")
        bg_tertiary = getattr(self, "BG_TERTIARY", "#2a2a2a")
        fg_primary = getattr(self, "FG_PRIMARY", "#ffffff")

        course_selections = {}
        shift_buttons_map = {}
        shift_time_map = {}
        cell_shift_info = {}

        main_container = tk.Frame(win, bg=bg_primary)
        main_container.pack(fill="both", expand=True, padx=10, pady=10)

        controls_frame = tk.Frame(main_container, bg=bg_primary)
        controls_frame.pack(fill="x", pady=(0, 10))

        campus_filter = self.campus_combo.get()
        tk.Label(controls_frame, text=f"Campus: {campus_filter}", bg=bg_primary, fg=fg_primary,
                 font=("Segoe UI", 10, "bold")).pack(side="left", padx=10)

        grid_frame = tk.Frame(main_container, bg=bg_primary, relief="flat", borderwidth=0)
        grid_frame.pack(fill="both", expand=True)

        canvas = tk.Canvas(grid_frame, bg=bg_primary, highlightthickness=0)
        scrollbar = ttk.Scrollbar(grid_frame, orient="vertical", command=canvas.yview)
        scrollable_content = tk.Frame(canvas, bg=bg_primary)
        canvas_window = canvas.create_window((0, 0), window=scrollable_content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        def on_content_configure(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def on_canvas_configure(event):
            canvas.itemconfig(canvas_window, width=event.width)

        scrollable_content.bind("<Configure>", on_content_configure)
        canvas.bind('<Configure>', on_canvas_configure)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        canvas.focus_set()

        def on_mousewheel(event):
            try:
                direction = 0
                if hasattr(event, 'delta') and event.delta != 0:
                    # Windows/macOS: delta > 0 is up
                    direction = -1 if event.delta > 0 else 1
                elif hasattr(event, 'num'):
                    # Linux: Button-4 up, Button-5 down
                    direction = -1 if event.num == 4 else (1 if event.num == 5 else 0)

                if direction != 0:
                    canvas.yview_scroll(direction * 3, "units")
            except Exception:
                pass

        def _focus_canvas(_event):
            canvas.focus_set()

        # Bind only to schedule widgets to avoid breaking other scroll areas
        for widget in (canvas, scrollable_content, grid_frame, win):
            widget.bind("<MouseWheel>", on_mousewheel)
            widget.bind("<Button-4>", on_mousewheel)
            widget.bind("<Button-5>", on_mousewheel)
            widget.bind("<Enter>", _focus_canvas)

        time_slots = [
            "08:00", "08:30", "09:00", "09:30", "10:00", "10:30", "11:00", "11:30",
            "12:00", "12:30", "13:00", "13:30", "14:00", "14:30", "15:00", "15:30",
            "16:00", "16:30", "17:00", "17:30", "18:00", "18:30", "19:00", "19:30", "20:00"
        ]
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

        def parse_time(time_str):
            if not time_str:
                return None
            if ' ' in time_str:
                time_str = time_str.split(' ')[1]
            parts = time_str.split(':')
            if len(parts) >= 2:
                return f"{parts[0]}:{parts[1]}"
            return None

        def get_day_name(lesson_data):
            if not lesson_data:
                return None
            weekday = lesson_data.get("weekDay")
            if weekday is not None:
                day_map = {1: "Monday", 2: "Tuesday", 3: "Wednesday", 4: "Thursday", 5: "Friday", 6: "Saturday", 7: "Sunday"}
                return day_map.get(weekday)
            start = lesson_data.get("start", "")
            if start and ' ' not in start:
                return None
            try:
                if 'T' in start:
                    dt = datetime.fromisoformat(start.replace('Z', '+00:00').split('+')[0].split('T')[0])
                elif ' ' in start:
                    date_part = start.split(' ')[0]
                    dt = datetime.strptime(date_part, "%Y-%m-%d")
                else:
                    return None
                day_map = {0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday", 4: "Friday", 5: "Saturday", 6: "Sunday"}
                return day_map.get(dt.weekday())
            except Exception:
                return None

        def get_contrast_text_color(hex_color: str) -> str:
            try:
                hex_color = hex_color.lstrip("#")
                r = int(hex_color[0:2], 16)
                g = int(hex_color[2:4], 16)
                b = int(hex_color[4:6], 16)
                luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
                return "#000000" if luminance > 0.6 else "#ffffff"
            except Exception:
                return "#ffffff"

        def times_overlap(start1, end1, start2, end2):
            try:
                s1 = datetime.strptime(start1, "%H:%M").time()
                e1 = datetime.strptime(end1, "%H:%M").time()
                s2 = datetime.strptime(start2, "%H:%M").time()
                e2 = datetime.strptime(end2, "%H:%M").time()
                return not (e1 <= s2 or e2 <= s1)
            except Exception:
                return False

        def time_to_minutes(t):
            try:
                h, m = t.split(":")
                return int(h) * 60 + int(m)
            except Exception:
                return 0

        slot_minutes = [time_to_minutes(t) for t in time_slots]

        def slot_index(time_str, round_up=False):
            """Map a time to the nearest slot index. round_up=True picks the next slot."""
            minutes = time_to_minutes(time_str)
            if minutes in slot_minutes:
                return slot_minutes.index(minutes)

            if round_up:
                for idx, sm in enumerate(slot_minutes):
                    if minutes <= sm:
                        return idx
                return len(slot_minutes) - 1

            for idx in range(len(slot_minutes) - 1, -1, -1):
                if minutes >= slot_minutes[idx]:
                    return idx
            return 0

        colors = ["#ffcdd2", "#bbdefb", "#e1bee7", "#c8e6c9", "#ffe0b2", "#f8bbd0", "#b2dfdb"]
        course_color_map = {}

        for idx, course in enumerate(selected_courses):
            course_id = course.get("id")
            course_acronym = course.get("acronym") or course.get("code") or ""
            shifts = course.get("shifts", [])
            course_color = colors[idx % len(colors)]
            course_color_map[course_id] = course_color
            course_selections[course_id] = {}
            saved_for_course = self.selected_shifts.get(course_id, {}) if hasattr(self, "selected_shifts") else {}

            for shift in shifts:
                shift_name = shift.get("name", "")
                types = shift.get("types") or []
                lessons = shift.get("lessons", [])

                campuses = get_shift_campus(shift)
                if campus_filter != "All" and campus_filter not in campuses:
                    continue

                shift_type = None
                for t in types:
                    norm = normalize_shift_type(t)
                    if norm:
                        shift_type = norm
                        break

                if not shift_type or not lessons:
                    continue

                lesson_slots = []
                seen_slots = set()
                for lesson in lessons:
                    start_time = parse_time(lesson.get("start", ""))
                    end_time = parse_time(lesson.get("end", ""))
                    day_name = get_day_name(lesson)
                    if not start_time or not end_time or not day_name:
                        continue
                    if start_time not in time_slots or day_name not in days:
                        continue
                    slot_key = (start_time, end_time, day_name)
                    if slot_key in seen_slots:
                        continue
                    seen_slots.add(slot_key)
                    lesson_slots.append((start_time, end_time, day_name))

                for start_time, end_time, day_name in lesson_slots:
                    start_idx = slot_index(start_time, round_up=False)
                    end_idx = slot_index(end_time, round_up=True)
                    if end_idx <= start_idx:
                        end_idx = min(start_idx + 1, len(time_slots) - 1)
                    rowspan = max(1, end_idx - start_idx)
                    row_idx = start_idx + 1

                    cell_key = (start_time, day_name)
                    if cell_key not in cell_shift_info:
                        cell_shift_info[cell_key] = {"row": row_idx, "rowspan": rowspan, "shifts": []}
                    else:
                        if rowspan > cell_shift_info[cell_key]["rowspan"]:
                            cell_shift_info[cell_key]["rowspan"] = rowspan

                    cell_shift_info[cell_key]["shifts"].append({
                        "course_id": course_id,
                        "shift_type": shift_type,
                        "shift_name": shift_name,
                        "course_acronym": course_acronym,
                        "course_color": course_color,
                        "start_time": start_time,
                        "end_time": end_time,
                        "day_name": day_name
                    })

                    if shift_type not in course_selections[course_id]:
                        course_selections[course_id][shift_type] = tk.StringVar(value="")
                        # Preselect saved shift for this course/type
                        saved_name = saved_for_course.get(shift_type, "")
                        if saved_name:
                            course_selections[course_id][shift_type].set(saved_name)

        day_track_counts = {day: 1 for day in days}
        day_base_col = {}
        shifts_by_day = {day: [] for day in days}

        for cell_key, cell_data in cell_shift_info.items():
            day_name = cell_key[1]
            for shift_info in cell_data["shifts"]:
                start_time = shift_info.get("start_time")
                end_time = shift_info.get("end_time")
                if not start_time or not end_time:
                    continue
                start_idx = slot_index(start_time, round_up=False)
                end_idx = slot_index(end_time, round_up=True)
                if end_idx <= start_idx:
                    end_idx = min(start_idx + 1, len(time_slots) - 1)
                rowspan = max(1, end_idx - start_idx)
                row_idx = start_idx + 1

                shifts_by_day[day_name].append({
                    "shift_info": shift_info,
                    "start_time": start_time,
                    "end_time": end_time,
                    "row_idx": row_idx,
                    "rowspan": rowspan
                })

        for day in days:
            entries = sorted(shifts_by_day[day], key=lambda e: time_to_minutes(e["start_time"]))
            track_ends = []
            for entry in entries:
                start_min = time_to_minutes(entry["start_time"])
                end_min = time_to_minutes(entry["end_time"])
                assigned = False
                for idx, end_time_min in enumerate(track_ends):
                    if start_min >= end_time_min:
                        track_ends[idx] = end_min
                        entry["track_idx"] = idx
                        assigned = True
                        break
                if not assigned:
                    entry["track_idx"] = len(track_ends)
                    track_ends.append(end_min)

                entry["shift_info"]["track_idx"] = entry["track_idx"]
                entry["shift_info"]["row_idx"] = entry["row_idx"]
                entry["shift_info"]["rowspan"] = entry["rowspan"]

            day_track_counts[day] = max(1, len(track_ends))

        # Ensure all days use the same width
        max_tracks = max(day_track_counts.values()) if day_track_counts else 1
        for day in days:
            day_track_counts[day] = max_tracks

        # Keep per-day track counts (only add extra columns when overlaps exist)

        grid_container = tk.Frame(scrollable_content, bg=bg_tertiary)
        grid_container.pack(fill="both", expand=True, padx=5, pady=5)
        grid_container.columnconfigure(0, weight=0, minsize=60)

        tk.Label(grid_container, text="Time", bg=bg_primary, fg=fg_primary, font=("Segoe UI", 9, "bold"),
                 relief="flat", borderwidth=0).grid(row=0, column=0, sticky="nsew", padx=1, pady=1)

        current_col = 1
        for day in days:
            day_base_col[day] = current_col
            for track_idx in range(day_track_counts[day]):
                grid_container.columnconfigure(current_col + track_idx, weight=1, minsize=100)
            tk.Label(grid_container, text=day, bg=bg_primary, fg=fg_primary, font=("Segoe UI", 9, "bold"),
                     relief="flat", borderwidth=0).grid(row=0, column=current_col, columnspan=day_track_counts[day],
                     sticky="nsew", padx=1, pady=1)
            current_col += day_track_counts[day]

        for row_idx, time in enumerate(time_slots):
            tk.Label(grid_container, text=time, bg=bg_secondary, fg=fg_primary, font=("Segoe UI", 8),
                     relief="flat", borderwidth=0).grid(row=row_idx+1, column=0, sticky="nsew", padx=1, pady=1)
            grid_container.rowconfigure(row_idx+1, weight=0, minsize=40)
            for day in days:
                base_col = day_base_col[day]
                for track_idx in range(day_track_counts[day]):
                    cell_bg = tk.Frame(grid_container, bg=bg_primary, highlightthickness=0, bd=0, relief="flat")
                    cell_bg.grid(row=row_idx+1, column=base_col + track_idx, sticky="nsew", padx=1, pady=1)

        def update_button_states():
            selected_slots = []
            for (cid, stype, sname, start_time, day_name), (s_start, s_end) in shift_time_map.items():
                var = course_selections.get(cid, {}).get(stype)
                if var and var.get() == sname:
                    selected_slots.append((cid, day_name, s_start, s_end))

            for (cid, stype, sname, start_time, day_name), btn in shift_buttons_map.items():
                course_color = course_color_map.get(cid, "#e0e0e0")
                current_selection = course_selections.get(cid, {}).get(stype, None)
                is_selected = current_selection and current_selection.get() == sname

                start_end = shift_time_map.get((cid, stype, sname, start_time, day_name))
                if start_end:
                    this_start, this_end = start_end
                else:
                    this_start, this_end = start_time, start_time

                is_compatible = True
                for selected_cid, selected_day, sel_start, sel_end in selected_slots:
                    if cid == selected_cid:
                        continue
                    if day_name != selected_day:
                        continue
                    if times_overlap(this_start, this_end, sel_start, sel_end):
                        is_compatible = False
                        break

                if is_selected:
                    btn_bg = "#2e7d32"
                    btn_fg = "white"
                    btn_state = "normal"
                elif not is_compatible:
                    btn_bg = "#3a3a3a"
                    btn_fg = "#888888"
                    btn_state = "disabled"
                else:
                    btn_bg = course_color
                    btn_fg = get_contrast_text_color(btn_bg)
                    btn_state = "normal"

                btn.configure(bg=btn_bg, fg=btn_fg, state=btn_state)

        def clear_all_selections():
            for cid in course_selections:
                for stype in course_selections[cid]:
                    course_selections[cid][stype].set("")
            update_button_states()

        ttk.Button(controls_frame, text="Clear All", command=clear_all_selections).pack(side="right", padx=10)

        for cell_key, cell_data in cell_shift_info.items():
            shifts_list = cell_data["shifts"]
            if not shifts_list:
                continue
            for shift_info in shifts_list:
                cid = shift_info["course_id"]
                stype = shift_info["shift_type"]
                sname = shift_info["shift_name"]
                cacro = shift_info["course_acronym"]
                color = shift_info["course_color"]

                row_idx = shift_info.get("row_idx", cell_data["row"])
                rowspan = shift_info.get("rowspan", cell_data["rowspan"])
                day_name = shift_info.get("day_name")
                track_idx = shift_info.get("track_idx", 0)
                base_col = day_base_col.get(day_name, 1)
                col_idx = base_col + track_idx

                def make_shift_click(cid, stype, sname, cacro):
                    def on_click():
                        current = course_selections[cid].get(stype, None)
                        if current and current.get() == sname:
                            current.set("")
                        else:
                            if stype not in course_selections[cid]:
                                course_selections[cid][stype] = tk.StringVar(value="")
                            course_selections[cid][stype].set(sname)
                        update_button_states()
                        self.log(f"Selected: {cacro} {stype} {sname}", "INFO")
                    return on_click

                btn_fg = get_contrast_text_color(color)
                shift_btn = tk.Button(
                    grid_container,
                    text=f"{cacro}\n{stype}\n{sname}",
                    font=("Segoe UI", 8),
                    bg=color,
                    fg=btn_fg,
                    relief="flat",
                    borderwidth=0,
                    highlightthickness=0,
                    cursor="hand2",
                    wraplength=70,
                    state="normal",
                    command=make_shift_click(cid, stype, sname, cacro)
                )
                shift_btn.grid(row=row_idx, column=col_idx, rowspan=rowspan, sticky="nsew", padx=2, pady=2)

                actual_start = shift_info.get("start_time")
                actual_end = shift_info.get("end_time")
                actual_day = shift_info.get("day_name")
                key = (cid, stype, sname, actual_start, actual_day)
                shift_buttons_map[key] = shift_btn
                shift_time_map[key] = (actual_start, actual_end)

        update_button_states()
        on_content_configure()
        win.after(150, on_content_configure)
        def apply_schedule():
            # Collect all selections from course_selections dictionary
            chosen = {}
            selection_count = 0
            
            for course_id, types_dict in course_selections.items():
                if not isinstance(types_dict, dict):
                    continue
                    
                chosen[course_id] = {}
                for stype, var in types_dict.items():
                    if not isinstance(var, tk.StringVar):
                        continue
                        
                    val = var.get().strip()
                    if val:
                        chosen[course_id][stype] = val
                        selection_count += 1
            
            if selection_count > 0:
                self.selected_shifts.update(chosen)
                self.log(f"Schedule selections saved: {selection_count} selections", "SUCCESS")
                win.destroy()
                self.add_selected_courses_to_queue(selected_courses)
                self.show_enrollment_queue()
            else:
                messagebox.showinfo("Info", "Select at least one shift by clicking on it in the grid")

        # Bottom button frame
        btn_frame = tk.Frame(win, bg=bg_primary, highlightthickness=0, bd=0, relief="flat")
        btn_frame.pack(fill="x", padx=10, pady=10)
        
        ttk.Button(btn_frame, text="✓ Confirm Schedule", command=apply_schedule).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=win.destroy).pack(side="left", padx=5)
    
    def create_tooltip(self, widget, text):
        """Create hover tooltip for widgets"""
        def show_tooltip(event):
            tooltip = tk.Toplevel()
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
            label = tk.Label(tooltip, text=text, background=bg_secondary, fg=fg_primary, relief="flat", 
                           borderwidth=0, font=("Segoe UI", 8), justify="left")
            label.pack()
            widget.tooltip = tooltip
        
        def hide_tooltip(event):
            if hasattr(widget, 'tooltip'):
                widget.tooltip.destroy()
                delattr(widget, 'tooltip')
        
        widget.bind('<Enter>', show_tooltip)
        widget.bind('<Leave>', hide_tooltip)
    
    def add_selected_courses_to_queue(self, courses):
        added_count = 0
        
        for course in courses:
            course_id = course.get("id") or course.get("code") or course.get("name")
            course_name = course.get("name", "Unknown")
            
            selections = self.selected_shifts.get(course_id, {})
            if not selections:
                self.log(f"No selections for {course_name}", "DEBUG")
                continue
            
            self.log(f"Adding {course_name} with {len(selections)} shifts", "INFO")
            
            for stype, shift_name in selections.items():
                enrollment = {
                    "course": course_name,
                    "shift_type": stype,
                    "shift_name": shift_name,
                    "course_id": course_id
                }
                
                existing = False
                for e in self.enrollments:
                    if e["course"] == course_name and e["shift_type"] == stype:
                        e["shift_name"] = shift_name
                        existing = True
                        break
                
                if not existing:
                    self.enrollments.append(enrollment)
                    added_count += 1
        
        self.tree.delete(*self.tree.get_children())
        for idx, e in enumerate(self.enrollments):
            row_tag = "evenrow" if idx % 2 == 0 else "oddrow"
            self.tree.insert(
                "", "end",
                values=(e["course"], e.get("shift_type", ""), e.get("shift_name", "")),
                tags=(row_tag,)
            )
        
        self.log(f"Added {added_count} new enrollments to queue (total: {len(self.enrollments)})")
    
    def show_enrollment_queue(self):
        """Bring enrollment queue to focus"""
        self.root.lift()
        self.root.focus_set()

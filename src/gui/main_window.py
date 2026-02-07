import tkinter as tk
from tkinter import ttk
import threading
from datetime import datetime

from ..api import FenixAPI
from ..config import DEFAULT_ACADEMIC_TERM

# Import all mixins
from .degree_selector import DegreeSelectorMixin
from .course_selector import CourseSelectorMixin
from .schedule_builder import ScheduleBuilderMixin
from .enrollment_manager import EnrollmentManagerMixin


class GUI(DegreeSelectorMixin, CourseSelectorMixin, ScheduleBuilderMixin, EnrollmentManagerMixin):
    """Main Fenix GUI Application"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("IST Fenix Auto Enroller")
        self.root.geometry("1000x1000")
        self.root.resizable(True, True)
        
        self.bot = None
        self.api = FenixAPI()
        self.enrollments = []
        self.is_logged_in = False
        self.available_courses = []
        self.selected_shifts = {}
        self.degrees = []
        self.degree_map = {}
        self.degree_labels = []
        self.selected_degree_id = ""
        self.selected_degree_acronym = ""
        self.all_degree_courses = []
        self.academic_term = DEFAULT_ACADEMIC_TERM
        self.course_by_item_id = {}
        self.last_lang = ""
        self.course_vars = {}
        self.course_widgets = []
        self.selected_count_var = tk.StringVar(value="Selected: 0")
        self.default_semester = ""
        self.default_period = ""
        self.saved_selected_course_ids = set()
        
        self.setup_ui()
        self.load_config()
        self.apply_current_semester_default()
        self.load_degrees_async()
        
    def setup_ui(self):
        # Dark mode colors - truly black theme
        self.BG_PRIMARY = "#0b0f14"
        self.BG_SECONDARY = "#111827"
        self.BG_TERTIARY = "#1f2937"
        self.FG_PRIMARY = "#f9fafb"
        self.FG_SECONDARY = "#cbd5f5"
        self.ACCENT = "#3b82f6"
        self.ACCENT_LIGHT = "#60a5fa"
        self.ERROR_COLOR = "#ef4444"
        
        # Configure ttk style for dark mode
        style = ttk.Style()
        style.theme_use('clam')
        
        # Global configurations
        style.configure("TFrame", background=self.BG_PRIMARY)
        style.configure("TLabel", background=self.BG_PRIMARY, foreground=self.FG_PRIMARY)
        style.configure("TLabelframe", background=self.BG_PRIMARY, foreground=self.FG_PRIMARY, borderwidth=0, relief="flat")
        style.configure("TLabelframe.Label", background=self.BG_PRIMARY, foreground=self.ACCENT_LIGHT)
        
        # Button styling
        style.configure("TButton", background=self.ACCENT, foreground="white", padding=(12, 6), relief="flat", 
                   borderwidth=0, focuscolor="none", font=("Segoe UI", 10))
        style.configure("Big.TButton", background=self.ACCENT, foreground="white", padding=(16, 9), relief="flat",
                   borderwidth=0, focuscolor="none", font=("Segoe UI", 11, "bold"))
        style.layout("TButton", [
            ("Button.padding", {"sticky": "nswe", "children": [
                ("Button.label", {"sticky": "nswe"})
            ]})
        ])
        style.layout("Big.TButton", [
            ("Button.padding", {"sticky": "nswe", "children": [
                ("Button.label", {"sticky": "nswe"})
            ]})
        ])
        style.map("TButton", 
                 background=[("active", self.ACCENT_LIGHT), ("pressed", "#0d47a1"), ("disabled", self.BG_TERTIARY)],
                 foreground=[("disabled", self.FG_SECONDARY)])
        
        # Entry styling
        style.configure("TEntry", fieldbackground=self.BG_SECONDARY, foreground=self.FG_PRIMARY, 
                   padding=6, borderwidth=0, relief="flat", font=("Segoe UI", 10),
                   highlightbackground=self.BG_SECONDARY, highlightcolor=self.BG_SECONDARY)
        style.map("TEntry", fieldbackground=[("focus", self.BG_TERTIARY)],
                 highlightbackground=[("focus", self.BG_TERTIARY)],
                 highlightcolor=[("focus", self.BG_TERTIARY)])

        # Force border colors to match background
        style.configure("TEntry", bordercolor=self.BG_SECONDARY, lightcolor=self.BG_SECONDARY, darkcolor=self.BG_SECONDARY,
                       insertcolor=self.FG_PRIMARY)
        
        # Combobox styling
        style.configure("TCombobox", fieldbackground=self.BG_SECONDARY, foreground=self.FG_PRIMARY, 
                   background=self.BG_SECONDARY, borderwidth=0, relief="flat", padding=4, font=("Segoe UI", 10),
                   highlightbackground=self.BG_SECONDARY, highlightcolor=self.BG_SECONDARY,
                   arrowcolor=self.FG_PRIMARY)
        style.map("TCombobox", 
                 fieldbackground=[("readonly", self.BG_SECONDARY), ("focus", self.BG_TERTIARY)],
                 background=[("active", self.BG_TERTIARY)],
                 foreground=[("focus", self.FG_PRIMARY)],
                 highlightbackground=[("focus", self.BG_TERTIARY)],
                 highlightcolor=[("focus", self.BG_TERTIARY)],
                 arrowcolor=[("active", self.FG_PRIMARY)])
        style.configure("TCombobox", bordercolor=self.BG_SECONDARY, lightcolor=self.BG_SECONDARY, darkcolor=self.BG_SECONDARY)

        # Strip internal borders for entry/combobox
        style.layout("TEntry", [("Entry.field", {"sticky": "nswe", "children": [("Entry.padding", {"sticky": "nswe", "children": [("Entry.textarea", {"sticky": "nswe"})]})]})])
        
        # Dark.TEntry - special style with complete border removal
        style.configure("Dark.TEntry", fieldbackground=self.BG_SECONDARY, foreground=self.FG_PRIMARY,
                       padding=6, borderwidth=0, relief="flat", font=("Segoe UI", 10))
        style.layout("Dark.TEntry", [("Entry.field", {"sticky": "nswe", "border": 0, "children": [("Entry.padding", {"sticky": "nswe", "children": [("Entry.textarea", {"sticky": "nswe"})]})]})])
        style.map("Dark.TEntry", fieldbackground=[("focus", self.BG_TERTIARY)])
        style.layout("TCombobox", [
            ("Combobox.field", {"sticky": "nswe", "children": [
                ("Combobox.padding", {"sticky": "nswe", "children": [
                    ("Combobox.textarea", {"sticky": "nswe"})
                ]})
            ]}),
            ("Combobox.downarrow", {"side": "right", "sticky": "ns"})
        ])
        
        # Dark.TCombobox - special style with complete border removal
        style.configure("Dark.TCombobox", fieldbackground=self.BG_SECONDARY, foreground=self.FG_PRIMARY,
                       background=self.BG_SECONDARY, borderwidth=0, relief="flat", padding=4, font=("Segoe UI", 10),
                       arrowcolor=self.FG_PRIMARY)
        style.layout("Dark.TCombobox", [
            ("Combobox.field", {"sticky": "nswe", "border": 0, "children": [
                ("Combobox.padding", {"sticky": "nswe", "children": [
                    ("Combobox.textarea", {"sticky": "nswe"})
                ]})
            ]}),
            ("Combobox.downarrow", {"side": "right", "sticky": "ns"})
        ])
        style.map("Dark.TCombobox", fieldbackground=[("readonly", self.BG_SECONDARY), ("focus", self.BG_TERTIARY)],
                 arrowcolor=[("active", self.FG_PRIMARY)])
        
        # Treeview styling
        style.configure("Treeview", background=self.BG_SECONDARY, foreground=self.FG_PRIMARY, 
               fieldbackground=self.BG_SECONDARY, borderwidth=0, relief="flat", rowheight=26, font=("Segoe UI", 10),
               lightcolor=self.BG_TERTIARY, darkcolor=self.BG_TERTIARY)
        style.configure("Treeview.Heading", background=self.BG_TERTIARY, foreground=self.FG_PRIMARY, 
               borderwidth=0, relief="flat", font=("Segoe UI", 10, "bold"),
               lightcolor=self.BG_TERTIARY, darkcolor=self.BG_TERTIARY)
        style.map("Treeview", 
                 background=[("selected", self.ACCENT)], 
                 foreground=[("selected", "white")])
        style.map("Treeview.Heading", 
                 background=[("active", self.ACCENT)])

        # Add vertical gridlines only; keep header border off to avoid white line
        style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
        self.root.option_add("*Treeview*Heading.borderWidth", 0)
        self.root.option_add("*Treeview.borderWidth", 0)
        self.root.option_add("*Treeview.gridLines", "vertical")
        
        # Scrollbar styling
        style.configure("TScrollbar", background=self.BG_TERTIARY, troughcolor=self.BG_SECONDARY,
               borderwidth=0, arrowcolor=self.BG_TERTIARY, lightcolor=self.BG_TERTIARY, darkcolor=self.BG_TERTIARY,
               width=10, arrowsize=0)
        style.configure("Vertical.TScrollbar", background=self.BG_TERTIARY, troughcolor=self.BG_SECONDARY,
               borderwidth=0, arrowcolor=self.BG_TERTIARY, lightcolor=self.BG_TERTIARY, darkcolor=self.BG_TERTIARY,
               width=10, arrowsize=0)
        style.map("TScrollbar", background=[("active", self.ACCENT)])
        style.map("Vertical.TScrollbar", background=[("active", self.ACCENT)])
        
        # Checkbutton styling
        style.configure("TCheckbutton", background=self.BG_PRIMARY, foreground=self.FG_PRIMARY, font=("Segoe UI", 10))
        style.map("TCheckbutton", background=[("active", self.BG_SECONDARY)])
        
        self.root.configure(bg=self.BG_PRIMARY)
        self.root.tk_setPalette(background=self.BG_PRIMARY, foreground=self.FG_PRIMARY)
        self.root.option_add("*TCombobox*Listbox.background", self.BG_SECONDARY)
        self.root.option_add("*TCombobox*Listbox.foreground", self.FG_PRIMARY)
        self.root.option_add("*TCombobox*Listbox.selectBackground", self.ACCENT)
        self.root.option_add("*TCombobox*Listbox.selectForeground", "white")
        self.root.option_add("*TCombobox*Listbox.relief", "flat")
        self.root.option_add("*TCombobox*Listbox.borderWidth", 0)
        self.root.option_add("*Entry.relief", "flat")
        self.root.option_add("*Entry.borderWidth", 0)
        self.root.option_add("*Entry.highlightThickness", 0)
        self.root.option_add("*Entry.highlightBackground", self.BG_SECONDARY)
        self.root.option_add("*TEntry.highlightThickness", 0)
        self.root.option_add("*TEntry.highlightBackground", self.BG_SECONDARY)
        self.root.option_add("*TCombobox.highlightThickness", 0)
        self.root.option_add("*TCombobox.highlightBackground", self.BG_SECONDARY)
        self.root.option_add("*Listbox.relief", "flat")
        self.root.option_add("*Listbox.borderWidth", 0)
        self.root.option_add("*Listbox.highlightThickness", 0)
        
        self.root.configure(bg=self.BG_PRIMARY)
        
        header = tk.Frame(self.root, bg=self.ACCENT, height=60)
        header.pack(fill="x", side="top")
        
        title = tk.Label(header, text="IST Fenix Auto Enroller", 
                font=("Segoe UI", 20, "bold"), bg=self.ACCENT, fg="white")
        title.pack(pady=(10, 0))

        subtitle = tk.Label(header, text="by nos4a2 (Ângelo Azevedo)",
                    font=("Segoe UI", 10), bg=self.ACCENT, fg="#e6f2ff")
        subtitle.pack(pady=(0, 8))
        
        # Create resizable vertical panes (main content + live log)
        panes = tk.PanedWindow(self.root, orient="vertical", sashwidth=6, sashrelief="raised",
                              bg=self.BG_PRIMARY)
        panes.pack(fill="both", expand=True, side="top")

        # Create scrollable main area using canvas
        scrollable_frame = tk.Frame(panes, bg=self.BG_PRIMARY)
        
        canvas = tk.Canvas(scrollable_frame, bg=self.BG_PRIMARY, highlightthickness=0, highlightcolor=self.BG_PRIMARY, selectbackground=self.BG_SECONDARY)
        scrollbar = ttk.Scrollbar(scrollable_frame, orient="vertical", command=canvas.yview)
        scrollable_content = tk.Frame(canvas, bg=self.BG_PRIMARY, highlightthickness=0)
        
        scrollable_content.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas_window = canvas.create_window((0, 0), window=scrollable_content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Bind mousewheel to canvas (works on Windows and Linux)
        def on_mousewheel(event):
            if event.num == 5 or event.delta < 0:
                canvas.yview_scroll(3, "units")
            elif event.num == 4 or event.delta > 0:
                canvas.yview_scroll(-3, "units")
            return "break"
        
        # Bind only to main scrollable widgets (avoid global bind_all)
        for widget in [canvas, scrollable_content, scrollable_frame]:
            widget.bind("<MouseWheel>", on_mousewheel)
            widget.bind("<Button-4>", on_mousewheel)
            widget.bind("<Button-5>", on_mousewheel)
        
        # Make canvas fill width when window is resized
        def on_canvas_configure(event):
            canvas.itemconfig(canvas_window, width=event.width)
        canvas.bind('<Configure>', on_canvas_configure)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        panes.add(scrollable_frame, stretch="always")
        
        # Main content frame (use this instead of 'main')
        main = tk.Frame(scrollable_content, bg=self.BG_PRIMARY, highlightthickness=0)
        main.pack(fill="x", padx=10, pady=10)
        
        select_frame = tk.LabelFrame(main, text="Select Degree, Semester & Period", padx=12, pady=8,
                         bg=self.BG_PRIMARY, fg=self.FG_PRIMARY, bd=0, relief="flat", highlightthickness=0,
                         font=("Segoe UI", 10, "bold"))
        select_frame.pack(fill="x", pady=(0, 10))

        # Semester selection
        ttk.Label(select_frame, text="Semester:").grid(row=0, column=0, sticky="w")
        self.semester_combo = ttk.Combobox(select_frame, width=15, values=["1st Semester", "2nd Semester"], state="readonly", style="Dark.TCombobox")
        self.semester_combo.grid(row=0, column=1, padx=5, sticky="w")
        self.semester_combo.set("1st Semester")
        self.semester_combo.bind("<<ComboboxSelected>>", lambda e: self.on_semester_selected())
        
        # Language selection
        ttk.Label(select_frame, text="Lang:").grid(row=0, column=2, sticky="w", padx=(20, 0))
        self.lang_combo = ttk.Combobox(select_frame, width=12, values=["pt-PT", "en-GB"], state="readonly", style="Dark.TCombobox")
        self.lang_combo.grid(row=0, column=3, padx=5, sticky="w")
        self.lang_combo.set("pt-PT")
        self.lang_combo.bind("<<ComboboxSelected>>", lambda e: self.on_semester_selected())
        
        # Degree search
        ttk.Label(select_frame, text="Degree search:").grid(row=1, column=0, sticky="w", pady=(10, 0))
        self.degree_filter_var = tk.StringVar()
        self.degree_filter_entry = tk.Entry(select_frame, width=40, textvariable=self.degree_filter_var,
                                            bg=self.BG_SECONDARY, fg=self.FG_PRIMARY,
                                            insertbackground=self.FG_PRIMARY, relief="flat", bd=0,
                                            highlightthickness=0, font=("Segoe UI", 10))
        self.degree_filter_entry.grid(row=1, column=1, columnspan=5, padx=5, sticky="ew", pady=(10, 0))
        self.degree_filter_entry.bind("<KeyRelease>", lambda _e: self.filter_degrees())
        
        self.degree_listbox = tk.Listbox(
            select_frame,
            height=4,
            exportselection=False,
            bg=self.BG_SECONDARY,
            fg=self.FG_PRIMARY,
            selectbackground=self.ACCENT,
            selectforeground="white",
            highlightthickness=0,
            bd=0,
            relief="flat",
            font=("Segoe UI", 10)
        )
        self.degree_listbox.grid(row=2, column=0, columnspan=6, sticky="nsew", padx=5, pady=5)
        self.degree_listbox.bind("<<ListboxSelect>>", lambda e: self.on_degree_list_select())
        
        degree_scroll = ttk.Scrollbar(select_frame, orient="vertical", command=self.degree_listbox.yview)
        degree_scroll.grid(row=2, column=6, sticky="ns", pady=5)
        self.degree_listbox.configure(yscrollcommand=degree_scroll.set)

        self.degrees_loading_frame = tk.Frame(select_frame, bg=self.BG_PRIMARY)
        self.degrees_loading_label = ttk.Label(self.degrees_loading_frame, text="Loading degrees...")
        self.degrees_loading_label.pack(side="left")
        self.degrees_loading_bar = ttk.Progressbar(self.degrees_loading_frame, mode="indeterminate", length=140)
        self.degrees_loading_bar.pack(side="left", padx=8)
        self.degrees_loading_frame.grid(row=3, column=0, columnspan=6, sticky="w", padx=5, pady=(0, 5))
        self.degrees_loading_frame.grid_remove()
        
        search_frame = tk.LabelFrame(main, text="Search Courses", padx=10, pady=8,
                         bg=self.BG_PRIMARY, fg=self.FG_PRIMARY, bd=0, relief="flat", highlightthickness=0,
                         font=("Segoe UI", 10, "bold"))
        search_frame.pack(fill="x", pady=(0, 10))
        
        ttk.Label(search_frame, text="Course Name/Code:").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(search_frame, width=40, textvariable=self.search_var,
                                     bg=self.BG_SECONDARY, fg=self.FG_PRIMARY,
                                     insertbackground=self.FG_PRIMARY, relief="flat", bd=0,
                                     highlightthickness=0, font=("Segoe UI", 10))
        self.search_entry.pack(side="left", padx=5)
        self.search_entry.bind("<KeyRelease>", lambda _e: self.filter_courses_display())
        
        ttk.Label(search_frame, text="Period:").pack(side="left", padx=(20, 0))
        self.period_combo = ttk.Combobox(search_frame, width=10, values=["P1", "P2"], state="readonly", style="Dark.TCombobox")
        self.period_combo.pack(side="left", padx=5)
        self.period_combo.set("P1")
        self.period_combo.bind("<<ComboboxSelected>>", lambda e: self.filter_courses_display())
        
        ttk.Button(search_frame, text="Clear", command=self.clear_search).pack(side="left", padx=5)
        ttk.Label(search_frame, textvariable=self.selected_count_var).pack(side="right", padx=5)
        
        courses_label_frame = tk.LabelFrame(main, text="Available Courses (select multiple)", padx=10, pady=8,
                            bg=self.BG_PRIMARY, fg=self.FG_PRIMARY, bd=0, relief="flat", highlightthickness=0,
                            font=("Segoe UI", 10, "bold"))
        courses_label_frame.pack(fill="both", expand=True, pady=(0, 10))

        self.courses_loading_frame = tk.Frame(courses_label_frame, bg=self.BG_PRIMARY)
        self.courses_loading_label = ttk.Label(self.courses_loading_frame, text="Loading courses...")
        self.courses_loading_label.pack(side="left")
        self.courses_loading_bar = ttk.Progressbar(self.courses_loading_frame, mode="indeterminate", length=160)
        self.courses_loading_bar.pack(side="left", padx=8)
        self.courses_loading_frame.pack(fill="x", pady=(0, 6))
        self.courses_loading_frame.pack_forget()
        
        self.courses_canvas = tk.Canvas(courses_label_frame, bg=self.BG_SECONDARY, highlightthickness=0, highlightcolor=self.BG_SECONDARY, selectbackground=self.BG_TERTIARY)
        self.courses_scroll = ttk.Scrollbar(courses_label_frame, orient="vertical", command=self.courses_canvas.yview)
        self.courses_container = tk.Frame(self.courses_canvas, bg=self.BG_SECONDARY, highlightthickness=0)
        
        self.courses_container.bind(
            "<Configure>",
            lambda e: self.courses_canvas.configure(scrollregion=self.courses_canvas.bbox("all"))
        )
        
        self.courses_canvas.create_window((0, 0), window=self.courses_container, anchor="nw")
        self.courses_canvas.configure(yscrollcommand=self.courses_scroll.set)
        
        # Add mousewheel binding to courses canvas
        def on_courses_mousewheel(event):
            if event.num == 5 or event.delta < 0:
                self.courses_canvas.yview_scroll(3, "units")
            elif event.num == 4 or event.delta > 0:
                self.courses_canvas.yview_scroll(-3, "units")
        
        for widget in [self.courses_canvas, self.courses_container]:
            widget.bind("<MouseWheel>", on_courses_mousewheel)
            widget.bind("<Button-4>", on_courses_mousewheel)
            widget.bind("<Button-5>", on_courses_mousewheel)
        
        self.courses_canvas.pack(side="left", fill="both", expand=True)
        self.courses_scroll.pack(side="right", fill="y")
        
        btn_frame = tk.Frame(courses_label_frame, bg=self.BG_PRIMARY, highlightthickness=0)
        btn_frame.pack(fill="x", pady=(10, 0))

        btn_top = tk.Frame(btn_frame, bg=self.BG_PRIMARY, highlightthickness=0)
        btn_top.pack(fill="x")

        ttk.Button(btn_top, text="[All] Select All", command=self.select_all_courses).pack(side="left", padx=5)
        ttk.Button(btn_top, text="[None] Clear Selection", command=self.clear_course_selection).pack(side="left", padx=5)

        ttk.Button(
            btn_frame,
            text="[Build] Build Schedule",
            command=self.on_build_schedule_clicked,
            style="Big.TButton"
        ).pack(fill="x", padx=5, pady=(8, 0), ipady=8)
        
        queue_frame = tk.LabelFrame(main, text="Enrollment Queue", padx=10, pady=8,
                        bg=self.BG_PRIMARY, fg=self.FG_PRIMARY, bd=0, relief="flat", highlightthickness=0,
                        font=("Segoe UI", 10, "bold"))
        queue_frame.pack(fill="both", expand=True, pady=(0, 10))
        
        self.tree = ttk.Treeview(queue_frame, columns=("Course", "Type", "Shift"), show="headings", height=4, style="Treeview")
        self.tree.heading("#0", text="")
        self.tree.heading("Course", text="Course Name")
        self.tree.heading("Type", text="Shift Type")
        self.tree.heading("Shift", text="Shift Name")
        
        self.tree.column("#0", width=0, stretch=False)
        self.tree.column("Course", width=480)
        self.tree.column("Type", width=90)
        self.tree.column("Shift", width=180)

        # Alternating row colors to simulate grid lines
        self.tree.tag_configure("evenrow", background=self.BG_SECONDARY, foreground=self.FG_PRIMARY)
        self.tree.tag_configure("oddrow", background=self.BG_TERTIARY, foreground=self.FG_PRIMARY)
        
        self.tree.pack(side="left", fill="both", expand=True)
        
        scrollbar2 = ttk.Scrollbar(queue_frame, orient="vertical", command=self.tree.yview)
        scrollbar2.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar2.set)
        
        btn_frame = tk.Frame(queue_frame, bg=self.BG_PRIMARY, highlightthickness=0)
        btn_frame.pack(fill="x", pady=(10, 0))
        
        ttk.Button(btn_frame, text="[-] Remove", command=self.remove_enrollment).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="[Save] Save", command=self.save_config).pack(side="left", padx=5)
        
        login_frame = tk.LabelFrame(main, text="Login", padx=12, pady=8,
                        bg=self.BG_PRIMARY, fg=self.FG_PRIMARY, bd=0, relief="flat", highlightthickness=0,
                        font=("Segoe UI", 10, "bold"))
        login_frame.pack(fill="x", pady=(0, 10))
        
        ttk.Label(login_frame, text="Username:").grid(row=0, column=0, sticky="w", pady=(5, 8))
        self.username_entry = tk.Entry(login_frame, width=25, bg=self.BG_SECONDARY, fg=self.FG_PRIMARY,
                                       insertbackground=self.FG_PRIMARY, relief="flat", bd=0,
                                       highlightthickness=0, font=("Segoe UI", 10))
        self.username_entry.grid(row=0, column=1, padx=5, pady=(5, 8))
        
        ttk.Label(login_frame, text="Password:").grid(row=1, column=0, sticky="w", pady=(0, 8))
        self.password_entry = tk.Entry(login_frame, width=25, show="●", bg=self.BG_SECONDARY, fg=self.FG_PRIMARY,
                                       insertbackground=self.FG_PRIMARY, relief="flat", bd=0,
                                       highlightthickness=0, font=("Segoe UI", 10))
        self.password_entry.grid(row=1, column=1, padx=5, pady=(0, 8))
        
        self.login_btn = ttk.Button(login_frame, text="Login", command=self.login)
        self.login_btn.grid(row=0, column=2, rowspan=2, padx=10, sticky="ns")
        
        self.status_label = ttk.Label(login_frame, text="● Not logged in", foreground="red")
        self.status_label.grid(row=2, column=0, columnspan=3, pady=(10, 0))
        
        action_frame = tk.LabelFrame(main, text="Enrollment", padx=12, pady=8,
                         bg=self.BG_PRIMARY, fg=self.FG_PRIMARY, bd=0, relief="flat", highlightthickness=0,
                         font=("Segoe UI", 10, "bold"))
        action_frame.pack(fill="x", pady=(0, 10))
        
        btn_container = tk.Frame(action_frame, bg=self.BG_PRIMARY, highlightthickness=0)
        btn_container.pack(fill="x")

        top_row = tk.Frame(btn_container, bg=self.BG_PRIMARY, highlightthickness=0)
        top_row.pack(fill="x")

        self.enroll_btn = ttk.Button(top_row, text="[Run] Start", 
                         command=self.start_enrollment, state="disabled")
        self.enroll_btn.pack(side="left", padx=5)

        self.cancel_btn = ttk.Button(top_row, text="[Stop] Cancel", 
             command=self.cancel_enrollment, state="disabled")
        self.cancel_btn.pack(side="left", padx=5)

        self.timed_btn = ttk.Button(top_row, text="[Time] Schedule", 
            command=self.schedule_enrollment, state="disabled")
        self.timed_btn.pack(side="left", padx=5)
        
        # Log frame as a resizable pane (always visible at bottom)
        log_frame = tk.Frame(panes, bg=self.BG_PRIMARY, highlightthickness=0, bd=0, relief="flat")
        log_frame.configure(height=120)

        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", style="Vertical.TScrollbar")
        self.log_text = tk.Text(log_frame, height=3, state="disabled", font=("Courier", 9),
                    bg="#121212", fg="#e6e6e6", relief="flat", borderwidth=0,
                    yscrollcommand=log_scroll.set)
        log_scroll.config(command=self.log_text.yview)
        log_scroll.pack(side="right", fill="y")
        self.log_text.pack(side="left", fill="both", expand=True)

        # Configure text tags for colors (vivid + bold)
        self.log_text.tag_configure("INFO", foreground="#3B82F6", font=("Courier", 9, "bold"))      # Vivid Blue
        self.log_text.tag_configure("SUCCESS", foreground="#22C55E", font=("Courier", 9, "bold"))   # Vivid Green
        self.log_text.tag_configure("ERROR", foreground="#EF4444", font=("Courier", 9, "bold"))     # Vivid Red
        self.log_text.tag_configure("WARNING", foreground="#F59E0B", font=("Courier", 9, "bold"))   # Vivid Amber
        self.log_text.tag_configure("DEBUG", foreground="#8B5CF6", font=("Courier", 9, "bold"))     # Vivid Purple

        # Make log scroll independent from main canvas
        def on_log_wheel(event):
            if event.num == 5 or event.delta < 0:
                self.log_text.yview_scroll(3, "units")
            elif event.num == 4 or event.delta > 0:
                self.log_text.yview_scroll(-3, "units")
            return "break"
        self.log_text.bind("<MouseWheel>", on_log_wheel)
        self.log_text.bind("<Button-4>", on_log_wheel)
        self.log_text.bind("<Button-5>", on_log_wheel)

        # Global mousewheel for main canvas (skip log/courses/tree)
        def on_global_mousewheel(event):
            w = event.widget
            if w is self.log_text:
                return
            if hasattr(self, "courses_canvas") and w in (self.courses_canvas, self.courses_container):
                return
            if hasattr(self, "tree") and w is self.tree:
                return
            if hasattr(self, "degree_listbox") and w is self.degree_listbox:
                return
            return on_mousewheel(event)

        self.root.bind_all("<MouseWheel>", on_global_mousewheel)
        self.root.bind_all("<Button-4>", on_global_mousewheel)
        self.root.bind_all("<Button-5>", on_global_mousewheel)

        panes.add(log_frame, stretch="never")

        # Set a smaller default log height
        self.root.update_idletasks()
        try:
            target_y = max(200, self.root.winfo_height() - 180)
            panes.sash_place(0, 0, target_y)
        except Exception:
            pass
        
    def log(self, message: str, level: str = "INFO"):
        ts = datetime.now().strftime("%H:%M:%S")
        prefix_map = {"INFO": "INFO", "SUCCESS": "OK", "ERROR": "ERROR", "WARNING": "WARN", "DEBUG": "DEBUG"}
        prefix = prefix_map.get(level, "INFO")
        msg = f"[{ts}] [{prefix}] {message}\n"
        
        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg, level)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
        self.root.update()

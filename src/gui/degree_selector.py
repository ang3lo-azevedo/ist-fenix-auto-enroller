import tkinter as tk
from tkinter import ttk
import threading
from ..utils import get_degree_type_name


class DegreeSelectorMixin:
    """Mixin for degree selection functionality"""

    def _set_degrees_loading(self, is_loading: bool):
        if not hasattr(self, "degrees_loading_frame"):
            return
        if is_loading:
            try:
                self.degrees_loading_frame.grid()
                self.degrees_loading_bar.start(10)
            except Exception:
                pass
        else:
            try:
                self.degrees_loading_bar.stop()
                self.degrees_loading_frame.grid_remove()
            except Exception:
                pass

    def populate_degrees(self, degrees):
        self.degrees = degrees or []
        self.degree_map = {}
        self.degree_acronym_map = {}
        labels = []
        saved_id = getattr(self, "_saved_degree_id", None)

        def degree_sort_key(d):
            dtype = get_degree_type_name(d)
            type_priority = {k: i for i, k in enumerate(["MEIC", "MEGI", "MEA", "LETI", "LEIC", "LEE", "Other"])}
            pri = type_priority.get(dtype, 100)
            acronym = d.get("acronym") or ""
            return (pri, acronym)

        sorted_degrees = sorted(self.degrees, key=degree_sort_key)
        
        for d in sorted_degrees:
            degree_id = d.get("id")
            acronym = d.get("acronym") or ""
            name = d.get("name") or ""
            
            display_name = f"[{acronym}] {name}" if acronym else name
            labels.append(display_name)
            if degree_id:
                self.degree_map[display_name] = str(degree_id)
                self.degree_acronym_map[display_name] = acronym
        
        self.degree_labels = labels
        # If we have a saved degree_id from config, select it; otherwise select first
        saved_id = getattr(self, "_saved_degree_id", None)
        self.log(f"populate_degrees: saved_id={saved_id}, selected_degree_id={self.selected_degree_id}", "DEBUG")
        
        has_saved_courses = bool(getattr(self, "saved_selected_course_ids", set()))

        if saved_id and not self.selected_degree_id:
            self.log(f"Attempting to select saved degree: {saved_id}", "DEBUG")
            # Don't let filter_degrees auto-select; we'll do it ourselves
            self.filter_degrees(skip_auto_select=True)
            self.select_degree_by_id(saved_id)
            self.on_degree_selected()  # Trigger course loading
        elif labels and not self.selected_degree_id and has_saved_courses:
            self.log(f"No saved degree, selecting first: {labels[0]}", "DEBUG")
            self.filter_degrees(skip_auto_select=True)
            self.select_degree_by_id(self.degree_map.get(labels[0], ""))
            self.on_degree_selected()  # Trigger course loading
        else:
            self.filter_degrees()
    
    def get_selected_degree_id(self):
        return self.selected_degree_id
    
    def select_degree_by_id(self, degree_id: str):
        if not degree_id:
            return
        for label, did in self.degree_map.items():
            if str(did) == str(degree_id):
                self.selected_degree_id = str(did)
                self.degree_filter_var.set(label)
                self.filter_degrees()
                self.select_degree_label(label)
                return

    def filter_degrees(self, skip_auto_select=False):
        query = (self.degree_filter_var.get() or "").strip().lower()
        labels = list(self.degree_map.keys())
        if not query:
            filtered = labels
        else:
            filtered = [l for l in labels if query in l.lower()]
        
        self.degree_listbox.delete(0, "end")
        for label in filtered:
            self.degree_listbox.insert("end", label)
        if filtered and not skip_auto_select:
            self.degree_listbox.selection_set(0)
            self.select_degree_label(filtered[0])

    def on_degree_list_select(self):
        selection = self.degree_listbox.curselection()
        if not selection:
            return
        label = self.degree_listbox.get(selection[0])
        self.select_degree_label(label)
        self.on_degree_selected()

    def select_degree_label(self, label: str):
        if not label:
            return
        self.selected_degree_id = self.degree_map.get(label, "")
        self.selected_degree_acronym = self.degree_acronym_map.get(label, "")
    
    def on_degree_selected(self):
        degree_id = self.get_selected_degree_id()
        if not degree_id:
            return
        self.on_semester_selected()
    
    def load_degrees_async(self):
        self._set_degrees_loading(True)

        def load_thread():
            try:
                term = self.academic_term
                degrees = self.api.get_degrees_all()
                valid_degrees = [d for d in degrees if term in d.get("academicTerms", [])]
                self.root.after(0, lambda: (self.populate_degrees(valid_degrees), self._set_degrees_loading(False)))
            except Exception as e:
                self.root.after(0, lambda: (self.log(f"Error loading degrees: {e}", "ERROR"), self._set_degrees_loading(False)))
        
        threading.Thread(target=load_thread, daemon=True).start()

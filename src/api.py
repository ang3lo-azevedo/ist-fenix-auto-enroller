import requests
import re
from bs4 import BeautifulSoup
from .config import BASE_URL, DEFAULT_LANG, DEFAULT_ACADEMIC_TERM, DEFAULT_SESSION_TIMEOUT


class FenixAPI:
    def __init__(self, lang: str = DEFAULT_LANG, academic_term: str = DEFAULT_ACADEMIC_TERM):
        self.session = requests.Session()
        self.session.timeout = DEFAULT_SESSION_TIMEOUT
        self.lang = lang
        self.academic_term = academic_term
        self._curriculum_cache = {}
        self._course_pt_cache = {}
        
    def set_lang(self, lang: str):
        if lang:
            self.lang = lang
        
    def set_academic_term(self, academic_term: str):
        if academic_term:
            self.academic_term = academic_term
        
    def get_degrees_all(self):
        try:
            resp = self.session.get(
                f"{BASE_URL}/degrees/all",
                params={"lang": self.lang}
            )
            return resp.json() if resp.ok else []
        except Exception as e:
            print(f"Error getting degrees: {e}")
            return []
    
    def get_degree_courses(self, degree_id: str, academic_term: str = None, enrich: bool = True, degree_acronym: str = ""):
        try:
            term = academic_term or self.academic_term
            resp = self.session.get(
                f"{BASE_URL}/degrees/{degree_id}/courses",
                params={"academicTerm": term, "lang": self.lang}
            )
            courses = resp.json() if resp.ok else []
            
            # Enrich courses with schedule data, semester_hint, and period_hint
            if enrich:
                curriculum_html = None
                if degree_acronym:
                    curriculum_html = self._get_degree_curriculum_html(degree_acronym, term)

                enriched_courses = []
                for course in courses:
                    course_id = course.get("id") or course.get("courseId")
                    if not course_id:
                        continue
                    
                    # Extract semester from academicTerm field (e.g., "1 Semestre 2024/2025")
                    semester_hint = self._extract_semester_from_course(course)
                    
                    # Fetch schedule to get period and shifts
                    schedule = self.get_course_schedule(course_id)
                    period_hint = self._extract_period_from_schedule(course, schedule)

                    if not period_hint and curriculum_html:
                        course_name = course.get("name", "")
                        if self.lang != "pt-PT":
                            pt_name, pt_url = self._get_course_pt_name_url(course_id)
                            if pt_name:
                                course_name = pt_name
                        period_hint = self._extract_period_from_curriculum(course, course_name, curriculum_html)
                    shifts = schedule.get("shifts") or []
                    
                    enriched_courses.append({
                        "id": course_id,
                        "name": course.get("name", "Unknown"),
                        "code": course.get("code", ""),
                        "acronym": course.get("acronym", ""),
                        "academicTerm": course.get("academicTerm", ""),
                        "shifts": shifts,
                        "courseLoads": schedule.get("courseLoads", []),
                        "semester_hint": semester_hint,
                        "period_hint": period_hint
                    })
                return enriched_courses
            
            return courses
        except Exception as e:
            print(f"Error getting degree courses: {e}")
            return []
    
    def _extract_semester_from_course(self, course):
        """Extract semester number from course academicTerm field"""
        # Format: "1 Semestre 2024/2025" or "2 Semestre 2024/2025"
        academic_term = course.get("academicTerm", "")
        if academic_term and len(academic_term) > 0:
            if academic_term[0] in ["1", "2"]:
                return academic_term[0]
        
        # Fallback: search for semester patterns
        match = re.search(r"\b([12])\s*(st|nd|º)?\s*(semester|semestre)\b", academic_term, re.IGNORECASE)
        if match:
            return match.group(1)
        
        return ""
    
    def _extract_period_from_schedule(self, course, schedule):
        """Extract period (P1-P4) from schedule metadata"""
        text_candidates = []
        
        def collect_text(val):
            if not val:
                return
            if isinstance(val, str):
                text_candidates.append(val)
            elif isinstance(val, dict):
                for k in ["name", "label", "acronym", "shortName", "value"]:
                    if k in val and isinstance(val[k], str):
                        text_candidates.append(val[k])
        
        # Collect from course and schedule metadata
        for key in ["executionPeriod", "period", "semester", "academicTerm", "term"]:
            collect_text(course.get(key))
            collect_text(schedule.get(key))
        
        # Collect from courseLoads
        for load in schedule.get("courseLoads") or []:
            if isinstance(load, dict):
                collect_text(load.get("executionPeriod"))
                collect_text(load.get("period"))
        
        # Search for P1-P4 patterns
        joined = " ".join(text_candidates).upper()
        match = re.search(r"\bP[1-4]\b", joined)
        if match:
            return match.group(0)
        
        # Fallback: check for individual periods
        for period in ["P1", "P2", "P3", "P4"]:
            if period in joined:
                return period
        
        return ""

    def _get_course_pt_name_url(self, course_id: str):
        if course_id in self._course_pt_cache:
            return self._course_pt_cache[course_id]
        try:
            resp = self.session.get(
                f"{BASE_URL}/courses/{course_id}",
                params={"lang": "pt-PT"}
            )
            if resp.ok:
                data = resp.json()
                name = data.get("name", "")
                url = data.get("url", "")
                self._course_pt_cache[course_id] = (name, url)
                return name, url
        except Exception:
            pass
        self._course_pt_cache[course_id] = ("", "")
        return "", ""

    def _get_degree_curriculum_html(self, degree_acronym: str, academic_term: str):
        key = (degree_acronym, academic_term)
        if key in self._curriculum_cache:
            return self._curriculum_cache[key]
        try:
            base_url = f"https://fenix.tecnico.ulisboa.pt/cursos/{degree_acronym.lower()}/curriculo"
            resp = self.session.get(base_url)
            if not resp.ok:
                return None
            html = resp.text
            soup = BeautifulSoup(html, "html.parser")
            year_param = None
            # Try to find the year link that matches the academic term
            for a in soup.select("div#content-block ul.dropdown-menu a"):
                text = (a.get_text() or "").strip()
                if academic_term in text:
                    href = a.get("href") or ""
                    match = re.search(r"year=(\d+)", href)
                    if match:
                        year_param = match.group(1)
                        break
            if year_param:
                resp = self.session.get(f"{base_url}?year={year_param}")
                if resp.ok:
                    html = resp.text
            self._curriculum_cache[key] = html
            return html
        except Exception:
            return None

    def _extract_period_from_curriculum(self, course, course_name: str, curriculum_html: str):
        if not course_name or not curriculum_html:
            return ""
        try:
            soup = BeautifulSoup(curriculum_html, "html.parser")
            course_name = course_name.strip()
            matches = []
            for a in soup.find_all("a"):
                name = (a.get_text() or "").strip()
                if name == course_name or (name.startswith(course_name) and name.endswith(")")):
                    sib = a.find_next_sibling("div")
                    if sib:
                        matches.append((a, sib.get_text(" ", strip=True)))

            if not matches:
                return ""

            semester_hint = course.get("semester_hint") or (course.get("academicTerm") or "")[:1]
            semester = int(semester_hint) if str(semester_hint).isdigit() else None

            def period_from_text(txt: str):
                parts = txt.split(",")
                if len(parts) < 2:
                    return ""
                return parts[1].replace("\t", "").replace(" ", "").strip()

            # If only one match
            if len(matches) == 1:
                return period_from_text(matches[0][1])

            # Multiple matches: choose by semester
            for _, txt in matches:
                p = period_from_text(txt)
                p_upper = p.upper()
                if semester == 1 and (p_upper in {"P1", "P2"} or (p_upper.startswith("S") and "1" in p_upper)):
                    return p
                if semester == 2 and (p_upper in {"P3", "P4"} or (p_upper.startswith("S") and "2" in p_upper)):
                    return p

            # Fallback to first match
            return period_from_text(matches[0][1])
        except Exception:
            return ""
    
    def get_course_schedule(self, course_id: str):
        try:
            resp = self.session.get(
                f"{BASE_URL}/courses/{course_id}/schedule",
                params={"lang": self.lang}
            )
            return resp.json() if resp.ok else {}
        except Exception as e:
            print(f"Error getting course schedule: {e}")
            return {}
    
    def search_courses(self, search_term: str, degree_id: str, academic_term: str = None):
        try:
            all_courses = self.get_degree_courses(degree_id, academic_term)
            results = []
            search_lower = search_term.lower()
            
            for course in all_courses:
                name = (course.get("name") or "").lower()
                code = (course.get("code") or "").lower()
                acronym = (course.get("acronym") or "").lower()
                
                if search_lower in name or search_lower in code or search_lower in acronym:
                    course_id = course.get("id") or course.get("courseId")
                    schedule = self.get_course_schedule(course_id) if course_id else {}
                    shifts = schedule.get("shifts") or schedule.get("lessons") or schedule.get("events") or []
                    course_loads = schedule.get("courseLoads") or []
                    
                    results.append({
                        "id": course_id,
                        "name": course.get("name", "Unknown"),
                        "code": course.get("code", ""),
                        "acronym": course.get("acronym", ""),
                        "acYear": (academic_term or self.academic_term),
                        "shifts": shifts,
                        "courseLoads": course_loads
                    })
            
            return results
        except Exception as e:
            print(f"Error searching courses: {e}")
            return []

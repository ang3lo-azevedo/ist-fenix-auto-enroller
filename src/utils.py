from datetime import datetime


def normalize_shift_type(raw_value: str):
    raw_norm = str(raw_value).strip().upper()
    raw_lower = str(raw_value).strip().lower()

    if raw_norm in {"T", "TEO", "TEOR", "THEORY", "TEORICA", "TEÓRICA"} or "teórico" in raw_lower or "teorico" in raw_lower:
        return "T"
    if raw_norm in {"L", "LAB", "LABORATORIAL", "LABORATORIO", "LABORATÓRIO"} or "laboratório" in raw_lower or "laboratorio" in raw_lower:
        return "L"
    if raw_norm in {"TP", "TEORICO_PRATICA", "TEÓRICO-PRÁTICA"} or "teórico-prática" in raw_lower or "teorico-pratica" in raw_lower:
        return "TP"
    if raw_norm in {"PB"} or "problemas" in raw_lower:
        return "PB"
    if raw_norm in {"S", "SEM", "SEMINAR", "SEMINARY", "SEMINÁRIO", "SEMINARIO"} or "semin" in raw_lower:
        return "S"
    if raw_norm in {"TO", "TUTO", "TUTORIAL", "TUTORIAL_ORIENTATION", "ORIENTATION"} or "tutorial" in raw_lower or "orient" in raw_lower:
        return "TO"
    return ""


def detect_shift_types(shifts, course_loads=None):
    types = set()

    def add_from_raw(raw_value):
        raw_norm = str(raw_value).strip().upper()
        raw_lower = str(raw_value).strip().lower()

        if raw_norm in {"T", "TEO", "TEOR", "THEORY", "TEORICA", "TEÓRICA"} or "teórico" in raw_lower or "teorico" in raw_lower:
            types.add("T")
        if raw_norm in {"L", "LAB", "LABORATORIAL", "LABORATORIO", "LABORATÓRIO"} or "laboratório" in raw_lower or "laboratorio" in raw_lower:
            types.add("L")
        if raw_norm in {"TP", "TEORICO_PRATICA", "TEÓRICO-PRÁTICA"} or "teórico-prática" in raw_lower or "teorico-pratica" in raw_lower:
            types.add("TP")
        if raw_norm in {"PB"} or "problemas" in raw_lower:
            types.add("PB")
        if raw_norm in {"S", "SEM", "SEMINAR", "SEMINARY", "SEMINÁRIO", "SEMINARIO"} or "semin" in raw_lower:
            types.add("S")
        if raw_norm in {"TO", "TUTO", "TUTORIAL", "TUTORIAL_ORIENTATION", "ORIENTATION"} or "tutorial" in raw_lower or "orient" in raw_lower:
            types.add("TO")

    for shift in shifts or []:
        if isinstance(shift, dict):
            for t in (shift.get("types") or []):
                add_from_raw(t)
            add_from_raw(shift.get("type") or "")
            add_from_raw(shift.get("classType") or "")
            add_from_raw(shift.get("shiftType") or "")
            add_from_raw(shift.get("lessonType") or "")
            name = shift.get("name") or ""
            if name:
                # Check TP before T to avoid misclassification
                if "TP" in name:
                    types.add("TP")
                elif "T" in name and "L" not in name:
                    types.add("T")
                if "L" in name:
                    types.add("L")

    for load in course_loads or []:
        if isinstance(load, dict):
            add_from_raw(load.get("type") or "")

    return sorted(types)


def format_shift_summary(lessons):
    slots = []
    for lesson in lessons or []:
        start = lesson.get("start")
        end = lesson.get("end")
        campus = (
            (lesson.get("room") or {}).get("topLevelSpace") or {}
        ).get("name") or ""
        try:
            start_dt = datetime.strptime(start, "%Y-%m-%d %H:%M:%S")
            end_dt = datetime.strptime(end, "%Y-%m-%d %H:%M:%S")
            day = start_dt.strftime("%a")
            slot = f"{day} {start_dt.strftime('%H:%M')}-{end_dt.strftime('%H:%M')}"
        except Exception:
            slot = f"{start} - {end}"
        if campus:
            slot = f"{slot} ({campus})"
        if slot not in slots:
            slots.append(slot)
    return "; ".join(slots)


def get_shift_campus(shift):
    campuses = set()
    lessons = shift.get("lessons") or []
    for lesson in lessons:
        campus = (
            (lesson.get("room") or {}).get("topLevelSpace") or {}
        ).get("name") or ""
        if campus:
            campuses.add(campus)
    return campuses


def check_time_overlap(lesson1_start, lesson1_end, lesson2_start, lesson2_end):
    try:
        start1 = datetime.strptime(lesson1_start, "%Y-%m-%d %H:%M:%S")
        end1 = datetime.strptime(lesson1_end, "%Y-%m-%d %H:%M:%S")
        start2 = datetime.strptime(lesson2_start, "%Y-%m-%d %H:%M:%S")
        end2 = datetime.strptime(lesson2_end, "%Y-%m-%d %H:%M:%S")
        return start1 < end2 and start2 < end1
    except Exception:
        return False


def shifts_compatible(shift1, shift2):
    lessons1 = shift1.get("lessons") or []
    lessons2 = shift2.get("lessons") or []
    
    for l1 in lessons1:
        for l2 in lessons2:
            if check_time_overlap(
                l1.get("start"), l1.get("end"),
                l2.get("start"), l2.get("end")
            ):
                return False
    return True


def get_degree_type_name(d):
    degree_type = d.get("degreeType")
    if isinstance(degree_type, dict):
        name = degree_type.get("name") or degree_type.get("label")
        if name:
            return name

    raw = (
        d.get("degreeTypeName")
        or d.get("degreeType")
        or d.get("type")
        or d.get("cycleType")
        or ""
    )
    raw_upper = str(raw).upper()

    if "LICENCIATURA" in raw_upper or "BOLONHA_DEGREE" in raw_upper or "BACHELOR" in raw_upper or raw_upper == "DEGREE":
        return "Licenciatura"
    if "MESTRADO" in raw_upper or "MASTER" in raw_upper:
        return "Mestrado"
    if "MINOR" in raw_upper:
        return "Minor"
    if "AVANCADOS" in raw_upper or "ADVANCED" in raw_upper or "DEA" in raw_upper:
        return "Diploma de Estudos Avançados"
    if "HACS" in raw_upper:
        return "HACS"

    acronym = (d.get("acronym") or "").upper()
    if acronym.startswith("MIN-"):
        return "Minor"
    if acronym.startswith("HACS"):
        return "HACS"
    if acronym.startswith("DE") and len(acronym) > 2:
        return "Diploma de Estudos Avançados"
    if acronym.startswith("LE") or acronym.startswith("LMAC"):
        return "Licenciatura"
    if acronym.startswith("ME") or acronym.startswith("MA") or acronym.startswith("MMA"):
        return "Mestrado"

    name = d.get("name") or ""
    name_upper = name.upper()
    if "licenciatura" in name.lower():
        return "Licenciatura"
    if "mestrado" in name.lower():
        return "Mestrado"
    if "minor" in name.lower():
        return "Minor"
    if "avançados" in name.lower() or "advanced" in name.lower():
        return "Diploma de Estudos Avançados"

    return "Licenciatura"

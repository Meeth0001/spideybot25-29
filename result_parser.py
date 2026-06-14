import json
import logging

logger = logging.getLogger(__name__)

def _h(text: str) -> str:
    """Escape HTML special characters for Telegram HTML parse mode."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )

def extract_json(raw_text):
    """Extract a JSON object from a response that may include surrounding whitespace or warnings."""
    if not raw_text:
        return ""
    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return raw_text[start : end + 1]
    return raw_text

def load_json(raw_data):
    if not raw_data:
        return None
    try:
        return json.loads(extract_json(raw_data))
    except json.JSONDecodeError as exc:
        logger.error("Could not decode portal JSON: %s", exc)
        return None

def parse_semesters(raw_data):
    """
    Parse the portal's exam list response.
    Expected: {"error_code": 0, "data": [{"fexamno": "A-2025-2", "fexamname": "FIRST SEMESTER"}]}
    """
    data = load_json(raw_data)
    if not data or str(data.get("error_code")) != "0":
        return []

    exams = data.get("data") or []
    semesters = []
    for exam in exams:
        exam_id = exam.get("fexamno") or exam.get("FEXAMNO")
        exam_name = exam.get("fexamname") or exam.get("FEXAMNAME") or exam_id
        if exam_id:
            semesters.append({
                "id": str(exam_id),
                "name": str(exam_name)
            })
    return semesters

def parse_results(raw_data):
    """
    Parse the portal's result response.
    Expected format matches:
    {"studDet": {...}, "body": [...], "error_code": 0, "ecredits": "..."}
    """
    data = load_json(raw_data)
    if not data:
        return None

    if str(data.get("error_code")) != "0":
        return {"error": data.get("msg") or "Failed to retrieve results."}

    stud_det = data.get("studDet") or {}
    body = data.get("body") or []
    dates = data.get("dates") or {}
    footer_remarks = data.get("footerRemarks") or {}

    # Parse subjects list
    subjects = []
    for row in body:
        if not isinstance(row, dict):
            continue
        subjects.append({
            "sl_no": row.get("sl_no", ""),
            "name": row.get("subject", "Unknown Course"),
            "credits": row.get("FCREDITS", "-"),
            "grade": row.get("FGRADE", "-"),
            "grade_points": row.get("FGP", "-"),
            "credit_points": row.get("FCP", "-"),
            "remarks": row.get("remarks1") or row.get("remarks") or "-",
        })

    # Get SGPA and Class from first body item if available
    first_item = body[0] if body else {}
    sgpa = first_item.get("FSGPA", "N/A")
    result_class = first_item.get("result") or first_item.get("FCLASS") or "N/A"

    # Clean ecredits string (e.g. " Credits Earned </b>: 19" -> "Credits Earned: 19")
    raw_ecredits = data.get("ecredits", "")
    clean_credits = (
        raw_ecredits.replace("</b>", "")
        .replace("<b>", "")
        .strip()
    ) if raw_ecredits else ""

    # Clean up scroll text if present
    scroll_txt = dates.get("scroll_txt", "")
    clean_scroll = (
        scroll_txt.replace("</b>", "")
        .replace("<b>", "")
        .replace("<br>", "\n")
        .replace("<br/>", "\n")
        .strip()
    ) if scroll_txt else ""

    return {
        "student_name": stud_det.get("FNAME", "N/A"),
        "register_number": stud_det.get("FREGNO") or stud_det.get("fregno") or "N/A",
        "programme": stud_det.get("FDESCPN") or stud_det.get("FDEGREE") or "N/A",
        "college": stud_det.get("FCOLLNAME") or stud_det.get("FCOLLCODE") or "N/A",
        "exam_date": stud_det.get("FRESEXAMDATE", "N/A"),
        "announced_date": dates.get("accDate", ""),
        "scroll_text": clean_scroll,
        "footer_remarks": footer_remarks.get("FRESULT_REMARKS", ""),
        "subjects": subjects,
        "sgpa": sgpa,
        "credits_earned": clean_credits,
        "result_status": result_class,
    }

def format_result_message(result_data):
    """
    Format parsed result data as HTML for Telegram.
    """
    if not result_data:
        return "Could not retrieve or parse the results."

    if "error" in result_data:
        return f"⚠️ <b>Error:</b> {result_data['error']}"

    # Header section
    lines = [
        "📋 <b>EXAMINATION RESULT</b>",
        f"👤 <b>Name</b>: {_h(result_data.get('student_name', 'N/A'))}",
        f"🪪 <b>USN</b>: <code>{_h(result_data.get('register_number', 'N/A'))}</code>",
        f"🎓 <b>Prog</b>: {_h(result_data.get('programme', 'N/A'))}",
        f"🏫 <b>Coll</b>: {_h(result_data.get('college', 'N/A'))}",
        f"🗓 <b>Exam Date</b>: {_h(result_data.get('exam_date', 'N/A'))}",
    ]

    if result_data.get("announced_date"):
        lines.append(f"📢 <b>Announced</b>: {_h(result_data['announced_date'])}")

    lines.append("")
    lines.append("<b>📚 Course Results:</b>")

    subjects = result_data.get("subjects") or []
    for subject in subjects:
        sl = subject.get("sl_no", "")
        prefix = f"{sl}. " if sl else ""
        name = _h(subject.get("name", "Unknown Course"))
        credits = subject.get("credits", "-")
        grade = subject.get("grade", "-")
        gp = subject.get("grade_points", "-")
        cp = subject.get("credit_points", "-")
        remarks = _h(subject.get("remarks", "-"))

        lines.append(
            f"  <b>{prefix}{name}</b>\n"
            f"   Credits: <code>{credits}</code> | Grade: <code>{grade}</code> (GP: {gp}, CP: {cp}) | {remarks}"
        )

    lines.append("")
    lines.append(f"⭐ <b>SGPA</b>: <b>{result_data.get('sgpa', 'N/A')}</b>")
    if result_data.get("credits_earned"):
        lines.append(f"💳 <b>{_h(result_data['credits_earned'])}</b>")
    lines.append(f"✅ <b>Status</b>: {_h(result_data.get('result_status', 'N/A'))}")

    if result_data.get("scroll_text"):
        lines.extend(["", f"ℹ️ <b>Info</b>:\n{_h(result_data['scroll_text'])}"])

    message = "\n".join(lines)
    if len(message) > 4000:
        return message[:3900] + "\n\n(Result truncated for Telegram)"
    return message

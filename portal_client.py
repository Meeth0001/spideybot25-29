import requests
import logging
import json
from config import (
    DEFAULT_HEADERS,
    PORTAL_LOGIN_URL,
    PORTAL_PROFILE_URL,
    PORTAL_SEMESTERS_URL,
    PORTAL_RESULTS_URL,
)

logger = logging.getLogger(__name__)

class PortalClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.is_authenticated = False
        self.regno = None
        self.profile_text = None

    @staticmethod
    def _extract_json(raw_text):
        if not raw_text:
            return None
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start != -1 and end != -1 and end > start:
            raw_text = raw_text[start : end + 1]
        try:
            return json.loads(raw_text)
        except ValueError:
            return None

    def _get_text(self, label, url, timeout=30):
        logger.info(f"Fetching {label} URL: {url}")
        response = self.session.get(url, timeout=timeout)
        response.raise_for_status()
        data = self._extract_json(response.text)
        if data:
            logger.info(
                "%s response: status=%s bytes=%s error_code=%s keys=%s",
                label,
                response.status_code,
                len(response.text),
                data.get("error_code"),
                ",".join(data.keys()),
            )
            if str(data.get("error_code")) == "1" or label in ("exam_list", "result_getResDet", "result_getResults"):
                logger.info(f"Full response body for {label}: {response.text}")
        else:
            logger.info(
                "%s response: status=%s bytes=%s non_json",
                label,
                response.status_code,
                len(response.text),
            )
        return response.text

    def _post_text(self, label, url, data=None, timeout=30):
        response = self.session.post(url, data=data, timeout=timeout)
        response.raise_for_status()
        parsed = self._extract_json(response.text)
        if parsed:
            logger.info(
                "%s response: status=%s bytes=%s error_code=%s keys=%s",
                label,
                response.status_code,
                len(response.text),
                parsed.get("error_code"),
                ",".join(parsed.keys()),
            )
        return response.text

    def login(self, mobile, password):
        """
        Authenticates with the student portal.
        """
        self.regno = mobile
        payload = {
            "regno": mobile,
            "passwd": password
        }
        
        try:
            response_text = self._post_text("login", PORTAL_LOGIN_URL, data=payload, timeout=30)
            
            # The portal's signin.php returns JSON like {"error_code": 0, "msg": "..."}
            data = self._extract_json(response_text)
            if data and str(data.get("error_code")) != "0":
                logger.error(f"Login failed: {data.get('msg')}")
                self.is_authenticated = False
                return False

            if not data and "Invalid credentials" in response_text:
                self.is_authenticated = False
                return False

            profile_text = self._post_text("profile", PORTAL_PROFILE_URL, timeout=30)
            self.profile_text = profile_text  # save for result fallback
            logger.info("FULL PROFILE RESPONSE: %s", profile_text)
            profile = self._extract_json(profile_text)
            
            if profile:
                # Extract real university register number from profile
                real_regno = profile.get("strRegno") or profile.get("fregno") or profile.get("FREGNO")
                if real_regno:
                    self.regno = str(real_regno)
                    logger.info("Extracted real regno from profile: %s", self.regno)

                if profile.get("status") == "success":
                    self.is_authenticated = True
                    return True

            logger.warning("Profile check did not confirm session; continuing because signin did not fail.")
            self.is_authenticated = True
            return True
            
        except requests.RequestException as e:
            logger.error(f"Login failed: {e}")
            self.is_authenticated = False
            return False

    def get_semesters(self):
        """
        Fetches all available exams/semesters for the authenticated user.
        Queries both old and new endpoints with the register number.
        """
        if not self.is_authenticated:
            raise PermissionError("Session is not authenticated.")

        real_regno = self.regno
        all_exams = {}  # examno -> {id, name}

        # Use New Semesters Endpoint
        try:
            base_url = PORTAL_SEMESTERS_URL.split("?a=")[0]
            url = f"{base_url}?a=getExamno&regno={real_regno}"
            resp = self._get_text("exam_list", url, timeout=20)
            exams = self._extract_exams_from_response(resp)
            for ex in exams:
                all_exams[ex["id"]] = ex
        except Exception as e:
            logger.error(f"Failed fetching semesters: {e}")

        if all_exams:
            data = [{"fexamno": ex["id"], "fexamname": ex["name"]} for ex in all_exams.values()]
            return json.dumps({"error_code": 0, "data": data})

        # Fallback to synthesising from profile
        if self.profile_text:
            profile = self._extract_json(self.profile_text)
            if profile:
                examno = profile.get("fexamno") or profile.get("FEXAMNO") or profile.get("strExamno") or "CURRENT"
                examname = profile.get("fexamname") or profile.get("FEXAMNAME") or profile.get("strSemester") or "Current Semester"
                return json.dumps({
                    "error_code": 0,
                    "data": [{"fexamno": str(examno), "fexamname": str(examname)}]
                })

        return None

    def _extract_exams_from_response(self, raw_text):
        data = self._extract_json(raw_text)
        if not data:
            return []
        inner = data.get("data") or data.get("exams") or data.get("examList") or []
        if not isinstance(inner, list):
            inner = [inner] if inner else []

        exams = []
        for row in inner:
            if not isinstance(row, dict):
                continue
            examno = row.get("fexamno") or row.get("FEXAMNO") or row.get("examno") or row.get("EXAMNO")
            examname = row.get("fexamname") or row.get("FEXAMNAME") or row.get("examname") or row.get("EXAMNAME") or examno
            if examno:
                exams.append({"id": str(examno), "name": str(examname)})
        return exams

    def _has_result_data(self, raw_text):
        data = self._extract_json(raw_text)
        if not data:
            return False
        return "studDet" in data or "body" in data or str(data.get("error_code")) == "0"

    def _has_new_result_data(self, raw_text):
        data = self._extract_json(raw_text)
        if not data or str(data.get("error_code")) != "0":
            return False
        inner = data.get("data")
        if not inner:
            return False
        if isinstance(inner, list):
            return len(inner) > 0
        return True

    def get_result(self, examno):
        """
        Fetches the result for a specific examno.
        Queries multiple endpoints and actions.
        """
        if not self.is_authenticated:
            raise PermissionError("Session is not authenticated.")

        if examno == "CURRENT":
            return self.profile_text

        real_regno = self.regno

        # Generate candidates for examno
        candidates = [examno]
        if "-" not in examno:
            import datetime
            year = datetime.datetime.now().year
            # We add typical year-semester suffixes. 
            for y in [year + 1, year, year - 1, year - 2]:
                candidates.append(f"{examno}-{y}-2")
                candidates.append(f"{examno}-{y}-1")

        # Try New Results URLs
        base_url = PORTAL_RESULTS_URL.split("?a=")[0]
        for cand_exam in candidates:
            for action in ["getResults", "getResDet"]:
                try:
                    url = f"{base_url}?a={action}&examno={cand_exam}&regno={real_regno}"
                    resp = self._get_text(f"result_{action}[{cand_exam}]", url, timeout=15)
                    if self._has_result_data(resp) or self._has_new_result_data(resp):
                        return resp
                except requests.RequestException:
                    pass

        # 4. Fallback to profile text
        if self.profile_text:
            return self.profile_text

        return None



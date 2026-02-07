import time
import re
import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, WebDriverException
from .config import FENIX_BASE_URL, BROWSER_TIMEOUT, PAGE_LOAD_TIMEOUT


class FenixBot:
    def __init__(self, username: str, password: str, headless: bool = False):
        self.username = username
        self.password = password
        self.base_url = FENIX_BASE_URL
        self.driver = None
        self.wait = None
        self.headless = headless
        self.logged_in = False
        self.capture_dir = None
        self.on_enrollment_wait = None
        
    def init_driver(self, retries=5):
        import os
        import shutil
        
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--disable-gpu")
        
        # Try to find chromedriver from environment or PATH
        chromedriver_path = None
        if os.environ.get("CHROMEDRIVER_PATH"):
            chromedriver_path = os.environ.get("CHROMEDRIVER_PATH")
        else:
            chromedriver_path = shutil.which("chromedriver")
        
        # Set chromium binary if available
        chrome_bin = os.environ.get("CHROME_BIN")
        if chrome_bin:
            chrome_options.binary_location = chrome_bin
        
        # Enable performance logging for network requests
        chrome_options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

        for attempt in range(retries):
            try:
                if chromedriver_path:
                    service = Service(chromedriver_path)
                    self.driver = webdriver.Chrome(service=service, options=chrome_options)
                else:
                    self.driver = webdriver.Chrome(options=chrome_options)
                
                self.wait = WebDriverWait(self.driver, BROWSER_TIMEOUT)
                self.driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
                return True
            except Exception as e:
                if attempt == retries - 1:
                    raise Exception(f"Failed to initialize browser: {e}")
                time.sleep(2)
        return False

    def start_capture(self):
        try:
            base = Path(os.environ.get("FENIX_PROJECT_ROOT", Path.cwd()))
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            capture = base / "logs" / f"enrollment_{ts}"
            capture.mkdir(parents=True, exist_ok=True)
            self.capture_dir = capture
        except Exception:
            self.capture_dir = None

    def _save_page(self, label: str):
        if not self.capture_dir:
            return
        try:
            path = self.capture_dir / f"{label}.html"
            path.write_text(self.driver.page_source or "", encoding="utf-8")
        except Exception:
            pass

    def _save_requests(self, label: str):
        if not self.capture_dir:
            return
        try:
            logs = self.driver.get_log("performance")
            path = self.capture_dir / f"{label}.network.json"
            with path.open("w", encoding="utf-8") as f:
                json.dump(logs, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def close(self):
        try:
            if self.driver:
                self.driver.quit()
        except Exception:
            pass
        self.driver = None
        self.wait = None
        self.logged_in = False

    def ensure_single_window(self):
        try:
            handles = self.driver.window_handles
            if handles:
                # Keep the first window, close the rest
                for h in handles[1:]:
                    self.driver.switch_to.window(h)
                    self.driver.close()
                self.driver.switch_to.window(handles[0])
        except Exception:
            pass
        
    def login(self, max_retries=5) -> bool:
        if not self.driver:
            self.init_driver()
        
        for attempt in range(max_retries):
            try:
                # Check if driver is still valid
                try:
                    _ = self.driver.window_handles
                except Exception:
                    return False  # Browser was closed

                self.ensure_single_window()
                
                self.driver.get(self.base_url)
                time.sleep(2)
                
                username_field = self.wait.until(
                    EC.presence_of_element_located((By.ID, "username"))
                )
                username_field.clear()
                username_field.send_keys(self.username)
                
                password_field = self.driver.find_element(By.ID, "password")
                password_field.clear()
                password_field.send_keys(self.password)
                
                button_selectors = [
                    (By.NAME, "submit"),
                    (By.XPATH, "//button[@type='submit']"),
                    (By.CSS_SELECTOR, "button[type='submit']"),
                    (By.XPATH, "//input[@type='submit']"),
                ]
                
                login_button = None
                for selector_type, selector_value in button_selectors:
                    try:
                        login_button = self.driver.find_element(selector_type, selector_value)
                        if login_button and login_button.is_displayed():
                            break
                    except:
                        continue
                
                if login_button:
                    login_button.click()
                else:
                    password_field.send_keys(Keys.RETURN)
                
                # Wait for either a successful login or an error state
                max_wait = 10
                for _ in range(max_wait):
                    time.sleep(1)
                    
                    # Check if browser is still open
                    try:
                        _ = self.driver.window_handles
                    except Exception:
                        return False
                    
                    page_source = self.driver.page_source.lower()
                    current_url = (self.driver.current_url or "").lower()

                    # Check for successful login (presence of logout links or redirect away from login page)
                    if any(kw in page_source for kw in ["logout", "sair", "estudante", "aluno", "student"]):
                        self.logged_in = True
                        return True
                    if "login" not in current_url and "cas" not in current_url:
                        # If not on login page and no login fields, assume success
                        try:
                            if not self.driver.find_elements(By.ID, "username"):
                                self.logged_in = True
                                return True
                        except:
                            self.logged_in = True
                            return True
                    # If we're on fenix login.do but no login fields are present, assume already logged in
                    if "login.do" in current_url:
                        try:
                            has_user = bool(self.driver.find_elements(By.ID, "username"))
                            has_pass = bool(self.driver.find_elements(By.ID, "password"))
                            if not has_user and not has_pass:
                                self.logged_in = True
                                return True
                        except Exception:
                            self.logged_in = True
                            return True

                    # Check for error messages indicating wrong credentials
                    error_keywords = ["credenciais inválidas", "invalid credentials", "acesso negado", "access denied",
                                      "utilizador não encontrado", "user not found", "username ou password incorretos",
                                      "erro", "error"]
                    try:
                        error_elements = self.driver.find_elements(
                            By.XPATH,
                            "//*[contains(text(), 'credenciais') or contains(text(), 'inválid') or contains(text(), 'invalid') or contains(text(), 'password') or contains(text(), 'erro')]"
                        )
                        if error_elements:
                            return False
                    except:
                        pass

                    if any(kw in page_source for kw in error_keywords):
                        return False

                # If still on login page after waiting, retry
                if attempt < max_retries - 1:
                    time.sleep(2)
                    try:
                        self.driver.refresh()
                    except:
                        return False
                continue
                    
            except TimeoutException:
                if attempt < max_retries - 1:
                    time.sleep(3)
                    try:
                        self.driver.refresh()
                    except:
                        return False
                continue
            except WebDriverException:
                return False  # Browser was closed or crashed
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(3)
                continue
        
        return False

    def check_logged_in(self, url: str = None) -> bool:
        if not self.driver:
            return False
        try:
            self.ensure_single_window()
            target = url or f"{self.base_url}/messaging/news/cms-news"
            self.driver.get(target)
            time.sleep(2)

            current_url = (self.driver.current_url or "").lower()
            page_source = (self.driver.page_source or "").lower()

            if "login" in current_url or "cas" in current_url:
                # If on login.do but no login fields, treat as already logged in
                if "login.do" in current_url:
                    try:
                        if not self.driver.find_elements(By.ID, "username") and not self.driver.find_elements(By.ID, "password"):
                            self.logged_in = True
                            return True
                    except Exception:
                        self.logged_in = True
                        return True
                return False
            if self.driver.find_elements(By.ID, "username"):
                return False

            if any(kw in page_source for kw in ["logout", "sair", "student", "estudante", "aluno"]):
                self.logged_in = True
                return True

            # Fallback: not on login page and no username field
            self.logged_in = True
            return True
        except Exception:
            return False
    
    def navigate_to_enrollments(self, max_retries=5) -> bool:
        for attempt in range(max_retries):
            try:
                self.ensure_single_window()
                self.driver.get(f"{self.base_url}/student/enroll/shift-enrollment")
                time.sleep(2)

                self._save_page("shift_enrollment_landing")
                self._save_requests("shift_enrollment_landing")

                # If enrollment is closed, wait until it opens
                if not self._wait_if_enrollment_closed():
                    return False

                self._save_page("shift_enrollment_after_wait")
                self._save_requests("shift_enrollment_after_wait")

                # If a "Continue" form exists, submit it
                if self._submit_continue_if_present():
                    time.sleep(2)

                # Check again after continue and any redirects
                if not self._wait_if_enrollment_closed():
                    return False

                self._save_page("shift_enrollment_after_continue")
                self._save_requests("shift_enrollment_after_continue")

                return True
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(3)
                continue
        
        return False

    def _is_enrollment_closed(self) -> bool:
        try:
            page_source = (self.driver.page_source or "").lower()
            return "enrollment period closed" in page_source or "período de inscrições fechado" in page_source
        except Exception:
            return False

    def _get_enrollment_start_datetime(self):
        try:
            page_source = self.driver.page_source or ""
            match = re.search(
                r"(?:Enrollment period closed|Período de inscrições fechado|Periodo de inscricoes fechado):\s*"
                r"(\d{2}/\d{2}/\d{4})\s*(\d{2}:\d{2})\s*-\s*"
                r"(\d{2}/\d{2}/\d{4})\s*(\d{2}:\d{2})",
                page_source,
                flags=re.IGNORECASE
            )
            if match:
                start_date = match.group(1)
                start_time = match.group(2)
                return datetime.strptime(f"{start_date} {start_time}", "%d/%m/%Y %H:%M")
            return None
        except Exception:
            return None

    def _get_enrollment_window_datetimes(self):
        try:
            page_source = self.driver.page_source or ""
            match = re.search(
                r"(?:Enrollment period closed|Período de inscrições fechado|Periodo de inscricoes fechado):\s*"
                r"(\d{2}/\d{2}/\d{4})\s*(\d{2}:\d{2})\s*-\s*"
                r"(\d{2}/\d{2}/\d{4})\s*(\d{2}:\d{2})",
                page_source,
                flags=re.IGNORECASE
            )
            if match:
                start_date, start_time, end_date, end_time = match.groups()
                start_dt = datetime.strptime(f"{start_date} {start_time}", "%d/%m/%Y %H:%M")
                end_dt = datetime.strptime(f"{end_date} {end_time}", "%d/%m/%Y %H:%M")
                return start_dt, end_dt
            return None, None
        except Exception:
            return None, None

    def _wait_if_enrollment_closed(self) -> bool:
        try:
            if not self._is_enrollment_closed():
                return True

            start_dt, _end_dt = self._get_enrollment_window_datetimes()
            notify = self.on_enrollment_wait if callable(self.on_enrollment_wait) else None
            if notify:
                try:
                    notify(start_dt, self._get_enrollment_window_text())
                except Exception:
                    pass

            # If start is in the future, wait until the start time
            if start_dt and datetime.now() < start_dt:
                while datetime.now() < start_dt:
                    time.sleep(min(30, max(1, int((start_dt - datetime.now()).total_seconds()))))

            # After the start time (or if start time already passed), keep checking for opening
            if start_dt:
                max_wait_seconds = 10 * 60
                deadline = datetime.now() + timedelta(seconds=max_wait_seconds)
                while datetime.now() < deadline:
                    self.driver.refresh()
                    time.sleep(2)
                    if not self._is_enrollment_closed():
                        return True
                    time.sleep(30)
                return False

            # Closed but no parsable start time
            return False
        except Exception:
            return False

    def _get_enrollment_window_text(self):
        try:
            page_source = self.driver.page_source or ""
            match = re.search(
                r"(?:Enrollment period closed|Período de inscrições fechado|Periodo de inscricoes fechado):\s*"
                r"(\d{2}/\d{2}/\d{4})\s*(\d{2}:\d{2})\s*-\s*"
                r"(\d{2}/\d{2}/\d{4})\s*(\d{2}:\d{2})"
                r"(?:\s*\(([^)]+)\))?",
                page_source,
                flags=re.IGNORECASE
            )
            if not match:
                return None
            start_date, start_time, end_date, end_time, term = match.groups()
            term_txt = f" ({term})" if term else ""
            return f"Enrollment period closed: {start_date} {start_time} - {end_date} {end_time}{term_txt}"
        except Exception:
            return None

    def _submit_continue_if_present(self) -> bool:
        try:
            form = self.driver.find_elements(By.XPATH, "//form[@action='/student/studentShiftEnrollmentManager.do']")
            if not form:
                return False
            continue_btns = self.driver.find_elements(By.XPATH, "//input[@type='submit' and (contains(@value,'Continue') or contains(@value,'Continuar'))]")
            if continue_btns:
                continue_btns[0].click()
                return True
            # fallback: submit the form via JS
            self.driver.execute_script("arguments[0].submit();", form[0])
            return True
        except Exception:
            return False
    
    def find_and_enroll_shift(self, course_name: str, shift_type: str, shift_name: str = "", max_retries=5,
                              retry_window_seconds: int = 900, retry_interval_seconds: int = 20) -> bool:
        deadline = datetime.now() + timedelta(seconds=max(0, retry_window_seconds))
        last_enroll_url = ""

        def try_enroll_from_links(links) -> bool:
            nonlocal last_enroll_url
            for link in links:
                try:
                    href = link.get_attribute("href") or ""
                    text = link.text.lower()

                    if "enrollStudentInShifts" not in href:
                        continue

                    if shift_name:
                        if shift_name.lower() not in (text + " " + href):
                            continue
                    else:
                        if course_name.lower() not in text or shift_type.lower() not in text:
                            continue

                    last_enroll_url = href
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", link)
                    time.sleep(1)
                    link.click()
                    time.sleep(3)

                    self._save_page("enroll_after_click")
                    self._save_requests("enroll_after_click")

                    try:
                        confirm = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Confirmar')]")
                        confirm.click()
                        time.sleep(2)
                    except:
                        pass

                    page_source = self.driver.page_source.lower()
                    if any(kw in page_source for kw in ["sucesso", "success", "enrolled", "inscrito"]):
                        return True

                    self.driver.back()
                    time.sleep(2)
                except Exception:
                    try:
                        self.driver.back()
                    except:
                        pass
                    time.sleep(2)
            return False

        for attempt in range(max_retries):
            try:
                self._save_page("enroll_search_start")
                self._save_requests("enroll_search_start")
                links = self.driver.find_elements(By.TAG_NAME, "a")
                if try_enroll_from_links(links):
                    return True

                # Keep retrying the same enrollment page until a seat opens
                while datetime.now() < deadline:
                    time.sleep(retry_interval_seconds)
                    try:
                        if last_enroll_url:
                            self.driver.get(last_enroll_url)
                        else:
                            self.driver.refresh()
                        time.sleep(2)
                    except Exception:
                        break

                    links = self.driver.find_elements(By.TAG_NAME, "a")
                    if try_enroll_from_links(links):
                        return True
                    # Continue polling until deadline
                
                if attempt < max_retries - 1:
                    time.sleep(2)
                    self.driver.refresh()
                    
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(2)
                    try:
                        self.driver.refresh()
                    except:
                        pass
                continue
        
        return False
    
    def close(self):
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass

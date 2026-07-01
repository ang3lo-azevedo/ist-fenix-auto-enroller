import time
import re
import os
import json
import unicodedata
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

    def _find_writable_logs_dir(self) -> Path:
        """Find writable logs directory using same logic as config.json saving."""
        # Use specific markers that uniquely identify the ist-fenix-auto-enroller project
        required_markers = ["src/gui/main_window.py", "main.py"]
        optional_markers = ["flake.nix", "README.md"]
        
        def is_nix_store(path: Path) -> bool:
            try:
                return str(path).startswith("/nix/store/")
            except Exception:
                return False
        
        def is_project_root(path: Path) -> bool:
            """Check if path has the required markers for ist-fenix-auto-enroller."""
            return all((path / marker).exists() for marker in required_markers)
        
        def is_writable(path: Path) -> bool:
            try:
                if not path.exists():
                    path.mkdir(parents=True, exist_ok=True)
                test_file = path / ".write_test"
                test_file.touch()
                test_file.unlink()
                return True
            except (OSError, PermissionError):
                return False
        
        # Try FENIX_PROJECT_ROOT first
        env_root = os.environ.get("FENIX_PROJECT_ROOT")
        if env_root:
            root_path = Path(env_root).resolve()
            if root_path.exists() and not is_nix_store(root_path) and is_project_root(root_path):
                logs_path = root_path / "logs"
                if is_writable(logs_path):
                    return logs_path
        
        # Try PWD and cwd
        candidates = []
        env_pwd = os.environ.get("PWD")
        if env_pwd:
            candidates.append(Path(env_pwd).resolve())
        candidates.append(Path.cwd().resolve())
        
        for base in candidates:
            if is_nix_store(base):
                continue
            # Walk up to find project root
            for parent in [base, *base.parents]:
                if is_project_root(parent):
                    logs_path = parent / "logs"
                    if is_writable(logs_path):
                        return logs_path
        
        # Last resort: search in home directory for project
        home = Path.home()
        
        for root, dirs, files in os.walk(home):
            root_path = Path(root)
            
            if is_nix_store(root_path):
                dirs[:] = []
                continue
            
            dirs[:] = [
                d for d in dirs
                if not d.startswith(".") and d not in {".git", "node_modules", "__pycache__"}
            ]
            
            if is_project_root(root_path):
                logs_path = root_path / "logs"
                if is_writable(logs_path):
                    return logs_path
        
        return None
    
    def start_capture(self):
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Find writable logs directory using same logic as config.json
            logs_dir = self._find_writable_logs_dir()
            if logs_dir:
                capture = logs_dir / f"enrollment_{ts}"
                capture.mkdir(parents=True, exist_ok=True)
                self.capture_dir = capture
                print(f"[CAPTURE] Recording session started: {self.capture_dir}")
            else:
                # Fallback to /tmp if no writable logs directory found
                import tempfile
                capture = Path(tempfile.mkdtemp(prefix=f"fenix_enrollment_{ts}_"))
                self.capture_dir = capture
                print(f"[CAPTURE] Using temp directory (no writable logs found): {self.capture_dir}")
        except Exception as e:
            print(f"[CAPTURE] ERROR: Failed to start capture: {e}")
            self.capture_dir = None

    def _save_page(self, label: str):
        if not self.capture_dir:
            return
        try:
            path = self.capture_dir / f"{label}.html"
            path.write_text(self.driver.page_source or "", encoding="utf-8")
            print(f"[CAPTURE] Saved page: {label}.html")
        except Exception as e:
            print(f"[CAPTURE] ERROR saving page {label}: {e}")

    def _save_requests(self, label: str):
        if not self.capture_dir:
            return
        try:
            logs = self.driver.get_log("performance")
            path = self.capture_dir / f"{label}.network.json"
            with path.open("w", encoding="utf-8") as f:
                json.dump(logs, f, ensure_ascii=False, indent=2)
            print(f"[CAPTURE] Saved network log: {label}.network.json ({len(logs)} entries)")
        except Exception as e:
            print(f"[CAPTURE] ERROR saving network log {label}: {e}")

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
                # First navigate to the enrollment landing page
                self.driver.get(f"{self.base_url}/student/enroll/shift-enrollment")
                time.sleep(2)

                self._save_page("shift_enrollment_landing")
                self._save_requests("shift_enrollment_landing")

                # Click the Continue button to proceed to enrollment manager
                if self._submit_continue_if_present():
                    time.sleep(2)

                self._save_page("shift_enrollment_after_continue")
                self._save_requests("shift_enrollment_after_continue")

                return True
            except Exception as e:
                print(f"[BOT] Error navigating to enrollments (attempt {attempt + 1}): {e}")
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
            # First, try to find "Continue" or "Continuar" link/button
            # Check for link with text "Continue" or "Continuar"
            try:
                continue_link = self.driver.find_element(By.XPATH, 
                    "//a[contains(text(), 'Continue') or contains(text(), 'Continuar')]")
                print(f"[BOT] Found Continue link, clicking...")
                continue_link.click()
                time.sleep(2)
                return True
            except:
                pass
            
            # Try form-based continue
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
        except Exception as e:
            print(f"[BOT] No continue button/link found: {e}")
            return False
    
    def navigate_to_course_enrollment(self, course_name: str, max_retries=3) -> bool:
        """Navigate to the specific course's enrollment page from the main enrollment page."""
        for attempt in range(max_retries):
            try:
                print(f"[BOT] Searching for course: {course_name}")

                # Look for course name in the page
                page_source = self.driver.page_source.lower()
                course_lower = course_name.lower()

                # Primary path: on the enrollment manager the "Book" links have the
                # generic text "Book" (href=proceedToShiftEnrolment) and the course
                # name lives in a sibling cell of the SAME table row. Locate the row
                # by the course name, then click the Book link inside that row.
                normalized_course = self._normalize_text(course_name)
                cells = self.driver.find_elements(By.XPATH, "//td | //th")
                for cell in cells:
                    try:
                        cell_text = cell.text or ""
                        if not cell_text.strip():
                            continue
                        if course_lower in cell_text.lower() or normalized_course in self._normalize_text(cell_text):
                            row = cell.find_element(By.XPATH, "./ancestor::tr[1]")
                            book_links = row.find_elements(
                                By.XPATH, ".//a[contains(@href, 'proceedToShiftEnrolment')]"
                            )
                            if book_links:
                                print(f"[BOT] Found Book link for {course_name} in course row")
                                self.driver.execute_script("arguments[0].scrollIntoView(true);", book_links[0])
                                time.sleep(0.5)
                                book_links[0].click()
                                time.sleep(2)
                                print(f"[BOT] Navigated to course enrollment page for {course_name}")
                                return True
                    except:
                        continue

                # Try to find a link containing the course name
                # These could be in forms, links, or table cells
                all_links = self.driver.find_elements(By.TAG_NAME, "a")
                
                for link in all_links:
                    try:
                        link_text = (link.text or "").lower()
                        href = link.get_attribute("href") or ""
                        
                        # Check if this link is related to our course
                        # Match course name or course code
                        if course_lower in link_text or course_lower in href.lower():
                            # Also check if it's a navigation link (not just informational)
                            if "proceedToShiftEnrolment" in href or "executionCourse" in href:
                                print(f"[BOT] Found course link: {link_text[:50]}")
                                self.driver.execute_script("arguments[0].scrollIntoView(true);", link)
                                time.sleep(0.5)
                                link.click()
                                time.sleep(2)
                                print(f"[BOT] Navigated to course enrollment page for {course_name}")
                                return True
                        
                        # Also try matching without accents or special chars
                        # (e.g., "Producao" matches "Produção")
                        import unicodedata
                        def normalize(s):
                            return ''.join(c for c in unicodedata.normalize('NFD', s) 
                                         if unicodedata.category(c) != 'Mn').lower()
                        
                        if normalize(course_name) in normalize(link_text):
                            if "proceedToShiftEnrolment" in href or "executionCourse" in href:
                                print(f"[BOT] Found course link (normalized match): {link_text[:50]}")
                                self.driver.execute_script("arguments[0].scrollIntoView(true);", link)
                                time.sleep(0.5)
                                link.click()
                                time.sleep(2)
                                print(f"[BOT] Navigated to course enrollment page for {course_name}")
                                return True
                    except:
                        continue
                
                # If not found, try looking in headers or other text elements
                headers = self.driver.find_elements(By.XPATH, "//h2 | //h3 | //h4 | //td[@class='disciplina']")
                for header in headers:
                    try:
                        header_text = (header.text or "").lower()
                        if course_lower in header_text:
                            # Found the course, now look for nearby enrollment links
                            parent = header.find_element(By.XPATH, "..//..")
                            nearby_links = parent.find_elements(By.TAG_NAME, "a")
                            for link in nearby_links:
                                href = link.get_attribute("href") or ""
                                if "proceedToShiftEnrolment" in href or "executionCourse" in href:
                                    print(f"[BOT] Found nearby enrollment link for {course_name}")
                                    link.click()
                                    time.sleep(2)
                                    return True
                    except:
                        continue
                
                print(f"[BOT] Course {course_name} not found on this page (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(1)
                    self.driver.refresh()
                    time.sleep(2)
                    
            except Exception as e:
                print(f"[BOT] Error navigating to course enrollment: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                continue
        
        return False

    def _extract_shift_enrollment_urls(self, shift_name: str = "", shift_type: str = "") -> list:
        """Extract all enrollStudentInShifts URLs from current page and match by shift name/type."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            enrollment_links = []
            
            # Find all links with enrollStudentInShifts
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                if 'enrollStudentInShifts' in href:
                    # Get the parent context to extract shift info
                    parent_text = ""
                    parent = link.parent
                    for _ in range(5):
                        if parent:
                            parent_text += " " + parent.get_text(strip=True)
                            parent = parent.parent
                        else:
                            break
                    
                    parent_text = parent_text.lower()
                    
                    # Try to extract shiftId from URL for better matching
                    shift_id_match = re.search(r'shiftId=(\d+)', href)
                    shift_id = shift_id_match.group(1) if shift_id_match else None
                    
                    enrollment_links.append({
                        'url': href if href.startswith('http') else f"{self.base_url}{href}",
                        'shiftId': shift_id,
                        'context': parent_text,
                        'link_text': link.get_text(strip=True).lower()
                    })
            
            print(f"[BOT] Found {len(enrollment_links)} enrollment URLs on page")
            
            # Filter by shift name or type
            if shift_name:
                # Try different variations of the shift name
                search_names = [
                    shift_name.lower(),
                    shift_name.lower().replace(" ", ""),
                    shift_name.split("(")[0].strip().lower(),
                ]
                
                matched = []
                for link_info in enrollment_links:
                    context = link_info['context'] + " " + link_info['link_text']
                    if any(name in context for name in search_names):
                        matched.append(link_info)
                
                if matched:
                    print(f"[BOT] Matched {len(matched)} URLs for shift '{shift_name}'")
                    return matched
            
            if shift_type:
                shift_type_lower = shift_type.lower()
                matched = [link for link in enrollment_links 
                          if shift_type_lower in link['context'] or shift_type_lower in link['link_text']]
                if matched:
                    print(f"[BOT] Matched {len(matched)} URLs for type '{shift_type}'")
                    return matched
            
            return enrollment_links
            
        except Exception as e:
            print(f"[BOT] Error extracting enrollment URLs: {e}")
            return []

    def _extract_common_enrollment_params(self):
        """Extract common enrollment parameters that are the same for all shifts."""
        try:
            from bs4 import BeautifulSoup
            from urllib.parse import urlparse, parse_qs
            
            if hasattr(self, '_cached_enrollment_params'):
                return self._cached_enrollment_params
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # Find any enrollment or shift management link
            sample_link = soup.find('a', href=lambda x: x and ('enrollStudentInShifts' in x or 'shiftId=' in x or 'removeStudentFromShifts' in x))
            if not sample_link:
                print(f"[BOT] No enrollment link found to extract common parameters")
                return None
            
            sample_url = sample_link.get('href')
            if not sample_url.startswith('http'):
                sample_url = f"{self.base_url}{sample_url}"
            
            parsed = urlparse(sample_url)
            params = parse_qs(parsed.query)
            
            common_params = {
                'registrationOID': params.get('registrationOID', [None])[0],
                'executionSemesterID': params.get('executionSemesterID', [None])[0],
            }
            
            if not common_params['registrationOID'] or not common_params['executionSemesterID']:
                print(f"[BOT] Could not extract required common parameters")
                return None
            
            print(f"[BOT] Extracted common parameters: {common_params}")
            self._cached_enrollment_params = common_params
            return common_params
            
        except Exception as e:
            print(f"[BOT] Error extracting common enrollment params: {e}")
            return None

    def _try_construct_enrollment_url(self, course_name: str, shift_name: str = "", shift_type: str = "") -> str:
        """Try to construct an enrollment URL by finding the shift link and extracting its parameters."""
        try:
            from bs4 import BeautifulSoup
            from urllib.parse import urlparse, parse_qs
            
            # Get common parameters (cached)
            common_params = self._extract_common_enrollment_params()
            if not common_params:
                return None
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # Find the specific shift link by matching shift name
            if shift_name:
                print(f"[BOT] Searching for shift {shift_name} in page...")
                
                for link in soup.find_all('a', href=lambda x: x and ('shiftId=' in x or 'enrollStudentInShifts' in x)):
                    link_text = link.get_text(strip=True).lower()
                    parent_text = ""
                    parent = link.parent
                    for _ in range(5):
                        if parent:
                            parent_text += " " + parent.get_text(strip=True).lower()
                            parent = parent.parent
                    
                    # Check if this link is for our shift
                    search_names = [
                        shift_name.lower(),
                        shift_name.lower().replace(" ", ""),
                        shift_name.split("(")[0].strip().lower(),
                    ]
                    
                    full_context = (link_text + " " + parent_text).lower()
                    if any(name in full_context for name in search_names):
                        href = link.get('href')
                        if not href.startswith('http'):
                            href = f"{self.base_url}{href}"
                        
                        parsed = urlparse(href)
                        params = parse_qs(parsed.query)
                        
                        shift_id = params.get('shiftId', [None])[0]
                        class_id = params.get('classId', [None])[0]
                        execution_course_id = params.get('executionCourseID', [None])[0]
                        checksum = params.get('_request_checksum_', [None])[0]
                        
                        if shift_id and checksum:
                            # Construct the enrollment URL with all parameters
                            url = (f"{self.base_url}/student/enrollStudentInShifts.do?"
                                  f"registrationOID={common_params['registrationOID']}&"
                                  f"shiftId={shift_id}&"
                                  f"classId={class_id or ''}&"
                                  f"executionCourseID={execution_course_id or ''}&"
                                  f"executionSemesterID={common_params['executionSemesterID']}&"
                                  f"weekStart=null&weekEnd=null&"
                                  f"_request_checksum_={checksum}")
                            
                            print(f"[BOT] Constructed enrollment URL for {shift_name}: shiftId={shift_id}")
                            return url
            
            return None
            
        except Exception as e:
            print(f"[BOT] Error constructing enrollment URL: {e}")
            return None

    def find_and_enroll_shift(self, course_name: str, shift_type: str, shift_name: str = "", max_retries=5,
                              retry_window_seconds: int = 900, retry_interval_seconds: int = 20, dry_run: bool = False) -> bool:
        deadline = datetime.now() + timedelta(seconds=max(0, retry_window_seconds))
        last_enroll_url = ""
        enrolled_successfully = False

        try:
            # Normalize shift type for display matching (T, L, TP, etc.)
            shift_type_display = shift_type.replace("TEORICO_PRATICA", "TP").replace("TEORICA", "T").replace("LABORATORIAL", "L")
            if len(shift_type) > 2:
                shift_type_display = shift_type_display.upper()

            def is_shift_already_enrolled() -> bool:
                """Check if this specific shift is already booked.

                Fenix marks a booked shift with a cancel control
                ("Cancel Booking" -> unEnroleStudentFromShift) rendered in the
                same row/block as the shift code. We only trust that control.

                We deliberately do NOT fall back to a page-wide scan for
                "reserved"/"enrolled" text: those words are always present as
                column labels on the enrollment manager page, so combined with a
                loose substring match on the shift code they produce false
                positives that make the bot skip shifts it never actually booked
                and report false success.
                """
                try:
                    cancel_links = self.driver.find_elements(
                        By.XPATH,
                        "//a[contains(@href, 'unEnroleStudentFromShift') or "
                        "contains(@href, 'removeStudentFromShifts') or "
                        "contains(text(), 'Cancel') or contains(text(), 'Cancelar')]"
                    )
                    for cancel_link in cancel_links:
                        try:
                            block = ""
                            node = cancel_link
                            for _ in range(4):
                                node = node.find_element(By.XPATH, "..")
                                block = (block + " " + (node.text or "")).lower()

                            if shift_name:
                                if shift_name.lower() in block:
                                    print(f"[BOT] Shift {shift_name} is already booked (cancel link found). Skipping.")
                                    return True
                            elif shift_type_display.lower() in block:
                                print(f"[BOT] Shift with type {shift_type} is already booked. Skipping.")
                                return True
                        except:
                            pass
                except:
                    pass
                return False

            def try_enroll_from_urls(enrollment_urls) -> bool:
                """Try to enroll by directly navigating to enrollment URLs"""
                nonlocal last_enroll_url

                for url_info in enrollment_urls:
                    try:
                        url = url_info['url']
                        last_enroll_url = url

                        print(f"[BOT] Found enrollment URL for {shift_name or shift_type}")

                        if dry_run:
                            print(f"[DRY-RUN] Would navigate to: {url[:80]}...")
                            print(f"[DRY-RUN] Would enroll in: {shift_name or shift_type}")
                            return True

                        print(f"[BOT] Navigating to enrollment URL for {shift_name or shift_type}")
                        self.driver.get(url)
                        time.sleep(2)

                        self._save_page("enroll_after_navigation")
                        self._save_requests("enroll_after_navigation")

                        page_source = self.driver.page_source.lower()

                        try:
                            confirm = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Confirmar')] | //input[@value='Confirmar']")
                            print(f"[BOT] Clicking confirmation button")
                            confirm.click()
                            time.sleep(2)
                        except:
                            pass

                        page_source = self.driver.page_source.lower()
                        if any(kw in page_source for kw in ["sucesso", "success", "enrolled", "inscrito", "confirmada"]):
                            print(f"[BOT] Successfully enrolled in {shift_name or shift_type}")
                            return True

                        if any(kw in page_source for kw in ["erro", "error", "lotada", "full", "capacity"]):
                            print(f"[BOT] Enrollment failed (shift may be full or unavailable)")
                    except Exception as e:
                        print(f"[BOT] Error while trying enrollment URL: {e}")
                        continue

                return False

            for attempt in range(max_retries):
                try:
                    self._save_page("enroll_search_start")
                    self._save_requests("enroll_search_start")

                    if is_shift_already_enrolled():
                        return True

                    print(f"[BOT] Attempting to construct enrollment URL for {shift_name or shift_type}...")
                    constructed_url = self._try_construct_enrollment_url(course_name, shift_name, shift_type_display)

                    if constructed_url:
                        print(f"[BOT] Successfully constructed enrollment URL, trying direct enrollment...")
                        if try_enroll_from_urls([{'url': constructed_url, 'shiftId': None, 'context': '', 'link_text': ''}]):
                            enrolled_successfully = True
                            break
                        else:
                            print(f"[BOT] Direct enrollment with constructed URL failed, falling back to search...")
                    else:
                        print(f"[BOT] Could not construct URL from current page...")

                    print(f"[BOT] Navigating to course page to find shift links...")
                    if not self.navigate_to_course_enrollment(course_name):
                        print(f"[BOT] Failed to navigate to course enrollment page for {course_name}")
                        if attempt < max_retries - 1:
                            continue
                        return False

                    constructed_url = self._try_construct_enrollment_url(course_name, shift_name, shift_type_display)
                    if constructed_url:
                        print(f"[BOT] Constructed URL from course page, enrolling...")
                        if try_enroll_from_urls([{'url': constructed_url, 'shiftId': None, 'context': '', 'link_text': ''}]):
                            enrolled_successfully = True
                            break

                    enrollment_urls = self._extract_shift_enrollment_urls(shift_name, shift_type_display)

                    if not enrollment_urls:
                        print(f"[BOT] No enrollment URLs found for {shift_name or shift_type}")
                        if attempt < max_retries - 1:
                            time.sleep(2)
                            self.driver.refresh()
                            time.sleep(2)
                            continue
                        print(f"[BOT] Failed to find enrollment URL after {max_retries} attempts")
                        return False

                    if try_enroll_from_urls(enrollment_urls):
                        enrolled_successfully = True
                        break

                    while datetime.now() < deadline:
                        time.sleep(retry_interval_seconds)
                        try:
                            if last_enroll_url:
                                print(f"[BOT] Retrying enrollment URL...")
                                self.driver.get(last_enroll_url)
                            else:
                                self.driver.refresh()
                            time.sleep(2)

                            page_source = self.driver.page_source.lower()
                            if any(kw in page_source for kw in ["sucesso", "success", "enrolled", "inscrito", "confirmada"]):
                                print(f"[BOT] Successfully enrolled in {shift_name or shift_type}")
                                enrolled_successfully = True
                                break
                        except Exception:
                            break

                    if enrolled_successfully:
                        break

                    if attempt < max_retries - 1:
                        time.sleep(2)
                        self.driver.refresh()

                except Exception as e:
                    print(f"[BOT] Error during enrollment attempt {attempt + 1}: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(2)
                        try:
                            self.driver.refresh()
                        except:
                            pass
                    continue
        
        finally:
            # Always navigate back to main enrollment page for next course
            try:
                print(f"[BOT] Navigating back to main enrollment page...")
                self.driver.get(f"{self.base_url}/student/enroll/shift-enrollment")
                time.sleep(2)
                # Click continue again
                self._submit_continue_if_present()
                time.sleep(2)
            except Exception as e:
                print(f"[BOT] Error navigating back: {e}")
        
        if not enrolled_successfully:
            print(f"[BOT] Failed to enroll in {shift_name or shift_type} after {max_retries} attempts")
        
        return enrolled_successfully
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for matching (remove accents, lowercase)"""
        return ''.join(c for c in unicodedata.normalize('NFD', text) 
                      if unicodedata.category(c) != 'Mn').lower()
    
    def close(self):
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass

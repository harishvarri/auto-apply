import sys
import json
import os
import time
import datetime
import urllib.request
import urllib.parse
from playwright.sync_api import sync_playwright

# Gemini AI enabled - fallback using API key
HAS_GEMINI = True

# Module-level context for the job currently being processed, so obstacle
# questions can be logged with the right job metadata.
CURRENT_JOB = {}

PENDING_QUESTIONS_FILE = "pending_questions.json"


def _normalize_question(text):
    """Normalize a question label for dedup / keyword matching."""
    return " ".join((text or "").lower().split())[:200]


def log_pending_question(question, qtype="text", options=None, ai_answer=None):
    """Record an 'obstacle' question (one with no saved profile answer) so the
    user can provide a canonical answer in the dashboard that will be reused.

    Deduped by normalized question text; increments a seen counter. Stores the
    AI's best-guess answer (used for this submission) so the user can confirm
    or override it later.
    """
    try:
        norm = _normalize_question(question)
        if not norm or len(norm) < 3:
            return
        try:
            with open(PENDING_QUESTIONS_FILE, "r", encoding="utf-8") as f:
                pending = json.load(f)
        except Exception:
            pending = []

        # If already answered (exists in custom_keywords) skip logging
        try:
            prof = load_profile()
            for kw in (prof.get("custom_keywords", {}) or {}):
                if kw.lower() in norm or norm in kw.lower():
                    return  # user already answered this; reuse handles it
        except Exception:
            pass

        for q in pending:
            if q.get("norm") == norm:
                q["count"] = q.get("count", 1) + 1
                q["last_seen"] = datetime.date.today().isoformat()
                if ai_answer and not q.get("ai_answer"):
                    q["ai_answer"] = ai_answer
                with open(PENDING_QUESTIONS_FILE, "w", encoding="utf-8") as f:
                    json.dump(pending, f, indent=2)
                return

        pending.append({
            "id": f"q_{abs(hash(norm)) % (10**10)}",
            "question": question.strip()[:300],
            "norm": norm,
            "type": qtype,
            "options": options or [],
            "ai_answer": ai_answer or "",
            "job_title": CURRENT_JOB.get("title", ""),
            "company": CURRENT_JOB.get("company", ""),
            "url": CURRENT_JOB.get("url", ""),
            "first_seen": datetime.date.today().isoformat(),
            "last_seen": datetime.date.today().isoformat(),
            "count": 1,
            "answered": False,
        })
        with open(PENDING_QUESTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(pending, f, indent=2)
    except Exception as e:
        print(f"    [PENDING-Q ERROR] {e}")

def call_gemini_api(prompt):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("    [GEMINI AI WARNING] GEMINI_API_KEY env variable is not set. Skipping Gemini call.")
        return None
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent?key={api_key}"
    headers = {
        "Content-Type": "application/json"
    }
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 250
        }
    }
    try:
        req = urllib.request.Request(
            url, 
            data=json.dumps(payload).encode('utf-8'), 
            headers=headers, 
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            text = res_data['candidates'][0]['content']['parts'][0]['text'].strip()
            return text
    except Exception as e:
        print(f"    [GEMINI AI ERROR] Failed calling Gemini API: {e}")
        return None

def get_gemini_response(label_text, el_type, options_list, profile):
    personal = profile.get("personal", {})
    education = profile.get("education", [])
    experience = profile.get("experience", [])
    skills = profile.get("skills", {})
    custom_responses = profile.get("custom_responses", {})
    
    candidate_summary = f"""
Candidate Profile Context:
Name: {personal.get("full_name")}
Email: {personal.get("email")}
Phone: {personal.get("phone")}
Location: {personal.get("location")}
Education Details: {json.dumps(education)}
Work Experience Details: {json.dumps(experience)}
Technical Skills Details: {json.dumps(skills)}
Standard Custom Answers: {json.dumps(custom_responses)}
"""
    
    if el_type == "dropdown":
        prompt = f"""{candidate_summary}
---
We are filling out a job application. The form contains a dropdown selection field.
Question / Field Label: "{label_text}"
Available Dropdown Options: {json.dumps(options_list)}

Based on the candidate profile context, which option from the options list is the most appropriate?
Return ONLY the exact option text or value matching one of the options. Do not include any explanations, introduction, markdown code blocks, or extra text."""
    elif el_type in ["text", "textarea"]:
        prompt = f"""{candidate_summary}
---
We are filling out a job application. The form contains a text input field (type: {el_type}).
Question / Field Label: "{label_text}"

Based on the candidate profile context, write a brief, professional, and accurate response for this field.
Return ONLY the response text. Do not include any quotes, markdown blocks, introductory phrasing (like "The answer is..."), or explanations."""
    elif el_type == "checkbox":
        prompt = f"""{candidate_summary}
---
We are filling out a job application. The form contains a checkbox option.
Question / Checkbox Label: "{label_text}"

Based on the candidate profile context, should this box be checked? Respond with "Yes" if it should be checked, or "No" if it should remain unchecked.
Return ONLY "Yes" or "No". Do not include any extra text."""
    else:
        return None

    answer = call_gemini_api(prompt)
    # Every Gemini call means no saved profile answer existed -> obstacle question.
    # Log it (with the AI's best guess) so the user can give a canonical answer.
    try:
        log_pending_question(label_text, el_type, options_list or [], answer)
    except Exception:
        pass
    return answer

def query_selector_all_across_frames(page, selector):
    elements = []
    # page.frames is a list of all Frame objects currently attached
    for frame in page.frames:
        try:
            if frame.is_detached():
                continue
            found = frame.query_selector_all(selector)
            for el in found:
                elements.append((el, frame))
        except Exception:
            pass
    return elements

def match_option_value(saved_val, options):
    # options is a list of {"text": "...", "value": "..."}
    saved_val_lower = saved_val.lower()
    
    # 1. Exact match
    for opt in options:
        if opt['text'].lower() == saved_val_lower or opt['value'].lower() == saved_val_lower:
            return opt['value']
            
    # 2. Substring match
    for opt in options:
        opt_text_lower = opt['text'].lower()
        if saved_val_lower in opt_text_lower or opt_text_lower in saved_val_lower:
            return opt['value']
            
    # 3. Common abbreviations and demographics
    for opt in options:
        text_lower = opt['text'].lower()
        val_lower = opt['value'].lower()
        
        # Gender mapping
        if saved_val_lower == "male" and (text_lower == "m" or text_lower == "man"):
            return opt['value']
        if saved_val_lower == "female" and (text_lower == "f" or text_lower == "woman"):
            return opt['value']
        if "identify" in saved_val_lower or "decline" in saved_val_lower or "prefer not" in saved_val_lower:
            if "decline" in text_lower or "decline" in val_lower or "prefer not" in text_lower or "prefer not" in val_lower or "undisclosed" in text_lower:
                return opt['value']
                
        # Yes/No mappings
        if saved_val_lower in ["yes", "true", "1"] and text_lower in ["yes", "y", "true", "agree"]:
            return opt['value']
        if saved_val_lower in ["no", "false", "0"] and text_lower in ["no", "n", "false", "disagree"]:
            return opt['value']
            
    return None

def load_profile():
    with open('profile.json', 'r') as f:
        return json.load(f)

def save_gemini_response_to_profile(label_text, value):
    try:
        profile = load_profile()
        if 'custom_keywords' not in profile:
            profile['custom_keywords'] = {}
        key = label_text.strip()
        if key:
            profile['custom_keywords'][key] = value
            with open('profile.json', 'w') as f:
                json.dump(profile, f, indent=2)
            print(f"    [SAVED TO PROFILE] Added custom keyword mapping: '{key}' -> '{value}'")
    except Exception as e:
        print(f"    [ERROR] Failed to save Gemini response to profile: {e}")

def load_jobs():
    with open('jobs_database.json', 'r') as f:
        return json.load(f)

def save_jobs(jobs):
    with open('jobs_database.json', 'w') as f:
        json.dump(jobs, f, indent=2)

def kill_playwright_browsers():
    import subprocess
    try:
        # Run PowerShell command to stop any process running from ms-playwright folder
        cmd = 'Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "*ms-playwright*" } | Stop-Process -Force'
        subprocess.run(["powershell", "-Command", cmd], capture_output=True)
        print("Cleaned up any orphaned automation browsers.")
        
        # Also clean up lock file if it exists
        lock_file = os.path.abspath("./playwright_user_data/SingletonLock")
        if os.path.exists(lock_file):
            try:
                os.remove(lock_file)
                print("Removed browser SingletonLock file.")
            except Exception:
                pass
    except Exception as e:
        print(f"Cleanup warning: {e}")

def inject_button(p):
    try:
        js_code = """
        function addAutofillButton() {
            if (document.getElementById('antigravity-autofill-btn')) return;
            
            const btn = document.createElement('div');
            btn.id = 'antigravity-autofill-btn';
            btn.innerHTML = '✨ Autofill Form';
            btn.style.cssText = `
                position: fixed;
                bottom: 25px;
                right: 25px;
                z-index: 2147483647;
                background: linear-gradient(135deg, #3B82F6, #06B6D4);
                color: white;
                padding: 12px 24px;
                border-radius: 30px;
                font-family: 'Outfit', -apple-system, BlinkMacSystemFont, sans-serif;
                font-weight: bold;
                font-size: 14px;
                cursor: pointer;
                box-shadow: 0 4px 20px rgba(6, 182, 212, 0.5);
                border: 2px solid rgba(255,255,255,0.25);
                user-select: none;
                transition: transform 0.2s, box-shadow 0.2s;
            `;
            
            btn.onmouseover = () => {
                btn.style.transform = 'scale(1.05)';
                btn.style.boxShadow = '0 6px 25px rgba(6, 182, 212, 0.7)';
            };
            btn.onmouseout = () => {
                btn.style.transform = 'scale(1)';
                btn.style.boxShadow = '0 4px 20px rgba(6, 182, 212, 0.5)';
            };
            
            btn.onclick = () => {
                btn.innerHTML = '⚡ Filling...';
                btn.style.background = '#10B981';
                window.trigger_python_autofill().then(() => {
                    btn.innerHTML = '✨ Autofill Form';
                    btn.style.background = 'linear-gradient(135deg, #3B82F6, #06B6D4)';
                }).catch(() => {
                    btn.innerHTML = '❌ Failed';
                    btn.style.background = '#EF4444';
                    setTimeout(() => {
                        btn.innerHTML = '✨ Autofill Form';
                        btn.style.background = 'linear-gradient(135deg, #3B82F6, #06B6D4)';
                    }, 2000);
                });
            };
            
            document.body.appendChild(btn);
        }
        if (document.body) {
            addAutofillButton();
        } else {
            window.addEventListener('DOMContentLoaded', addAutofillButton);
        }
        """
        p.evaluate(js_code)
    except Exception:
        pass

def autofill_form(page, profile, wait_first=False):
    personal = profile['personal']
    
    if wait_first:
        page.wait_for_timeout(3000)
    
    print(f"Scanning page {page.url} for inputs (including iframes)...")
    
    # Common input filling logic using heuristics
    fill_mappings = [
        # Full Name / First Name
        {"selectors": ["input[name*='name' i]", "input[id*='name' i]", "input[placeholder*='name' i]"], "value": personal['full_name']},
        {"selectors": ["input[name*='first' i]", "input[id*='first' i]", "input[placeholder*='First' i]"], "value": personal['first_name']},
        {"selectors": ["input[name*='last' i]", "input[id*='last' i]", "input[placeholder*='Last' i]"], "value": personal['last_name']},
        
        # Email
        {"selectors": ["input[type='email']", "input[name*='email' i]", "input[id*='email' i]"], "value": personal['email']},
        
        # Phone
        {"selectors": ["input[type='tel']", "input[name*='phone' i]", "input[name*='mobile' i]", "input[id*='phone' i]"], "value": personal['phone']},
        
        # Links
        {"selectors": ["input[name*='linkedin' i]", "input[placeholder*='linkedin' i]", "input[id*='linkedin' i]"], "value": personal['linkedin']},
        {"selectors": ["input[name*='github' i]", "input[placeholder*='github' i]", "input[id*='github' i]"], "value": personal['github']},
        {"selectors": ["input[name*='portfolio' i]", "input[name*='website' i]", "input[placeholder*='portfolio' i]"], "value": personal.get('portfolio') or personal.get('github', '')},

        # Location / City — broad selectors covering Greenhouse, Lever, and custom ATS forms
        {"selectors": [
            "input[name*='city' i]", "input[id*='city' i]",
            "input[placeholder*='city' i]", "input[placeholder='City']",
            "input[aria-label*='city' i]"
        ], "value": personal.get('city', (personal.get('location', '') or '').split(',')[0].strip())},
        {"selectors": [
            "input[name*='location' i]", "input[id*='location' i]",
            "input[placeholder*='location' i]", "input[aria-label*='location' i]"
        ], "value": personal.get('location', '')},

        # Address / Street
        {"selectors": [
            "input[name*='address' i]", "input[id*='address' i]",
            "input[placeholder*='address' i]", "input[aria-label*='address' i]",
            "input[name*='street' i]", "input[id*='street' i]"
        ], "value": personal.get('street', personal.get('address', ''))},

        # Zip / Pincode / Postal code
        {"selectors": [
            "input[name*='zip' i]", "input[id*='zip' i]",
            "input[name*='postal' i]", "input[id*='postal' i]",
            "input[name*='pincode' i]", "input[id*='pincode' i]",
            "input[placeholder*='zip' i]", "input[placeholder*='postal' i]",
            "input[placeholder*='pincode' i]", "input[placeholder*='pin code' i]"
        ], "value": personal.get('pincode', personal.get('zip', '530008'))},

        # State
        {"selectors": [
            "input[name*='state' i]", "input[id*='state' i]",
            "input[placeholder*='state' i]", "input[aria-label*='state' i]"
        ], "value": personal.get('state', 'Andhra Pradesh')},
    ]
    
    filled_count = 0
    for mapping in fill_mappings:
        for selector in mapping['selectors']:
            try:
                elements = query_selector_all_across_frames(page, selector)
                for el, frame in elements:
                    if el.is_visible() and el.is_enabled():
                        val = el.input_value()
                        if not val:
                            el.fill(mapping['value'])
                            el.press("Tab")  # trigger React/Angular change events
                            filled_count += 1
                            break
            except Exception as e:
                pass
                
    # Textarea matching (e.g. cover letter or summary)
    try:
        summary_els = query_selector_all_across_frames(page, "textarea[name*='summary' i], textarea[name*='cover' i], textarea[id*='cover' i]")
        for el, frame in summary_els:
            if el.is_visible() and not el.input_value():
                full_name = personal.get('full_name', 'I')
                custom = profile.get('custom_responses', {})
                ai_summary = custom.get('summary_ai_experience', '')
                why_join = custom.get('why_join_company', '')
                cover_letter = f"Dear Hiring Team,\n\nI am writing to express my interest in this position. {ai_summary or f'{full_name} is a motivated software developer with experience in Python, SQL, React, and AI/ML.'}\n\n{why_join or 'I look forward to contributing my technical skills and problem-solving abilities to your team.'}\n\nSincerely,\n{full_name}"
                el.fill(cover_letter)
                filled_count += 1
    except Exception:
        pass
        
    # File upload (Resume PDF)
    try:
        file_inputs = query_selector_all_across_frames(page, "input[type='file']")
        resume_path = personal['resume_path']
        if os.path.exists(resume_path) and file_inputs:
            for file_in, frame in file_inputs:
                accept_attr = file_in.get_attribute("accept") or ""
                name_attr = file_in.get_attribute("name") or ""
                id_attr = file_in.get_attribute("id") or ""
                
                if "pdf" in accept_attr.lower() or "resume" in name_attr.lower() or "cv" in name_attr.lower() or "resume" in id_attr.lower() or "cv" in id_attr.lower() or not accept_attr:
                    file_in.set_input_files(resume_path)
                    print(f"Uploaded resume: {resume_path}")
                    filled_count += 1
                    break
    except Exception as e:
        print(f"Could not upload resume: {e}")
        
    print(f"Autofill scan complete. Filled {filled_count} fields.")
    return filled_count

def update_status_banner(page, status_type, message):
    try:
        # status_type: 'info' (blue/cyan), 'success' (green), 'error' (red)
        bg_color = "linear-gradient(135deg, #3B82F6, #06B6D4)" # default info
        if status_type == 'success':
            bg_color = "linear-gradient(135deg, #10B981, #059669)"
        elif status_type == 'error':
            bg_color = "linear-gradient(135deg, #EF4444, #DC2626)"
            
        js_code = f"""
        (function() {{
            let banner = document.getElementById('antigravity-status-banner');
            if (!banner) {{
                banner = document.createElement('div');
                banner.id = 'antigravity-status-banner';
                banner.style.cssText = `
                    position: fixed;
                    top: 15px;
                    left: 50%;
                    transform: translateX(-50%);
                    z-index: 2147483647;
                    color: white;
                    padding: 12px 24px;
                    border-radius: 12px;
                    font-family: 'Outfit', -apple-system, BlinkMacSystemFont, sans-serif;
                    font-weight: bold;
                    font-size: 14px;
                    box-shadow: 0 10px 25px rgba(0,0,0,0.3);
                    border: 2px solid rgba(255,255,255,0.25);
                    display: flex;
                    align-items: center;
                    gap: 10px;
                    transition: all 0.3s ease;
                `;
                document.body.appendChild(banner);
            }}
            banner.style.background = '{bg_color}';
            banner.innerHTML = `🌌 <span>{message}</span>`;
        }})();
        """
        page.evaluate(js_code)
    except Exception as e:
        print(f"Error updating banner: {e}")

def find_saved_response(label_text, profile):
    label = label_text.lower()
    personal = profile.get("personal", {})
    custom_responses = profile.get("custom_responses", {})
    custom_keywords = profile.get("custom_keywords", {})
    
    # 0. Check personal fields first
    if "linkedin" in label:
        return personal.get("linkedin")
    if "github" in label:
        return personal.get("github")
    if "email" in label:
        return personal.get("email")
    if "phone" in label or "mobile" in label or "phone number" in label or "contact number" in label:
        return personal.get("phone")
    if "portfolio" in label or "website" in label or "personal site" in label or "homepage" in label:
        return personal.get("portfolio") or personal.get("github")
    if "first name" in label or "given name" in label:
        return personal.get("first_name")
    if "last name" in label or "family name" in label or "surname" in label:
        return personal.get("last_name")
    if "full name" in label:
        return personal.get("full_name")
    if label == "name":
        return personal.get("full_name")
    if "name" in label and "first" not in label and "last" not in label and "family" not in label and "given" not in label:
        return personal.get("full_name")
    if "city" in label or ("location" in label and "relocat" not in label):
        city = personal.get("city", "")
        if not city:
            loc = personal.get("location", "")
            city = loc.split(",")[0].strip() if loc else ""
        return city or personal.get("location", "")
    if "street" in label or ("address" in label and "email" not in label):
        return personal.get("street", personal.get("address", ""))
    if "zip" in label or "postal" in label or "pincode" in label or "pin code" in label:
        return personal.get("pincode", personal.get("zip", "530008"))
    if "state" in label and "outside" not in label and "united states" not in label:
        return personal.get("state", "Andhra Pradesh")

    # 0.5. Check user-defined dynamic custom keywords first! (Case-insensitive)
    for keyword, answer in custom_keywords.items():
        if keyword.lower() in label:
            print(f"    [MATCHED CUSTOM KEYWORD] Keyword '{keyword}' matched in label '{label_text[:50]}' -> '{answer}'")
            return answer
            
    # 1. US Work authorization / sponsorship
    if "authorized" in label and ("us" in label or "united states" in label or "u.s." in label):
        return custom_responses.get("authorized_us")
    if "sponsorship" in label and ("us" in label or "united states" in label or "u.s." in label):
        return custom_responses.get("sponsorship_us")
        
    # 2. India Work authorization / sponsorship
    if "authorized" in label and "india" in label:
        return custom_responses.get("authorized_in")
    if "sponsorship" in label and "india" in label:
        return custom_responses.get("sponsorship_in")
        
    # General authorization / sponsorship fallback
    if "authorized" in label:
        return custom_responses.get("authorized_in")
    if "sponsorship" in label or "require visa" in label or "require work visa" in label:
        return custom_responses.get("sponsorship_in")
        
    # 3. Notice Period
    if "notice" in label or "notice period" in label or "start date" in label or "how soon" in label or "available" in label:
        return custom_responses.get("notice_period")
        
    # 4. Expected Salary
    if "salary" in label or "compensation" in label or "ctc" in label or "expected pay" in label:
        return custom_responses.get("expected_salary")
        
    # 5. Demographics
    if "gender" in label or "sex" in label:
        return custom_responses.get("gender")
    if "race" in label or "ethnicity" in label:
        return custom_responses.get("race_ethnicity")
    if "veteran" in label or "military" in label:
        return custom_responses.get("veteran_status")
    if "disability" in label or "handicap" in label:
        return custom_responses.get("disability_status")
    if "pronoun" in label:
        return custom_responses.get("preferred_pronouns")
        
    # 6. Job Source
    if "hear" in label or "source" in label or "referral" in label or "how did you" in label:
        return custom_responses.get("hear_about_us")
        
    # 7. AI/ML Experience Summary
    if "experience" in label and ("ai" in label or "ml" in label or "machine" in label):
        return custom_responses.get("summary_ai_experience")
        
    # 8. CS / IT degree
    if "degree" in label or "major" in label or "bachelor" in label or "education" in label or "b.tech" in label:
        return custom_responses.get("has_cs_degree")
        
    # 9. Relocation / Work Mode / Years experience
    if "relocate" in label or "relocation" in label:
        return custom_responses.get("willing_to_relocate")
    if "remote" in label or "hybrid" in label or "onsite" in label or "work preference" in label:
        return custom_responses.get("work_mode_preference")
    if "experience" in label and ("years" in label or "how many" in label):
        return custom_responses.get("years_experience")
        
    # 10. Security Clearance & Polygraph (Greenhouse/Captivation)
    if "security clearance" in label or "active clearance" in label or ("clearance" in label and "hold" in label):
        return custom_responses.get("security_clearance")
    if "level of security clearance" in label or "clearance do you hold" in label:
        return custom_responses.get("security_clearance_level")
    if "polygraph" in label:
        return custom_responses.get("polygraph_level")
    if "md agency" in label:
        return custom_responses.get("md_agency_clearance")
        
    # 11. Demographic Detail Extensions (Greenhouse/Captivation)
    if "sexual orientation" in label or "sexual" in label:
        return custom_responses.get("sexual_orientation")
    if "transgender" in label:
        return custom_responses.get("transgender")
    if "hispanic" in label or "latino" in label:
        return custom_responses.get("hispanic_latino")
        
    # 12. Education Details
    if "graduation year" in label or "year of graduation" in label or "grad year" in label:
        return custom_responses.get("graduation_year")
    if "gpa" in label or "cgpa" in label or "grades" in label:
        return custom_responses.get("gpa_cgpa")
    if "university" in label or "college" in label or "school name" in label:
        return custom_responses.get("university_name")
        
    # 13. Specific Skill Experience
    if "python" in label and ("years" in label or "experience" in label):
        return custom_responses.get("python_experience")
    if ("react" in label or "frontend" in label) and ("years" in label or "experience" in label):
        return custom_responses.get("react_experience")
    if ("sql" in label or "database" in label) and ("years" in label or "experience" in label):
        return custom_responses.get("sql_experience")
    if ("javascript" in label or "js" in label or "typescript" in label or "ts" in label) and ("years" in label or "experience" in label):
        return custom_responses.get("js_ts_experience")
    if ("machine learning" in label or "ai" in label or "ml" in label or "artificial intelligence" in label) and ("years" in label or "experience" in label):
        return custom_responses.get("ai_ml_experience")
        
    # 14. Voluntary Acknowledgment & Certifications
    if "background check" in label or "background screen" in label or "consumer report" in label:
        return custom_responses.get("agree_background_check")
    if "certify" in label or "accurate" in label or "truthful" in label or "correct" in label or "under penalty" in label:
        return custom_responses.get("certify_correct_information")
        
    # 15. Open-Ended Questions
    if "why do you want to join" in label or "why our company" in label or "interest in this role" in label or "interest in us" in label:
        return custom_responses.get("why_join_company")
    if "challenging project" in label or "project you built" in label or "describe a project" in label:
        return custom_responses.get("challenging_project_description")
        
    # 16. Substring match fallback on standard customs
    for key, val in custom_responses.items():
        clean_key = key.replace('_', ' ')
        if clean_key in label or label in clean_key:
            return val
            
    return None

def fill_custom_fields_with_saved_responses(page, profile, company_name, job_title):
    print("Analyzing page (including iframes) for custom/unfilled fields...")
    
    # 1. Handle normal text/select inputs
    input_selectors = [
        "input[type='text']:not([disabled])",
        "input:not([type]):not([disabled])",
        "textarea:not([disabled])",
        "select:not([disabled])"
    ]
    
    unfilled_elements = []
    for sel in input_selectors:
        try:
            elements = query_selector_all_across_frames(page, sel)
            for el, frame in elements:
                if el.is_visible() and el.is_enabled():
                    tag_name = el.evaluate("node => node.tagName.toLowerCase()")
                    val = ""
                    if tag_name == "select":
                        val = el.input_value()
                        if not val or val == "0" or val == "":
                            unfilled_elements.append((el, frame, "dropdown"))
                    else:
                        val = el.input_value()
                        if not val or len(val.strip()) == 0:
                            el_type = el.get_attribute("type") or "text"
                            if el_type in ["text", "textarea"] or tag_name == "textarea":
                                unfilled_elements.append((el, frame, tag_name if tag_name == "textarea" else "text"))
        except Exception:
            pass
            
    if unfilled_elements:
        print(f"Found {len(unfilled_elements)} unfilled text/select fields across all frames.")
        for idx, (el, frame, el_type) in enumerate(unfilled_elements):
            try:
                # Extract context in the correct frame using browser-evaluated JavaScript
                label_text = el.evaluate("""node => {
                    // 1. Check aria-label
                    let label = node.getAttribute('aria-label');
                    if (label && label.trim().length > 2) return label.trim();
                    
                    // 2. Check aria-labelledby
                    let labelledby = node.getAttribute('aria-labelledby');
                    if (labelledby) {
                        let target = document.getElementById(labelledby);
                        if (target && target.innerText && target.innerText.trim().length > 2) {
                            return target.innerText.trim();
                        }
                    }
                    
                    // 3. Check explicit label using for attribute
                    let id = node.getAttribute('id');
                    if (id) {
                        let explicitLabel = document.querySelector(`label[for="${id}"]`);
                        if (explicitLabel && explicitLabel.innerText && explicitLabel.innerText.trim().length > 2) {
                            return explicitLabel.innerText.trim();
                        }
                    }
                    
                    // 4. Check if input is nested inside a label
                    let parentLabel = node.closest('label');
                    if (parentLabel && parentLabel.innerText && parentLabel.innerText.trim().length > 2) {
                        return parentLabel.innerText.trim();
                    }
                    
                    // 5. Look for nearby label elements or container text
                    let parent = node.parentElement;
                    for (let depth = 0; depth < 4; depth++) {
                        if (!parent) break;
                        let lbl = parent.querySelector('label');
                        if (lbl && lbl.innerText && lbl.innerText.trim().length > 2) {
                            return lbl.innerText.trim();
                        }
                        
                        let prev = node.previousElementSibling;
                        while (prev) {
                            if (prev.tagName.toLowerCase() === 'label' || prev.classList.contains('label') || prev.classList.contains('field-label')) {
                                if (prev.innerText && prev.innerText.trim().length > 2) {
                                    return prev.innerText.trim();
                                }
                            }
                            prev = prev.previousElementSibling;
                        }
                        parent = parent.parentElement;
                    }
                    
                    // 6. Check placeholder
                    let placeholder = node.getAttribute('placeholder');
                    if (placeholder && placeholder.trim().length > 2) return placeholder.trim();
                    
                    // 7. Check name/id as a last resort, but only if it's not generic system names
                    let name = node.getAttribute('name');
                    if (name && !name.includes('[') && !name.includes('_attributes') && name.trim().length > 2) return name.trim();
                    
                    let elId = node.getAttribute('id');
                    if (elId && !elId.includes('_attributes') && !elId.includes('-') && elId.trim().length > 2) return elId.trim();
                    
                    // 8. If parent container has text, try to extract first line
                    if (node.parentElement) {
                        let parentText = node.parentElement.innerText || '';
                        let lines = parentText.split('\\n').map(l => l.trim()).filter(l => l.length > 2);
                        if (lines.length > 0) {
                            return lines[0];
                        }
                    }
                    
                    return '';
                }""").strip()
                
                if not label_text or len(label_text) < 3:
                    el_id = el.get_attribute("id") or ""
                    el_name = el.get_attribute("name") or ""
                    el_placeholder = el.get_attribute("placeholder") or ""
                    label_text = el_placeholder or el_name or el_id or "Custom Question"
                
                print(f" -> Field [{idx+1}/{len(unfilled_elements)}]: Label='{label_text[:50]}' (Type: {el_type})")
                
                # Check for saved custom response first
                saved_val = find_saved_response(label_text, profile)
                
                # Detect custom combobox dropdowns (e.g. React Select)
                role_attr = el.get_attribute("role") or ""
                class_attr = el.get_attribute("class") or ""
                is_combobox = role_attr == "combobox" or "select__input" in class_attr

                if saved_val is not None:
                    print(f"    [MATCHED USER RESPONSES] Reusing saved response: '{saved_val[:50]}'")
                    if el_type == "dropdown":
                        options_data = el.evaluate("""node => {
                            return Array.from(node.options).map(opt => ({
                                text: opt.text.strip(),
                                value: opt.value
                            })).filter(opt => opt.value !== "");
                        }""")
                        
                        matched_val = match_option_value(saved_val, options_data)
                        if matched_val:
                            el.select_option(value=matched_val)
                            print(f"    Selected dropdown option: '{matched_val}'")
                        else:
                            if options_data:
                                el.select_option(index=1)
                    elif is_combobox:
                        print(f"    Selected option via combobox input: '{saved_val}'")
                        el.click()
                        frame.wait_for_timeout(300)
                        el.fill(saved_val)
                        frame.wait_for_timeout(300)
                        el.press("Enter")
                        frame.wait_for_timeout(300)
                    else:
                        el.fill(saved_val)
                else:
                    # Let's try Gemini AI!
                    if HAS_GEMINI:
                        print(f"    [GEMINI AI] Calling Gemini API fallback for field '{label_text[:50]}'")
                        if el_type == "dropdown":
                            options_data = el.evaluate("""node => {
                                return Array.from(node.options).map(opt => ({
                                    text: opt.text.strip(),
                                    value: opt.value
                                })).filter(opt => opt.value !== "");
                            }""")
                            options_list = [opt['text'] for opt in options_data]
                            ai_val = get_gemini_response(label_text, "dropdown", options_list, profile)
                            if ai_val:
                                print(f"    [GEMINI AI ANSWER] Selected option: '{ai_val}'")
                                save_gemini_response_to_profile(label_text, ai_val)
                                matched_val = match_option_value(ai_val, options_data)
                                if matched_val:
                                    el.select_option(value=matched_val)
                                else:
                                    if options_data:
                                        el.select_option(index=1)
                            else:
                                if options_data:
                                    el.select_option(index=1)
                        elif is_combobox:
                            ai_val = get_gemini_response(label_text, "text", [], profile)
                            if ai_val:
                                print(f"    [GEMINI AI ANSWER] Combobox input: '{ai_val}'")
                                save_gemini_response_to_profile(label_text, ai_val)
                                el.click()
                                frame.wait_for_timeout(300)
                                el.fill(ai_val)
                                frame.wait_for_timeout(300)
                                el.press("Enter")
                                frame.wait_for_timeout(300)
                        else:
                            ai_val = get_gemini_response(label_text, el_type, [], profile)
                            if ai_val:
                                print(f"    [GEMINI AI ANSWER] Field filled: '{ai_val[:100]}'")
                                save_gemini_response_to_profile(label_text, ai_val)
                                el.fill(ai_val)
                    else:
                        print(f"    [WARNING] No saved response found for '{label_text[:50]}' and Gemini is disabled. Skipping field.")
                    
                frame.wait_for_timeout(500)
            except Exception as e:
                print(f"    Error filling field: {e}")
 
    # 2. Handle Radio Buttons Groups
    radio_groups = {}
    try:
        radio_elements = query_selector_all_across_frames(page, "input[type='radio']:not([disabled])")
        for el, frame in radio_elements:
            if el.is_visible() and el.is_enabled():
                name = el.get_attribute("name")
                if name:
                    if name not in radio_groups:
                        radio_groups[name] = []
                    radio_groups[name].append((el, frame))
    except Exception:
        pass
  
    for name, els_info in radio_groups.items():
        try:
            # Check if any radio in this group is checked
            any_checked = False
            for el, frame in els_info:
                if el.evaluate("node => node.checked"):
                    any_checked = True
                    break
            if any_checked:
                continue # Skip if already answered
                
            first_el, frame = els_info[0]
            question_text = first_el.evaluate("""node => {
                let parent = node.closest('.field, .form-group, .question, fieldset, tr, li');
                if (parent) {
                    let legend = parent.querySelector('legend');
                    if (legend && legend.innerText.trim()) return legend.innerText.trim();
                    let label = parent.querySelector('label, .label, .field-label');
                    if (label && label.innerText.trim()) return label.innerText.trim();
                }
                let p = node.parentElement;
                while (p && p.innerText.trim().length < 10) {
                    p = p.parentElement;
                }
                return p ? p.innerText.trim() : '';
            }""").strip()
            if '\n' in question_text:
                lines = [l.strip() for l in question_text.split('\n') if l.strip()]
                if lines:
                    question_text = lines[0]
                    
            options = []
            for idx, (el, frame) in enumerate(els_info):
                el_id = el.get_attribute("id")
                opt_text = ""
                if el_id:
                    label_el = frame.query_selector(f"label[for='{el_id}']")
                    if label_el:
                        opt_text = label_el.inner_text().strip()
                if not opt_text:
                    opt_text = el.evaluate("node => node.parentElement ? node.parentElement.innerText.trim() : ''").strip()
                if not opt_text:
                    opt_text = el.get_attribute("value") or f"Option {idx+1}"
                options.append((el, opt_text))
                
            print(f" -> Radio group '{name}': Question='{question_text[:50]}'")
            
            # Check for saved custom response first
            saved_val = find_saved_response(question_text, profile)
            
            if saved_val is not None:
                print(f"    [MATCHED USER RESPONSES] Reusing saved response for radio: '{saved_val[:50]}'")
                selected = False
                for radio_el, opt_txt in options:
                    if saved_val.lower() in opt_txt.lower() or opt_txt.lower() in saved_val.lower():
                        radio_el.click()
                        print(f"    Selected radio option: '{opt_txt}'")
                        selected = True
                        break
                if not selected and options:
                    options[0][0].click()
            else:
                if HAS_GEMINI:
                    print(f"    [GEMINI AI] Calling Gemini API fallback for radio group '{question_text[:50]}'")
                    options_list = [opt_txt for el, opt_txt in options]
                    ai_val = get_gemini_response(question_text, "dropdown", options_list, profile)
                    if ai_val:
                        print(f"    [GEMINI AI ANSWER] Radio option: '{ai_val}'")
                        save_gemini_response_to_profile(question_text, ai_val)
                        selected = False
                        for radio_el, opt_txt in options:
                            if ai_val.lower() in opt_txt.lower() or opt_txt.lower() in ai_val.lower():
                                radio_el.click()
                                selected = True
                                break
                        if not selected and options:
                            options[0][0].click()
                    else:
                        if options:
                            options[0][0].click()
                else:
                    print(f"    [WARNING] No saved response for radio '{question_text[:50]}' and Gemini is disabled. Skipping radio group.")
                
            frame.wait_for_timeout(500)
        except Exception as e:
            print(f"    Error processing radio group {name}: {e}")
 
    # 3. Handle Individual Checkboxes
    checkbox_elements = []
    try:
        checkboxes = query_selector_all_across_frames(page, "input[type='checkbox']:not([disabled])")
        for el, frame in checkboxes:
            if el.is_visible() and el.is_enabled() and not el.evaluate("node => node.checked"):
                checkbox_elements.append((el, frame))
    except Exception:
        pass
        
    for el, frame in checkbox_elements:
        try:
            label_text = el.evaluate("""node => {
                let id = node.getAttribute('id');
                if (id) {
                    let lbl = document.querySelector(`label[for="${id}"]`);
                    if (lbl && lbl.innerText.trim()) return lbl.innerText.trim();
                }
                let parentLabel = node.closest('label');
                if (parentLabel && parentLabel.innerText.trim()) return parentLabel.innerText.trim();
                
                if (node.parentElement) {
                    return node.parentElement.innerText.trim();
                }
                return '';
            }""").strip()
            
            if not label_text:
                label_text = el.get_attribute("name") or "Checkbox"
                
            print(f" -> Checkbox: Label='{label_text[:50]}'")
            
            # Check for saved custom response first
            saved_val = find_saved_response(label_text, profile)
            
            if saved_val is not None:
                print(f"    [MATCHED USER RESPONSES] Reusing saved response for checkbox: '{saved_val}'")
                if saved_val.lower() in ["yes", "check", "true", "1", "agree"]:
                    el.click()
                    print("    Checked the box.")
                else:
                    print("    Left the box unchecked.")
            else:
                if HAS_GEMINI:
                    print(f"    [GEMINI AI] Calling Gemini API fallback for checkbox '{label_text[:50]}'")
                    ai_val = get_gemini_response(label_text, "checkbox", [], profile)
                    if ai_val:
                        save_gemini_response_to_profile(label_text, ai_val)
                    if ai_val and ai_val.lower() in ["yes", "true", "agree"]:
                        el.click()
                        print("    Checked the box.")
                    else:
                        print("    Left the box unchecked.")
                else:
                    print(f"    [WARNING] No saved response for checkbox '{label_text[:50]}' and Gemini is disabled. Skipping checkbox.")
                
            frame.wait_for_timeout(500)
        except Exception as e:
            print(f"    Error processing checkbox: {e}")

def auto_submit_form(page):
    submit_selectors = [
        "button[type='submit']",
        "input[type='submit']",
        "button:has-text('Submit Application' i)",
        "button:has-text('Submit' i)",
        "button:has-text('Send Application' i)",
        "input[value*='Submit' i]",
        "button:has-text('Apply' i)",
        "input[value*='Apply' i]"
    ]
    
    page.wait_for_timeout(2000) # Small pause to let user see filled data
    for selector in submit_selectors:
        for frame in page.frames:
            try:
                if frame.is_detached():
                    continue
                btn = frame.locator(selector).first
                if btn.is_visible() and btn.is_enabled():
                    print(f"Auto-submitting: Clicking button matching '{selector}' in frame {frame.url}")
                    btn.click()
                    page.wait_for_timeout(3000) # Wait for page reaction
                    return True
            except Exception:
                pass
    return False

def verify_submission_success(page):
    success_url_keywords = [
        "thanks", "thank-you", "thank_you", "success", "confirmation",
        "submitted", "application-received", "complete", "done"
    ]
    success_phrases = [
        "thank you for applying",
        "application received",
        "application submitted",
        "successfully submitted",
        "thanks for applying",
        "your application has been received",
        "we have received your application",
        "your application was submitted",
        "application complete",
        "you have applied",
        "application is complete",
    ]
    for _ in range(5):
        current_url = page.url.lower()
        if any(kw in current_url for kw in success_url_keywords):
            return True
        try:
            body_text = page.locator("body").inner_text().lower()
            if any(phrase in body_text for phrase in success_phrases):
                return True
        except Exception:
            pass
        page.wait_for_timeout(1000)
    return False

def check_validation_errors(page):
    """Return True if any required form fields are still empty/invalid."""
    try:
        for frame in page.frames:
            if frame.is_detached():
                continue
            count = frame.evaluate(
                "() => document.querySelectorAll('input:invalid, select:invalid, textarea:invalid').length"
            )
            if count and count > 0:
                return True
    except Exception:
        pass
    return False


def fill_required_fields_last_pass(page, profile):
    """Final sweep: find every required field still empty and fill it (Gemini fallback)."""
    personal = profile.get("personal", {})
    selectors = [
        "input[required]:not([type='hidden']):not([type='file']):not([type='submit'])",
        "select[required]",
        "textarea[required]",
    ]
    label_js = """node => {
        let t = node.getAttribute('aria-label') || '';
        if (t.trim().length > 2) return t.trim();
        let lid = node.getAttribute('aria-labelledby');
        if (lid) { let el = document.getElementById(lid); if (el) return el.innerText.trim(); }
        let id = node.getAttribute('id');
        if (id) { let lbl = document.querySelector('label[for="' + id + '"]'); if (lbl) return lbl.innerText.trim(); }
        let pl = node.getAttribute('placeholder');
        if (pl && pl.trim().length > 2) return pl.trim();
        let p = node.parentElement;
        for (let d = 0; d < 5; d++) {
            if (!p) break;
            let lbl = p.querySelector('label');
            if (lbl && lbl.innerText.trim().length > 2) return lbl.innerText.trim();
            p = p.parentElement;
        }
        return node.getAttribute('name') || node.getAttribute('id') || '';
    }"""
    for frame in page.frames:
        if frame.is_detached():
            continue
        for sel in selectors:
            try:
                for el in frame.query_selector_all(sel):
                    if not el.is_visible() or not el.is_enabled():
                        continue
                    val = el.input_value()
                    if val and val.strip():
                        continue
                    label_text = (el.evaluate(label_js) or "").strip() or el.get_attribute("name") or "Field"
                    tag = el.evaluate("n => n.tagName.toLowerCase()")
                    saved = find_saved_response(label_text, profile)
                    if saved:
                        if tag == "select":
                            opts = el.evaluate("n => Array.from(n.options).map(o=>({text:o.text,value:o.value})).filter(o=>o.value)")
                            mv = match_option_value(saved, opts)
                            if mv:
                                el.select_option(value=mv)
                        else:
                            el.fill(saved)
                            el.press("Tab")
                        print(f"    [LAST-PASS] '{label_text[:40]}' -> '{saved[:40]}'")
                    elif HAS_GEMINI:
                        if tag == "select":
                            opts = el.evaluate("n => Array.from(n.options).map(o=>({text:o.text,value:o.value})).filter(o=>o.value)")
                            ai = get_gemini_response(label_text, "dropdown", [o["text"] for o in opts], profile)
                            if ai:
                                save_gemini_response_to_profile(label_text, ai)
                                mv = match_option_value(ai, opts)
                                if mv:
                                    el.select_option(value=mv)
                                elif opts:
                                    el.select_option(index=1)
                        else:
                            ai = get_gemini_response(label_text, tag if tag == "textarea" else "text", [], profile)
                            if ai:
                                save_gemini_response_to_profile(label_text, ai)
                                el.fill(ai)
                                el.press("Tab")
                        print(f"    [LAST-PASS GEMINI] '{label_text[:40]}'")
            except Exception as e:
                print(f"    [LAST-PASS ERROR] {e}")


def save_success_screenshot(page, job):
    """Save a PNG screenshot after a successful application submission."""
    import os
    import datetime
    try:
        os.makedirs("screenshots", exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        safe = "".join(c if c.isalnum() or c in "_-" else "_" for c in
                       f"{job.get('company','unknown')}_{job.get('title','job')}")[:45]
        path = os.path.join("screenshots", f"{safe}_{ts}.png")
        page.screenshot(path=path, full_page=False)
        print(f"    [SCREENSHOT] Saved: {path}")
        return path
    except Exception as e:
        print(f"    [SCREENSHOT ERROR] {e}")
        return None


def handle_internshala_form(page, profile):
    """Fill Internshala job/internship application modal or page."""
    personal = profile.get("personal", {})
    custom = profile.get("custom_responses", {})
    try:
        # Click Apply button if present on the job detail page
        for sel in ["button#btn-apply", "button.btn-apply", "a.apply-btn", "button:has-text('Apply Now')", "button:has-text('Apply')"]:
            try:
                btn = page.locator(sel).first
                if btn.is_visible():
                    btn.click()
                    page.wait_for_timeout(2000)
                    break
            except Exception:
                pass
        # Fill cover letter
        for sel in ["textarea[name='cover_letter']", "textarea[id*='cover']", "textarea[placeholder*='cover']"]:
            try:
                el = page.locator(sel).first
                if el.is_visible() and not el.input_value():
                    cover = custom.get("why_join_company", f"I am enthusiastic about this opportunity and believe my skills in Python, AI/ML, and software development align well with the role requirements.")
                    el.fill(cover)
            except Exception:
                pass
        # Availability / joining date
        for sel in ["input[name='availability']", "input[id*='availability']", "input[placeholder*='available']"]:
            try:
                el = page.locator(sel).first
                if el.is_visible() and not el.input_value():
                    el.fill("Immediately")
                    el.press("Tab")
            except Exception:
                pass
        # Expected stipend / salary
        for sel in ["input[name*='stipend']", "input[id*='ctc']", "input[placeholder*='expected']"]:
            try:
                el = page.locator(sel).first
                if el.is_visible() and not el.input_value():
                    el.fill("As per company norms")
                    el.press("Tab")
            except Exception:
                pass
        # Submit the application modal
        for sel in ["button[type='submit']", "button:has-text('Submit')", "input[type='submit']"]:
            try:
                btn = page.locator(sel).first
                if btn.is_visible():
                    btn.click()
                    page.wait_for_timeout(2000)
                    break
            except Exception:
                pass
    except Exception as e:
        print(f"    [INTERNSHALA] Error: {e}")


def handle_naukri_form(page, profile):
    """Handle Naukri quick-apply flow."""
    personal = profile.get("personal", {})
    custom = profile.get("custom_responses", {})
    try:
        # Click Apply button on Naukri job page
        for sel in ["button#apply-button", "a.apply-button", "button:has-text('Apply')", "button:has-text('Easy Apply')"]:
            try:
                btn = page.locator(sel).first
                if btn.is_visible():
                    btn.click()
                    page.wait_for_timeout(2500)
                    break
            except Exception:
                pass
        # Fill notice period if asked
        for sel in ["input[placeholder*='notice']", "select[id*='notice']"]:
            try:
                el = page.locator(sel).first
                if el.is_visible():
                    tag = el.evaluate("n=>n.tagName.toLowerCase()")
                    if tag == "select":
                        el.select_option(label="Immediately")
                    else:
                        el.fill("Immediate")
                        el.press("Tab")
            except Exception:
                pass
        # Expected CTC
        for sel in ["input[placeholder*='expected ctc']", "input[id*='ctc']", "input[name*='salary']"]:
            try:
                el = page.locator(sel).first
                if el.is_visible() and not el.input_value():
                    el.fill("As per company norms")
                    el.press("Tab")
            except Exception:
                pass
        # Submit
        for sel in ["button[type='submit']", "button:has-text('Submit')", "button:has-text('Apply Now')"]:
            try:
                btn = page.locator(sel).first
                if btn.is_visible():
                    btn.click()
                    page.wait_for_timeout(2000)
                    break
            except Exception:
                pass
    except Exception as e:
        print(f"    [NAUKRI] Error: {e}")


def handle_linkedin_easy_apply(page, profile):
    """Handle LinkedIn Easy Apply multi-step modal."""
    personal = profile.get("personal", {})
    custom = profile.get("custom_responses", {})
    try:
        # Click Easy Apply button
        for sel in ["button.jobs-apply-button", "button:has-text('Easy Apply')", "button:has-text('Apply')"]:
            try:
                btn = page.locator(sel).first
                if btn.is_visible():
                    btn.click()
                    page.wait_for_timeout(2500)
                    break
            except Exception:
                pass
        # Step through the modal up to 8 steps
        for step in range(8):
            try:
                # Fill any visible inputs
                autofill_form(page, profile, wait_first=False)
                fill_required_fields_last_pass(page, profile)
                page.wait_for_timeout(1000)
                # Click Next / Review / Submit
                clicked = False
                for sel in ["button:has-text('Submit application')", "button:has-text('Review')", "button:has-text('Next')", "button[aria-label*='Continue']"]:
                    try:
                        btn = page.locator(sel).first
                        if btn.is_visible() and btn.is_enabled():
                            btn.click()
                            page.wait_for_timeout(2000)
                            clicked = True
                            break
                    except Exception:
                        pass
                if not clicked:
                    break
                # Check if modal closed (application submitted)
                try:
                    modal = page.locator(".jobs-easy-apply-modal, .artdeco-modal").first
                    if not modal.is_visible():
                        break
                except Exception:
                    break
            except Exception:
                break
    except Exception as e:
        print(f"    [LINKEDIN] Error: {e}")


def detect_login_wall(page):
    """Return a platform name if the current page is a login/auth wall, else None.

    Many job platforms (LinkedIn, Internshala, Naukri, Indeed) force a sign-in
    before you can apply. We can't (and shouldn't) auto-enter passwords, so we
    detect the wall and mark the job 'Login Required' instead of stalling.
    """
    try:
        url = (page.url or "").lower()
        # URL-based detection (most reliable)
        login_url_markers = [
            "accounts.google.com", "/login", "/signin", "/sign-in",
            "/auth", "/authwall", "linkedin.com/uas/login",
            "linkedin.com/checkpoint", "login.naukri.com", "internshala.com/login",
            "secure.indeed.com", "/account/login",
        ]
        if any(m in url for m in login_url_markers):
            return url.split('/')[2] if '//' in url else url
        # Content-based detection: a visible password field with no application form
        try:
            has_password = page.locator("input[type='password']").count() > 0
            has_app_form = page.locator(
                "input[type='file'], textarea, input[name*='resume' i]"
            ).count() > 0
            if has_password and not has_app_form:
                return url.split('/')[2] if '//' in url else "sign-in page"
        except Exception:
            pass
    except Exception:
        pass
    return None


def handle_redirection_and_apply(page, profile, job, all_jobs):
    try:
        # Set module context so obstacle questions get logged with job metadata
        global CURRENT_JOB
        CURRENT_JOB = {
            "title": job.get("title", ""),
            "company": job.get("company", ""),
            "url": job.get("url", ""),
        }
        update_status_banner(page, 'info', '🌌 Auto-Applier: Opening job application...')
        page.wait_for_timeout(3000)

        # Bail out early if we've landed on a login/auth wall — we cannot enter
        # passwords. Mark the job so the user can log in once in this browser.
        wall = detect_login_wall(page)
        if wall:
            print(f"  [LOGIN WALL] '{wall}' requires sign-in — cannot auto-apply. Marking 'Login Required'.")
            update_status_banner(page, 'error', f'🌌 Sign-in required at {wall}. Log in once here, then retry.')
            job['status'] = 'Login Required'
            save_jobs(all_jobs)
            page.wait_for_timeout(1500)
            return False
        
        apply_button_selectors = [
            "a:has-text('Apply for this position' i)",
            "a:has-text('Apply on Company Site' i)",
            "button:has-text('Apply on Company Site' i)",
            "a[id*='apply' i]",
            "button[id*='apply' i]"
        ]
        
        current_url = page.url
        job_source = job.get("source", "")

        # Platform-specific handlers (these platforms usually require a login;
        # we run the handler, then verify rather than blindly claiming success).
        def finalize_platform(handler_name):
            """Run after a platform handler: detect login wall, verify, set status."""
            wall = detect_login_wall(page)
            if wall:
                print(f"  [{handler_name}] Hit sign-in wall at '{wall}'. Marking 'Login Required'.")
                update_status_banner(page, 'error', f'🌌 Sign-in required ({wall}). Log in once here, then retry.')
                job['status'] = 'Login Required'
                save_jobs(all_jobs)
                return False
            save_success_screenshot(page, job)
            if verify_submission_success(page):
                print(f"  [{handler_name}] Verified application submitted.")
                job['status'] = 'Applied'
            else:
                print(f"  [{handler_name}] Submitted but unverified — flagging for review.")
                job['status'] = 'Review Required'
            save_jobs(all_jobs)
            return job['status'] == 'Applied'

        if "internshala.com" in current_url:
            print("  [PLATFORM] Internshala detected — using dedicated handler")
            update_status_banner(page, 'info', '🌌 Auto-Applier: Filling Internshala application...')
            handle_internshala_form(page, profile)
            result = finalize_platform("INTERNSHALA")
            try:
                page.close()
            except Exception:
                pass
            return result

        if "naukri.com" in current_url:
            print("  [PLATFORM] Naukri detected — using dedicated handler")
            update_status_banner(page, 'info', '🌌 Auto-Applier: Filling Naukri application...')
            handle_naukri_form(page, profile)
            result = finalize_platform("NAUKRI")
            try:
                page.close()
            except Exception:
                pass
            return result

        if "linkedin.com/jobs" in current_url:
            print("  [PLATFORM] LinkedIn detected — using Easy Apply handler")
            update_status_banner(page, 'info', '🌌 Auto-Applier: LinkedIn Easy Apply...')
            handle_linkedin_easy_apply(page, profile)
            result = finalize_platform("LINKEDIN")
            try:
                page.close()
            except Exception:
                pass
            return result

        if "weworkremotely.com" in current_url:
            try:
                apply_btn = page.locator("a#apply_paragraph").first
                if apply_btn.is_visible():
                    print("WeWorkRemotely: Found apply container button. Clicking...")
                    update_status_banner(page, 'info', '🌌 Auto-Applier: Redirecting to application form...')
                    apply_btn.click()
                    page.wait_for_timeout(2000)
            except Exception:
                pass
                
        for selector in apply_button_selectors:
            try:
                btn = page.locator(selector).first
                if btn.is_visible() and btn.is_enabled():
                    href = btn.get_attribute("href") or ""
                    if href.startswith("#"):
                        print(f"Anchor click: Clicking button '{selector}' to scroll to form")
                        update_status_banner(page, 'info', '🌌 Auto-Applier: Scrolling to form...')
                        btn.click()
                        page.wait_for_timeout(1500)
                    else:
                        print(f"Clicking apply redirect/scroll button matching '{selector}'")
                        update_status_banner(page, 'info', '🌌 Auto-Applier: Navigating to company application site...')
                        btn.click()
                        page.wait_for_timeout(3000)
                    break
            except Exception:
                pass
                
        page_title = page.title()
        company_name = job.get('company', 'Tech Company')
        job_title = job.get('title', 'Software Engineer')
        
        update_status_banner(page, 'info', f'🌌 Auto-Applier: Pre-filling {job_title} at {company_name}...')
        autofill_form(page, profile, wait_first=False)

        update_status_banner(page, 'info', '🌌 Auto-Applier: Filling custom & EEO fields...')
        fill_custom_fields_with_saved_responses(page, profile, company_name, job_title)

        # Final sweep — fill any remaining required fields (Gemini fallback)
        update_status_banner(page, 'info', '🌌 Auto-Applier: Final pass on required fields...')
        fill_required_fields_last_pass(page, profile)

        update_status_banner(page, 'info', '🌌 Auto-Applier: Submitting application...')
        url_before = page.url
        submitted = auto_submit_form(page)

        if submitted:
            # If validation errors remain, do one more fill + retry submit
            if check_validation_errors(page):
                print("Validation errors detected — doing one more fill pass and retrying submit...")
                update_status_banner(page, 'info', '🌌 Auto-Applier: Fixing validation errors, resubmitting...')
                fill_required_fields_last_pass(page, profile)
                page.wait_for_timeout(1000)
                auto_submit_form(page)

            page.wait_for_timeout(2000)

            # Determine success: URL changed OR no validation errors on page
            url_after = page.url
            navigated_away = (url_after != url_before)
            has_errors = check_validation_errors(page)
            success = verify_submission_success(page) or (navigated_away and not has_errors) or (not has_errors and submitted)

            screenshot_path = save_success_screenshot(page, job)
            if success:
                print(f"Applied: {job_title} at {company_name}")
                update_status_banner(page, 'success', f'🌌 Applied: {job_title} at {company_name}!')
                job['status'] = 'Applied'
                save_jobs(all_jobs)
                page.wait_for_timeout(2000)
                try:
                    page.close()
                except Exception:
                    pass
                return True
            else:
                print(f"Submitted (unverified): {job_title} at {company_name}")
                update_status_banner(page, 'info', f'🌌 Submitted (check manually): {job_title}')
                job['status'] = 'Applied'
                save_jobs(all_jobs)
                try:
                    page.close()
                except Exception:
                    pass
                return True
        else:
            print(f"No submit button found for {job_title} at {company_name}.")
            update_status_banner(page, 'error', '🌌 Auto-Applier: No submit button found.')
            job['status'] = 'Review Required'
            save_jobs(all_jobs)
            return False
            
    except Exception as e:
        print(f"Error in handle_redirection_and_apply: {e}")
        try:
            update_status_banner(page, 'error', f'🌌 Auto-Applier: Error: {str(e)[:50]}')
        except Exception:
            pass
        job['status'] = 'Review Required'
        save_jobs(all_jobs)
        return False

def apply_to_jobs(job_ids, web_mode=False):
    if not job_ids:
        print("Error: No job IDs provided.")
        return
        
    kill_playwright_browsers()
    
    profile = load_profile()
    jobs = load_jobs()
    
    valid_jobs = []
    for job_id in job_ids:
        job = next((j for j in jobs if j['id'] == job_id), None)
        if job:
            valid_jobs.append(job)
        else:
            print(f"Warning: Job {job_id} not found in database.")
            
    if not valid_jobs:
        print("Error: No valid jobs found to apply.")
        return
        
    print(f"\n==================================================")
    print(f"BATCH APPLYING TO {len(valid_jobs)} JOBS:")
    for job in valid_jobs:
        print(f" - {job['title']} at {job['company']}")
    print(f"==================================================")
    
    resume_path = profile['personal']['resume_path']
    if not os.path.exists(resume_path):
        print("Resume PDF not found. Running generate_resume_pdf.py...")
        os.system("python generate_resume_pdf.py")
        
    user_data_dir = os.path.abspath("./playwright_user_data")
    
    with sync_playwright() as p:
        browser_context = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
            viewport=None,
            args=[
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars"
            ],
            ignore_default_args=["--enable-automation"]
        )
        
        for idx, job in enumerate(valid_jobs):
            print(f"\n[{idx+1}/{len(valid_jobs)}] {job['title']} at {job['company']}")
            page = None
            try:
                # Always open a fresh page for each job so closed pages don't bleed
                if idx == 0 and browser_context.pages:
                    page = browser_context.pages[0]
                else:
                    page = browser_context.new_page()

                def make_autofill_callback(current_page, current_job):
                    return lambda: handle_redirection_and_apply(current_page, profile, current_job, jobs)

                try:
                    page.expose_function("trigger_python_autofill", make_autofill_callback(page, job))
                except Exception:
                    pass

                page.on("framenavigated", lambda frame, p=page: inject_button(p) if frame == p.main_frame else None)
                page.add_init_script("const newProto = navigator.__proto__; delete newProto.webdriver; navigator.__proto__ = newProto;")

                page.goto(job['url'], wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(4000)
                handle_redirection_and_apply(page, profile, job, jobs)
                # Only inject if page is still open
                if not page.is_closed():
                    inject_button(page)
            except Exception as e:
                print(f"  Error on {job['title']}: {e}")
                # Only mark Review Required if status wasn't already set by handle_redirection_and_apply
                if job.get('status') not in ('Applied',):
                    job['status'] = 'Review Required'
                    save_jobs(jobs)
                # Close the page gracefully before continuing to next job
                try:
                    if page and not page.is_closed():
                        page.close()
                except Exception:
                    pass

        print("\nAll jobs processed.")
            
        try:
            browser_context.close()
        except Exception:
            pass

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python autofill_applier.py <job_id1> [job_id2] ... [--web]")
        sys.exit(1)
        
    web_mode = "--web" in sys.argv
    job_ids = [arg for arg in sys.argv[1:] if arg != "--web"]
    apply_to_jobs(job_ids, web_mode=web_mode)

import http.server
import socketserver
import json
import subprocess
import os
import urllib.parse

PORT = int(os.environ.get('PORT', 8000))

class JobApplierHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/api/apply' or self.path.startswith('/api/apply?'):
            # Parse content length
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            
            try:
                data = json.loads(post_data)
                job_ids = data.get('job_ids', [])
                job_id = data.get('job_id')
                
                if job_id and not job_ids:
                    job_ids = [job_id]
                    
                if not job_ids:
                    self.send_error_response(400, "Missing job_id or job_ids")
                    return
                
                print(f"Launching autofill_applier.py for Job IDs: {job_ids}")
                
                # Execute Playwright script as a subprocess with all job IDs (unbuffered)
                subprocess.Popen([sys_python(), "-u", "autofill_applier.py"] + job_ids + ["--web"])
                
                self.send_success_response({"status": "launched", "job_ids": job_ids})
                
            except Exception as e:
                self.send_error_response(500, f"Server error: {str(e)}")
        
        elif self.path == '/api/run-scraper':
            try:
                print("Running job scraper...")
                subprocess.Popen([sys_python(), "job_scraper.py"])
                self.send_success_response({"status": "launched", "message": "Scraper started in background"})
            except Exception as e:
                self.send_error_response(500, str(e))
                
        elif self.path == '/api/save-profile':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            try:
                data = json.loads(post_data)
                
                # Load existing profile to merge
                if os.path.exists('profile.json'):
                    with open('profile.json', 'r') as f:
                        profile = json.load(f)
                else:
                    profile = {"personal": {}}
                
                profile['personal']['full_name'] = data.get('full_name', profile['personal'].get('full_name', ''))
                names = profile['personal']['full_name'].split()
                profile['personal']['first_name'] = names[0] if names else ""
                profile['personal']['last_name'] = names[-1] if len(names) > 1 else ""
                profile['personal']['email'] = data.get('email', profile['personal'].get('email', ''))
                profile['personal']['phone'] = data.get('phone', profile['personal'].get('phone', ''))
                profile['personal']['location'] = data.get('location', profile['personal'].get('location', ''))
                profile['personal']['linkedin'] = data.get('linkedin', profile['personal'].get('linkedin', ''))
                profile['personal']['github'] = data.get('github', profile['personal'].get('github', ''))
                profile['personal']['resume_path'] = data.get('resume_path', profile['personal'].get('resume_path', ''))
                
                # Dynamically save any custom responses prefixed with 'custom_'
                if 'custom_responses' not in profile:
                    profile['custom_responses'] = {}
                for key, val in data.items():
                    if key.startswith('custom_'):
                        response_key = key[7:]  # remove 'custom_'
                        profile['custom_responses'][response_key] = val
                
                # Save custom keywords dict
                profile['custom_keywords'] = data.get('custom_keywords', profile.get('custom_keywords', {}))
                
                with open('profile.json', 'w') as f:
                    json.dump(profile, f, indent=2)
                    
                self.send_success_response({"status": "saved", "message": "Profile saved successfully"})
            except Exception as e:
                self.send_error_response(500, f"Error saving profile: {str(e)}")
                
        elif self.path == '/api/apply-url':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            try:
                data = json.loads(post_data)
                urls = data.get('urls', [])
                if not urls:
                    self.send_error_response(400, "No URLs provided")
                    return

                # Load existing jobs
                if os.path.exists('jobs_database.json'):
                    with open('jobs_database.json', 'r') as f:
                        jobs = json.load(f)
                else:
                    jobs = []

                import time, re, datetime as _dt
                today_str = _dt.date.today().isoformat()
                new_job_ids = []
                for i, url in enumerate(urls[:20]):  # cap at 20
                    url = url.strip()
                    if not url.startswith('http'):
                        continue
                    # Detect platform
                    if 'greenhouse' in url:
                        source = 'Greenhouse Form'
                    elif 'lever.co' in url:
                        source = 'Lever Form'
                    elif 'internshala' in url:
                        source = 'Internshala'
                    elif 'naukri' in url:
                        source = 'Naukri'
                    elif 'linkedin' in url:
                        source = 'LinkedIn'
                    else:
                        source = 'Custom URL'

                    # Extract a company name hint from URL
                    domain_match = re.search(r'https?://(?:www\.)?([^/]+)', url)
                    domain = domain_match.group(1) if domain_match else 'Company'

                    job_id = f"custom_{int(time.time())}_{i}"
                    jobs.append({
                        "id": job_id,
                        "title": "Job Application",
                        "company": domain,
                        "location": "India",
                        "url": url,
                        "description": f"Custom URL application via Quick Apply. Source: {source}",
                        "skills_required": ["Python", "SQL"],
                        "source": "Custom URL",
                        "date_posted": today_str,
                        "status": "Pending",
                        "match_rate": 80
                    })
                    new_job_ids.append(job_id)

                with open('jobs_database.json', 'w') as f:
                    json.dump(jobs, f, indent=2)

                print(f"Quick Apply: launching for {len(new_job_ids)} custom URLs")
                subprocess.Popen([sys_python(), "-u", "autofill_applier.py"] + new_job_ids + ["--web"])
                self.send_success_response({"status": "launched", "job_ids": new_job_ids})
            except Exception as e:
                self.send_error_response(500, f"Error: {str(e)}")

        elif self.path == '/api/parse-resume':
            try:
                import base64, urllib.request as ureq

                # Load profile to get resume path
                if not os.path.exists('profile.json'):
                    self.send_error_response(400, "profile.json not found")
                    return
                with open('profile.json', 'r') as f:
                    profile = json.load(f)

                resume_path = profile.get('personal', {}).get('resume_path', '')
                if not resume_path or not os.path.exists(resume_path):
                    self.send_error_response(400, f"Resume PDF not found at: {resume_path}")
                    return

                api_key = os.environ.get('GEMINI_API_KEY', '')
                if not api_key:
                    self.send_error_response(400, "GEMINI_API_KEY not set")
                    return

                with open(resume_path, 'rb') as f:
                    pdf_b64 = base64.b64encode(f.read()).decode('utf-8')

                prompt = """Extract the following information from this resume PDF and return ONLY a valid JSON object with these exact keys. Fill only what you can find; use empty string for missing fields. Return ONLY the JSON, no markdown, no explanation:
{
  "full_name": "",
  "email": "",
  "phone": "",
  "location": "",
  "city": "",
  "state": "",
  "linkedin": "",
  "github": "",
  "portfolio": "",
  "university_name": "",
  "degree": "",
  "major": "",
  "gpa_cgpa": "",
  "graduation_year": "",
  "years_experience": "",
  "python_experience": "",
  "react_experience": "",
  "sql_experience": "",
  "summary_ai_experience": "",
  "why_join_company": ""
}"""

                payload = {
                    "contents": [{
                        "parts": [
                            {"inline_data": {"mime_type": "application/pdf", "data": pdf_b64}},
                            {"text": prompt}
                        ]
                    }],
                    "generationConfig": {"temperature": 0.1, "maxOutputTokens": 600}
                }

                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent?key={api_key}"
                req = ureq.Request(url, data=json.dumps(payload).encode('utf-8'),
                                   headers={"Content-Type": "application/json"}, method='POST')
                with ureq.urlopen(req, timeout=40) as resp:
                    res_data = json.loads(resp.read().decode('utf-8'))

                text = res_data['candidates'][0]['content']['parts'][0]['text'].strip()
                # Strip markdown fences if present
                if '```' in text:
                    text = text.split('```')[1]
                    if text.startswith('json'):
                        text = text[4:]
                    text = text.strip()

                extracted = json.loads(text)

                # Merge non-empty extracted fields into profile
                personal = profile.setdefault('personal', {})
                field_map = {
                    'full_name': 'full_name', 'email': 'email', 'phone': 'phone',
                    'location': 'location', 'city': 'city', 'state': 'state',
                    'linkedin': 'linkedin', 'github': 'github', 'portfolio': 'portfolio'
                }
                for k, v in field_map.items():
                    if extracted.get(k):
                        personal.setdefault(v, extracted[k])

                custom = profile.setdefault('custom_responses', {})
                custom_map = {
                    'university_name': 'university_name', 'gpa_cgpa': 'gpa_cgpa',
                    'graduation_year': 'graduation_year', 'years_experience': 'years_experience',
                    'python_experience': 'python_experience', 'react_experience': 'react_experience',
                    'sql_experience': 'sql_experience',
                    'summary_ai_experience': 'summary_ai_experience',
                    'why_join_company': 'why_join_company'
                }
                for k, v in custom_map.items():
                    if extracted.get(k):
                        custom.setdefault(v, extracted[k])

                with open('profile.json', 'w') as f:
                    json.dump(profile, f, indent=2)

                print("Resume parsed and profile updated.")
                self.send_success_response(extracted)

            except Exception as e:
                self.send_error_response(500, f"Parse resume error: {str(e)}")

        elif self.path == '/api/answer-question':
            # User provides a canonical answer to an obstacle question.
            # Saves it to profile.custom_keywords (so find_saved_response reuses it)
            # and removes it from pending_questions.json.
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length).decode('utf-8')
            try:
                data = json.loads(post_data)
                q_id = data.get('id')
                answer = data.get('answer', '')
                keyword = (data.get('keyword') or '').strip()

                # Load pending questions
                pending = []
                if os.path.exists('pending_questions.json'):
                    with open('pending_questions.json', 'r', encoding='utf-8') as f:
                        pending = json.load(f)

                matched = next((q for q in pending if q.get('id') == q_id), None)
                if not matched:
                    self.send_error_response(404, "Question not found")
                    return

                # Use provided keyword, else derive from the question text
                if not keyword:
                    keyword = matched.get('question', '')[:80]

                # Save to profile.custom_keywords for automatic reuse
                if os.path.exists('profile.json'):
                    with open('profile.json', 'r', encoding='utf-8') as f:
                        profile = json.load(f)
                else:
                    profile = {}
                profile.setdefault('custom_keywords', {})
                profile['custom_keywords'][keyword] = answer
                with open('profile.json', 'w', encoding='utf-8') as f:
                    json.dump(profile, f, indent=2)

                # Remove the answered question from pending
                pending = [q for q in pending if q.get('id') != q_id]
                with open('pending_questions.json', 'w', encoding='utf-8') as f:
                    json.dump(pending, f, indent=2)

                self.send_success_response({"status": "saved", "keyword": keyword, "remaining": len(pending)})
            except Exception as e:
                self.send_error_response(500, f"Answer question error: {str(e)}")

        elif self.path == '/api/dismiss-question':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length).decode('utf-8')
            try:
                data = json.loads(post_data)
                q_id = data.get('id')
                pending = []
                if os.path.exists('pending_questions.json'):
                    with open('pending_questions.json', 'r', encoding='utf-8') as f:
                        pending = json.load(f)
                pending = [q for q in pending if q.get('id') != q_id]
                with open('pending_questions.json', 'w', encoding='utf-8') as f:
                    json.dump(pending, f, indent=2)
                self.send_success_response({"status": "dismissed", "remaining": len(pending)})
            except Exception as e:
                self.send_error_response(500, f"Dismiss error: {str(e)}")

        else:
            self.send_error_response(404, "Endpoint not found")

    def do_GET(self):
        # API: list pending obstacle questions
        if self.path.startswith('/api/pending-questions'):
            try:
                pending = []
                if os.path.exists('pending_questions.json'):
                    with open('pending_questions.json', 'r', encoding='utf-8') as f:
                        pending = json.load(f)
                # Sort by most-seen then most-recent
                pending.sort(key=lambda q: (q.get('count', 1), q.get('last_seen', '')), reverse=True)
                self.send_success_response(pending)
            except Exception as e:
                self.send_error_response(500, f"Pending questions error: {str(e)}")
            return
        # Everything else: serve static files (default behavior)
        return super().do_GET()

    def send_success_response(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def send_error_response(self, code, message):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode('utf-8'))

    def do_OPTIONS(self):
        # Support CORS preflight
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

def sys_python():
    # Return correct python executable
    import sys
    return sys.executable

if __name__ == '__main__':
    # Ensure database file exists
    if not os.path.exists('jobs_database.json'):
        print("Jobs database not found. Initializing with empty list...")
        with open('jobs_database.json', 'w') as f:
            json.dump([], f)
            
    print(f"Starting server on http://localhost:{PORT}")
    handler = JobApplierHandler
    # Enable serving from current directory
    with socketserver.TCPServer(("", PORT), handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")

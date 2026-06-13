import http.server
import socketserver
import json
import subprocess
import os
import urllib.parse

PORT = int(os.environ.get('PORT', 8000))

class JobApplierHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path.startswith('/api/apply'):
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
                
        else:
            self.send_error_response(404, "Endpoint not found")

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

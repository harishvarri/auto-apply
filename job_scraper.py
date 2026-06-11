import json
import os
import urllib.parse
import requests
import bs4

def fetch_readme_content(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.0.0 Safari/537.36'
    }
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            return r.text
    except Exception as e:
        print(f"Error fetching from {url}: {e}")
    return None

def parse_readme_to_jobs(readme_text, list_source, user_skills, seen_urls, jobs):
    if not readme_text:
        return
        
    lines = readme_text.split('\n')
    href_pattern = re_href_pattern()
    
    for idx, line in enumerate(lines):
        if '|' in line and not any(h in line for h in ['Company', '---', '===']):
            parts = [p.strip() for p in line.split('|')]
            # Markdown table line: | Company | Position | Location | Posting | Age |
            # Parts after split: ['', 'Company', 'Position', 'Location', 'Posting', 'Age', '']
            if len(parts) >= 6:
                company_html = parts[1]
                position_html = parts[2]
                location_html = parts[3]
                posting_html = parts[4]
                
                # Clean HTML tags from company and position
                company = bs4.BeautifulSoup(company_html, 'html.parser').get_text().strip()
                title = bs4.BeautifulSoup(position_html, 'html.parser').get_text().strip()
                location = bs4.BeautifulSoup(location_html, 'html.parser').get_text().strip()
                
                # Exclude closed postings (marked by lock icon)
                if "🔒" in line:
                    continue
                    
                # Find direct Lever/Greenhouse links in this line
                hrefs = href_pattern.findall(line)
                apply_url = None
                for match in hrefs:
                    url_val = next((g for g in match if g), None)
                    if url_val and ('lever.co' in url_val or 'greenhouse.io' in url_val):
                        apply_url = url_val
                        break
                        
                if not apply_url:
                    continue
                    
                # Standardize and clean URLs
                is_lever = 'jobs.lever.co' in apply_url
                is_greenhouse = 'greenhouse.io' in apply_url
                
                # Clean URL (remove UTM params, query details)
                if '/embed/' in apply_url or 'token=' in apply_url:
                    parsed_u = urllib.parse.urlparse(apply_url)
                    queries_u = urllib.parse.parse_qs(parsed_u.query)
                    token = queries_u.get('token', [''])[0]
                    clean_url = f"https://boards.greenhouse.io/embed/job_app?token={token}"
                else:
                    clean_url = apply_url.split('?')[0]
                
                if is_lever and not clean_url.endswith('/apply'):
                    clean_url = clean_url + '/apply'
                    
                if 'boards.greenhouse.io/embed/job_app' in clean_url and 'token=' not in clean_url:
                    continue
                    
                if clean_url in seen_urls:
                    continue
                    
                seen_urls.add(clean_url)
                
                # Determine relevant skills based on job title
                skills_required = ["Python", "SQL"]
                title_lower = title.lower()
                if any(k in title_lower for k in ["ai", "machine", "ml", "artificial", "intelligence", "deep learning"]):
                    skills_required.extend(["Artificial Intelligence", "Numpy", "Pandas"])
                elif any(k in title_lower for k in ["react", "front", "web", "full-stack", "fullstack", "ui"]):
                    skills_required.extend(["MERN Stack", "Web Programming"])
                elif "django" in title_lower:
                    skills_required.extend(["Django"])
                    
                # Calculate match rate
                matches = len([s for s in skills_required if s in user_skills])
                match_rate = int((matches / len(skills_required)) * 100) if skills_required else 70
                
                # Determine location properties
                loc_lower = location.lower()
                is_india = any(k in loc_lower for k in ['india', 'bengaluru', 'bangalore', 'hyderabad', 'pune', 'mumbai', 'noida', 'gurugram', 'gurgaon', 'chennai'])
                is_remote = 'remote' in loc_lower
                
                # Boost match rate significantly for India/Remote freshers
                if is_india:
                    match_rate = min(match_rate + 25, 100)
                elif is_remote:
                    match_rate = min(match_rate + 20, 100)
                else:
                    # Penalize other locations so India/Remote appear first
                    match_rate = max(match_rate - 30, 45)
                    
                jobs.append({
                    "id": f"real_{len(jobs):03d}",
                    "title": title,
                    "company": company,
                    "location": location,
                    "url": clean_url,
                    "description": f"Direct entry-level software/tech role at {company}. Position: {title} in {location}. Fully automated autofill is ready. Required skills: {', '.join(skills_required)}.",
                    "skills_required": skills_required,
                    "source": "Lever Form" if is_lever else "Greenhouse Form",
                    "date_posted": "June 2026",
                    "status": "Pending",
                    "match_rate": max(match_rate, 45)
                })

def re_href_pattern():
    import re
    return re.compile(r'href="([^"]+)"|href=\'([^\'\s]+)\'|\[[^\]]+\]\((https?://[^\)]+)\)')

def scrape_jobs():
    print("Fetching active 2026 job boards from GitHub repositories...")
    
    # 1. SimplifyJobs US-focused README
    url_simplify = "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/README.md"
    # 2. speedyapply International new grad README
    url_speedy = "https://raw.githubusercontent.com/speedyapply/2026-SWE-College-Jobs/main/NEW_GRAD_INTL.md"
    
    user_skills = ["Python", "C++", "C", "SQL", "Power BI", "Excel", "Pandas", "Numpy", "Data Cleaning", 
                   "Django", "MERN Stack", "Artificial Intelligence", "Web Programming", "Supabase", "Github", "Vercel"]
    
    seen_urls = set()
    jobs = []
    
    print(" -> Fetching SimplifyJobs US-focused Grad Board...")
    simplify_text = fetch_readme_content(url_simplify)
    parse_readme_to_jobs(simplify_text, "SimplifyJobs", user_skills, seen_urls, jobs)
    
    print(" -> Fetching speedyapply International Grad Board...")
    speedy_text = fetch_readme_content(url_speedy)
    parse_readme_to_jobs(speedy_text, "speedyapply", user_skills, seen_urls, jobs)
    
    # Sort consolidated list by match rate descending so related jobs appear first!
    jobs.sort(key=lambda j: j['match_rate'], reverse=True)
    
    # Re-assign sequential IDs after sorting
    for idx, job in enumerate(jobs):
        job['id'] = f"real_{idx:03d}"
        
    # Save the database
    with open('jobs_database.json', 'w') as f:
        json.dump(jobs, f, indent=2)
        
    print(f"Database finalized. Found and saved {len(jobs)} active, real Greenhouse and Lever job listings.")

if __name__ == '__main__':
    scrape_jobs()

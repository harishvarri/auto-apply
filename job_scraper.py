import json
import os
import re
import urllib.parse
import datetime
import requests
import bs4

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'


def today_iso():
    return datetime.date.today().isoformat()


def parse_relative_date(text):
    """Convert 'Posted 3 days ago' / 'today' / '2 weeks ago' into an ISO date string."""
    if not text:
        return today_iso()
    t = text.lower().strip()
    today = datetime.date.today()
    if 'just now' in t or 'today' in t or 'few hours' in t or 'hour' in t or 'minute' in t:
        return today.isoformat()
    if 'yesterday' in t:
        return (today - datetime.timedelta(days=1)).isoformat()
    m = re.search(r'(\d+)\s*(day|week|month)', t)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        if unit == 'day':
            delta = n
        elif unit == 'week':
            delta = n * 7
        else:  # month
            delta = n * 30
        return (today - datetime.timedelta(days=delta)).isoformat()
    return today_iso()


def normalize_iso_date(value):
    """Normalize various ISO/RFC datetime strings to a YYYY-MM-DD date string."""
    if not value:
        return today_iso()
    try:
        # Handle '2026-06-12', '2026-06-02T13:47:37-04:00', '2026-06-10T18:54:28Z'
        s = str(value).strip()
        return s[:10] if len(s) >= 10 and s[4] == '-' else today_iso()
    except Exception:
        return today_iso()


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
                is_india = any(k in loc_lower for k in ['india', 'bengaluru', 'bangalore', 'hyderabad', 'pune', 'mumbai', 'noida', 'gurugram', 'gurgaon', 'chennai']) and 'indianapolis' not in loc_lower and 'indiana' not in loc_lower
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
                    "date_posted": today_iso(),
                    "status": "Pending",
                    "match_rate": max(match_rate, 45)
                })

def re_href_pattern():
    import re
    return re.compile(r'href="([^"]+)"|href=\'([^\'\s]+)\'|\[[^\]]+\]\((https?://[^\)]+)\)')


def scrape_internshala_jobs(seen_urls, jobs, user_skills):
    """Scrape Internshala India jobs for freshers/new grads."""
    import re
    search_pages = [
        "https://internshala.com/jobs/computer-science-jobs/",
        "https://internshala.com/jobs/software-development-jobs/",
        "https://internshala.com/jobs/data-science-ml-jobs/",
        "https://internshala.com/jobs/python-development-jobs/",
        "https://internshala.com/internships/computer-science-internship/",
        "https://internshala.com/internships/web-development-internship/",
        "https://internshala.com/internships/data-science-internship/",
    ]
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    added = 0
    for page_url in search_pages:
        try:
            r = requests.get(page_url, headers=headers, timeout=15)
            if r.status_code != 200:
                continue
            soup = bs4.BeautifulSoup(r.text, 'html.parser')
            is_internship = '/internship' in page_url
            cards = soup.select('.individual_internship')
            for card in cards:
                try:
                    title_el = card.select_one('.job-internship-name, .profile h3, h3.heading_4_5, .profile a')
                    company_el = card.select_one('.company-name, .company_name, p.company-name, .company_and_premium')
                    location_els = card.select('.row-1-item.locations span, .location_link, .locations span, .job_location, #location_names span')
                    link_el = card.select_one('a.job-title-href, a.view_detail_button, a[href*="/job/detail"], a[href*="/internship/detail"]')
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    company = company_el.get_text(strip=True) if company_el else "Company"
                    # Internshala appends "Actively hiring" to company names — strip it
                    company = company.replace("Actively hiring", "").strip()
                    location = ", ".join(el.get_text(strip=True) for el in location_els) if location_els else "India"
                    if not location or location.strip() == "":
                        location = "India"
                    if "india" not in location.lower():
                        location = location + ", India"
                    href = ""
                    if link_el:
                        href = link_el.get('href', '')
                    if not href:
                        href = card.get('data-href', '') or card.get('data-url', '')
                    if not href:
                        continue
                    if href.startswith('/'):
                        href = 'https://internshala.com' + href
                    if href in seen_urls:
                        continue
                    seen_urls.add(href)
                    # Extract posting date from "Posted X days ago" text
                    card_text = card.get_text(" ", strip=True)
                    dm = re.search(r'(\d+\s*(?:day|days|week|weeks|hour|hours|month|months)\s*ago|just now|today|few hours ago|yesterday)', card_text, re.I)
                    date_posted = parse_relative_date(dm.group(0)) if dm else today_iso()
                    title_lower = title.lower()
                    skills = ["Python", "SQL"]
                    if any(k in title_lower for k in ["react", "front", "web", "ui", "angular", "vue"]):
                        skills.extend(["MERN Stack", "Web Programming"])
                    if any(k in title_lower for k in ["data", "ml", "ai", "machine"]):
                        skills.extend(["Pandas", "Artificial Intelligence"])
                    match_rate = min(75 + len([s for s in skills if s in user_skills]) * 5, 95)
                    jobs.append({
                        "id": f"real_{len(jobs):03d}",
                        "title": ("Intern — " if is_internship else "") + title,
                        "company": company,
                        "location": location,
                        "url": href,
                        "description": f"{'Internship' if is_internship else 'Job'} at {company} on Internshala. Role: {title}. Location: {location}.",
                        "skills_required": skills,
                        "source": "Internshala",
                        "date_posted": date_posted,
                        "status": "Pending",
                        "match_rate": match_rate
                    })
                    added += 1
                except Exception:
                    continue
        except Exception as e:
            print(f"  Internshala scrape error ({page_url[-40:]}): {e}")
    print(f"  -> Internshala: {added} jobs found.")
    return added


def scrape_linkedin_india_jobs(seen_urls, jobs, user_skills):
    """Scrape LinkedIn via the public guest job API (no login, bot-safe)."""
    import time
    # f_E: 1=Internship, 2=Entry, 3=Associate. f_TPR=r2592000 = last 30 days
    keywords = [
        "software engineer", "data scientist", "python developer",
        "machine learning engineer", "frontend developer", "backend developer",
        "full stack developer", "data analyst", "software developer intern",
        "associate software engineer",
    ]
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept': 'text/html,application/xhtml+xml',
    }
    added = 0
    for keyword in keywords:
        kw_enc = keyword.replace(' ', '%20')
        for start in (0, 25, 50):  # paginate up to 75 results per keyword
            try:
                url = (
                    "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
                    f"?keywords={kw_enc}&location=India&f_E=1%2C2%2C3&f_TPR=r2592000&start={start}"
                )
                r = requests.get(url, headers=headers, timeout=15)
                if r.status_code != 200:
                    break
                soup = bs4.BeautifulSoup(r.text, 'html.parser')
                cards = soup.select('li')
                if not cards:
                    break
                page_added = 0
                for card in cards:
                    try:
                        title_el = card.select_one('.base-search-card__title')
                        company_el = card.select_one('.base-search-card__subtitle')
                        location_el = card.select_one('.job-search-card__location')
                        link_el = card.select_one('a.base-card__full-link')
                        if not (title_el and link_el):
                            continue
                        title = title_el.get_text(strip=True)
                        company = company_el.get_text(strip=True) if company_el else "Company"
                        job_location = location_el.get_text(strip=True) if location_el else "India"
                        href = link_el.get('href', '').split('?')[0]
                        if not href or href in seen_urls:
                            continue
                        seen_urls.add(href)
                        # Real posting date from the <time datetime="..."> element
                        time_el = card.select_one('time')
                        date_posted = normalize_iso_date(time_el.get('datetime')) if (time_el and time_el.get('datetime')) else today_iso()
                        title_lower = title.lower()
                        skills = ["Python", "SQL"]
                        if any(k in title_lower for k in ["react", "front", "web", "ui"]):
                            skills.extend(["MERN Stack", "Web Programming"])
                        if any(k in title_lower for k in ["data", "ml", "ai", "machine"]):
                            skills.extend(["Pandas", "Artificial Intelligence"])
                        match_rate = min(72 + len([s for s in skills if s in user_skills]) * 4, 92)
                        jobs.append({
                            "id": f"real_{len(jobs):03d}",
                            "title": title,
                            "company": company,
                            "location": job_location if job_location else "India",
                            "url": href,
                            "description": f"{title} at {company} via LinkedIn. Location: {job_location}.",
                            "skills_required": skills,
                            "source": "LinkedIn",
                            "date_posted": date_posted,
                            "status": "Pending",
                            "match_rate": match_rate
                        })
                        added += 1
                        page_added += 1
                    except Exception:
                        continue
                if page_added == 0:
                    break
                time.sleep(0.6)  # polite delay between guest API calls
            except Exception as e:
                print(f"  LinkedIn scrape error ({keyword} @ {start}): {e}")
                break
    print(f"  -> LinkedIn India: {added} jobs found.")
    return added


def scrape_greenhouse_india_boards(seen_urls, jobs, user_skills):
    """Scrape public Greenhouse company board APIs for India roles.

    Greenhouse exposes a fully public JSON API per company board:
      https://boards-api.greenhouse.io/v1/boards/{slug}/jobs
    No auth, no bot-blocking, real apply URLs (which our autofiller handles),
    and real updated_at dates. We curate a list of companies known to hire in
    India; unknown/closed boards just return 404 and are skipped.
    """
    # Companies with India hiring that use Greenhouse boards. 404s are skipped.
    company_slugs = [
        "postman", "razorpaysoftwareprivatelimited", "gong", "airbnb", "dropbox",
        "stripe", "databricks", "cloudflare", "sumologic", "hashicorp",
        "samsara", "rubrik", "wealthsimple", "twilio", "coursera",
        "mongodb", "atlassian", "snyk", "confluent", "gitlab",
        "nutanix", "freshworksinc", "zscaler", "harness", "chargebee",
        "innovaccer", "browserstack", "postmaninc", "sprinklr", "druva",
    ]
    headers = {'User-Agent': UA, 'Accept': 'application/json'}
    added = 0
    for slug in company_slugs:
        try:
            r = requests.get(
                f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
                headers=headers, timeout=20,
            )
            if not r.ok:
                continue
            board_jobs = r.json().get('jobs', [])
            for j in board_jobs:
                try:
                    loc_name = (j.get('location', {}) or {}).get('name', '') or ''
                    if 'india' not in loc_name.lower() and not any(
                        c in loc_name.lower() for c in
                        ['bengaluru', 'bangalore', 'hyderabad', 'pune', 'mumbai',
                         'noida', 'gurugram', 'gurgaon', 'chennai', 'delhi', 'kolkata']
                    ):
                        continue
                    title = j.get('title', '').strip()
                    href = j.get('absolute_url', '')
                    if not title or not href or href in seen_urls:
                        continue
                    seen_urls.add(href)
                    company = (j.get('company_name') or slug.replace('inc', '').replace('-', ' ')).title()
                    title_lower = title.lower()
                    skills = ["Python", "SQL"]
                    if any(k in title_lower for k in ["react", "front", "web", "ui"]):
                        skills.extend(["MERN Stack", "Web Programming"])
                    if any(k in title_lower for k in ["data", "ml", "ai", "machine"]):
                        skills.extend(["Pandas", "Artificial Intelligence"])
                    match_rate = min(78 + len([s for s in skills if s in user_skills]) * 4, 96)
                    jobs.append({
                        "id": f"real_{len(jobs):03d}",
                        "title": title,
                        "company": company,
                        "location": loc_name if 'india' in loc_name.lower() else (loc_name + ", India"),
                        "url": href,
                        "description": f"{title} at {company} (Greenhouse). Location: {loc_name}.",
                        "skills_required": skills,
                        "source": "Greenhouse Form",
                        "date_posted": normalize_iso_date(j.get('updated_at')),
                        "status": "Pending",
                        "match_rate": match_rate
                    })
                    added += 1
                except Exception:
                    continue
        except Exception:
            continue
    print(f"  -> Greenhouse India boards: {added} jobs found.")
    return added

def scrape_jobs():
    print("Fetching active 2026 job boards from GitHub repositories...")
    
    # 1. SimplifyJobs US-focused README
    url_simplify = "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/README.md"
    # 2. speedyapply International new grad README
    url_speedy = "https://raw.githubusercontent.com/speedyapply/2026-SWE-College-Jobs/main/NEW_GRAD_INTL.md"
    # 3. speedyapply International internship README
    url_speedy_intern = "https://raw.githubusercontent.com/speedyapply/2026-SWE-College-Jobs/main/INTERN_INTL.md"
    # 4. speedyapply International AI new grad README
    url_speedy_ai = "https://raw.githubusercontent.com/speedyapply/2026-AI-College-Jobs/main/NEW_GRAD_INTL.md"
    
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

    print(" -> Fetching speedyapply International Internship Board...")
    speedy_intern_text = fetch_readme_content(url_speedy_intern)
    parse_readme_to_jobs(speedy_intern_text, "speedyapply-intern", user_skills, seen_urls, jobs)

    print(" -> Fetching speedyapply International AI Board...")
    speedy_ai_text = fetch_readme_content(url_speedy_ai)
    parse_readme_to_jobs(speedy_ai_text, "speedyapply-ai", user_skills, seen_urls, jobs)

    print(" -> Scraping Internshala India jobs...")
    scrape_internshala_jobs(seen_urls, jobs, user_skills)

    print(" -> Scraping LinkedIn India jobs...")
    scrape_linkedin_india_jobs(seen_urls, jobs, user_skills)

    print(" -> Scraping Greenhouse India company boards...")
    scrape_greenhouse_india_boards(seen_urls, jobs, user_skills)

    # Preserve Applied / Review Required statuses from any previous run (match by URL).
    # Also keep prior custom_* URL applications so Quick Apply history survives a refresh.
    prior_status = {}
    prior_custom_jobs = []
    if os.path.exists('jobs_database.json'):
        try:
            with open('jobs_database.json', 'r', encoding='utf-8') as f:
                old_jobs = json.load(f)
            for oj in old_jobs:
                if oj.get('url'):
                    prior_status[oj['url']] = oj.get('status', 'Pending')
                if oj.get('source') == 'Custom URL':
                    prior_custom_jobs.append(oj)
        except Exception as e:
            print(f"  (Could not read prior database: {e})")

    # Re-apply preserved statuses
    for job in jobs:
        if job['url'] in prior_status and prior_status[job['url']] in ('Applied', 'Review Required'):
            job['status'] = prior_status[job['url']]

    # Re-attach any prior custom URL applications that aren't already present
    existing_urls = {j['url'] for j in jobs}
    for cj in prior_custom_jobs:
        if cj.get('url') not in existing_urls:
            jobs.append(cj)

    # Sort consolidated list by match rate descending so related jobs appear first!
    jobs.sort(key=lambda j: j['match_rate'], reverse=True)

    # Re-assign sequential IDs after sorting (keep custom_ ids stable)
    for idx, job in enumerate(jobs):
        if not str(job.get('id', '')).startswith('custom_'):
            job['id'] = f"real_{idx:03d}"

    # Save the database
    with open('jobs_database.json', 'w') as f:
        json.dump(jobs, f, indent=2)

    india_count = sum(1 for j in jobs if any(k in j.get('location', '').lower() for k in
                      ['india', 'bengaluru', 'bangalore', 'hyderabad', 'pune', 'mumbai',
                       'noida', 'gurugram', 'gurgaon', 'chennai', 'delhi', 'kolkata']))
    print(f"Database finalized. Saved {len(jobs)} jobs total ({india_count} India-based) "
          f"from Greenhouse, Lever, LinkedIn, Internshala, and Naukri.")

if __name__ == '__main__':
    scrape_jobs()

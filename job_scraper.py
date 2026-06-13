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
                    "date_posted": "June 2026",
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
            is_internship = 'internship' in page_url
            # Internshala uses different card classes for jobs vs internships
            cards = soup.select('.individual_internship') or soup.select('.internship_meta')
            for card in cards:
                try:
                    title_el = card.select_one('.profile h3, .job_title, .profile a')
                    company_el = card.select_one('.company_name a, .company_name')
                    location_els = card.select('.location_link, .locations span, .job_location')
                    link_el = card.select_one('a.view_detail_button, a[href*="/job/detail"], a[href*="/internship/detail"]')
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    company = company_el.get_text(strip=True) if company_el else "Company"
                    location = ", ".join(el.get_text(strip=True) for el in location_els) if location_els else "India"
                    if not location or location.strip() == "":
                        location = "India"
                    if "india" not in location.lower():
                        location = location + ", India"
                    href = ""
                    if link_el:
                        href = link_el.get('href', '')
                    if not href:
                        # Try data-url attribute
                        href = card.get('data-url', '') or card.get('data-href', '')
                    if not href:
                        continue
                    if href.startswith('/'):
                        href = 'https://internshala.com' + href
                    if href in seen_urls:
                        continue
                    seen_urls.add(href)
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
                        "date_posted": "June 2026",
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
    """Scrape LinkedIn public job search for India fresher/entry-level roles."""
    import re, time
    search_queries = [
        ("software engineer", "India", "1,2"),    # Entry + Associate level
        ("data scientist", "India", "1,2"),
        ("python developer", "India", "1,2"),
        ("machine learning engineer", "India", "1,2"),
        ("frontend developer", "India", "1,2"),
    ]
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    added = 0
    for keyword, location, exp_level in search_queries:
        try:
            kw_enc = keyword.replace(' ', '%20')
            loc_enc = location.replace(' ', '%20')
            url = f"https://www.linkedin.com/jobs/search/?keywords={kw_enc}&location={loc_enc}&f_E={exp_level}&f_JT=F,I&sortBy=R"
            r = requests.get(url, headers=headers, timeout=15)
            if r.status_code != 200:
                continue
            soup = bs4.BeautifulSoup(r.text, 'html.parser')
            cards = soup.select('.job-search-card, .base-card')
            for card in cards:
                try:
                    title_el = card.select_one('.base-search-card__title, h3.base-search-card__title')
                    company_el = card.select_one('.base-search-card__subtitle, h4.base-search-card__subtitle')
                    location_el = card.select_one('.job-search-card__location, .base-search-card__metadata span')
                    link_el = card.select_one('a.base-card__full-link, a[data-tracking-control-name="public_jobs_jserp-result_search-card"]')
                    if not (title_el and link_el):
                        continue
                    title = title_el.get_text(strip=True)
                    company = company_el.get_text(strip=True) if company_el else "Company"
                    job_location = location_el.get_text(strip=True) if location_el else location
                    href = link_el.get('href', '').split('?')[0]
                    if not href or href in seen_urls:
                        continue
                    seen_urls.add(href)
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
                        "location": job_location if job_location else location,
                        "url": href,
                        "description": f"{title} at {company} via LinkedIn. Location: {job_location}.",
                        "skills_required": skills,
                        "source": "LinkedIn",
                        "date_posted": "June 2026",
                        "status": "Pending",
                        "match_rate": match_rate
                    })
                    added += 1
                except Exception:
                    continue
            time.sleep(1)  # polite delay between LinkedIn requests
        except Exception as e:
            print(f"  LinkedIn scrape error ({keyword}): {e}")
    print(f"  -> LinkedIn India: {added} jobs found.")
    return added


def scrape_naukri_india_jobs(seen_urls, jobs, user_skills):
    """Scrape Naukri.com India fresher job listings via their public search."""
    import re, urllib.parse
    search_terms = [
        ("software engineer", "0to1"),
        ("python developer", "0to1"),
        ("data analyst", "0to1"),
        ("machine learning engineer", "0to1"),
        ("frontend developer", "0to1"),
    ]
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'application/json',
        'Accept-Language': 'en-US,en;q=0.9',
        'appid': '109',
        'systemid': '109',
    }
    added = 0
    for keyword, experience in search_terms:
        try:
            kw_slug = keyword.replace(' ', '-')
            url = f"https://www.naukri.com/{kw_slug}-jobs-in-india?experience=0"
            r = requests.get(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept-Language': 'en-US,en;q=0.9',
            }, timeout=15)
            if r.status_code != 200:
                continue
            soup = bs4.BeautifulSoup(r.text, 'html.parser')
            # Naukri job cards
            cards = soup.select('article.jobTuple, .job-card, .cust-job-tuple')
            for card in cards:
                try:
                    title_el = card.select_one('.title a, a.title, .jobTitle')
                    company_el = card.select_one('.subTitle.ellipsis a, .company-name, .companyName a')
                    location_el = card.select_one('.ellipsis.locWdth, .location, .jobLocation')
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    company = company_el.get_text(strip=True) if company_el else "Company"
                    job_location = location_el.get_text(strip=True) if location_el else "India"
                    href = title_el.get('href', '')
                    if not href or href in seen_urls:
                        continue
                    if href.startswith('/'):
                        href = 'https://www.naukri.com' + href
                    seen_urls.add(href)
                    title_lower = title.lower()
                    skills = ["Python", "SQL"]
                    if any(k in title_lower for k in ["react", "front", "web"]):
                        skills.extend(["MERN Stack"])
                    if any(k in title_lower for k in ["data", "ml", "ai"]):
                        skills.extend(["Pandas", "Artificial Intelligence"])
                    match_rate = min(70 + len([s for s in skills if s in user_skills]) * 4, 90)
                    jobs.append({
                        "id": f"real_{len(jobs):03d}",
                        "title": title,
                        "company": company,
                        "location": job_location + (", India" if "india" not in job_location.lower() else ""),
                        "url": href,
                        "description": f"{title} at {company} via Naukri.com. Location: {job_location}.",
                        "skills_required": skills,
                        "source": "Naukri",
                        "date_posted": "June 2026",
                        "status": "Pending",
                        "match_rate": match_rate
                    })
                    added += 1
                except Exception:
                    continue
        except Exception as e:
            print(f"  Naukri scrape error ({keyword}): {e}")
    print(f"  -> Naukri: {added} jobs found.")
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

    print(" -> Scraping Naukri India jobs...")
    scrape_naukri_india_jobs(seen_urls, jobs, user_skills)

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

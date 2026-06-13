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
                            "date_posted": "June 2026",
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


def scrape_naukri_india_jobs(seen_urls, jobs, user_skills):
    """Scrape Naukri.com India fresher jobs. Tries JSON API first, falls back to Playwright stealth browser."""
    # Naukri blocks plain requests (HTTP 406) and renders cards via JS, so we
    # use a headless stealth Playwright browser with a fresh temp profile.
    search_slugs = [
        "software-engineer", "python-developer", "data-analyst",
        "machine-learning-engineer", "frontend-developer",
        "software-developer", "data-scientist",
    ]
    added = 0
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("  -> Naukri: Playwright not available, skipping.")
        return 0

    import tempfile
    tmp_profile = os.path.join(tempfile.gettempdir(), "naukri_scrape_profile")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                    "--no-sandbox",
                ],
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1366, "height": 900},
                locale="en-IN",
            )
            context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
            page = context.new_page()
            for slug in search_slugs:
                try:
                    url = f"https://www.naukri.com/{slug}-jobs-in-india?experience=0"
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(3500)  # let JS render the cards
                    # Naukri job cards (class names change periodically — use broad selectors)
                    cards = page.query_selector_all("div.srp-jobtuple-wrapper, article.jobTuple, .cust-job-tuple")
                    for card in cards:
                        try:
                            title_el = card.query_selector("a.title")
                            company_el = card.query_selector("a.comp-name, .companyInfo .subTitle, a.subTitle")
                            location_el = card.query_selector("span.locWdth, .loc span, .ellipsis.fleft.locWdth")
                            if not title_el:
                                continue
                            title = (title_el.inner_text() or "").strip()
                            company = (company_el.inner_text() or "").strip() if company_el else "Company"
                            job_location = (location_el.inner_text() or "").strip() if location_el else "India"
                            href = title_el.get_attribute("href") or ""
                            if not href or href in seen_urls:
                                continue
                            seen_urls.add(href)
                            title_lower = title.lower()
                            skills = ["Python", "SQL"]
                            if any(k in title_lower for k in ["react", "front", "web"]):
                                skills.append("MERN Stack")
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
                    print(f"  Naukri page error ({slug}): {e}")
            try:
                context.close()
                browser.close()
            except Exception:
                pass
    except Exception as e:
        print(f"  Naukri Playwright error: {e}")
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

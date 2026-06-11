import requests
import re
import bs4

def test():
    url = "https://raw.githubusercontent.com/speedyapply/2026-SWE-College-Jobs/main/NEW_GRAD_INTL.md"
    text = requests.get(url).text
    
    lines = text.split('\n')
    print("Total lines in markdown:", len(lines))
    
    lever_greenhouse_matches = []
    india_count = 0
    remote_count = 0
    
    # Regex to find href in HTML anchor tag
    href_pattern = re.compile(r'href="([^"]+)"')
    
    for idx, line in enumerate(lines):
        if '|' in line and not any(h in line for h in ['Company', '---', '===']):
            # Split by |
            parts = [p.strip() for p in line.split('|')]
            # Markdown table line: | Company | Position | Location | Posting | Age |
            # Parts after split: ['', 'Company', 'Position', 'Location', 'Posting', 'Age', '']
            if len(parts) >= 6:
                company_html = parts[1]
                position = parts[2]
                location = parts[3]
                posting_html = parts[4]
                
                # Clean company name from HTML
                company = bs4.BeautifulSoup(company_html, 'html.parser').get_text().strip()
                
                # Check for links in parts[4] (Posting) or parts[1] (Company) or parts[2] (Position)
                hrefs = href_pattern.findall(line)
                
                for href in hrefs:
                    if 'lever.co' in href or 'greenhouse.io' in href:
                        loc_lower = location.lower()
                        is_india = any(k in loc_lower for k in ['india', 'bengaluru', 'hyderabad', 'pune', 'mumbai', 'noida', 'chennai', 'gurgaon'])
                        is_remote = 'remote' in loc_lower
                        
                        if is_india or is_remote:
                            lever_greenhouse_matches.append((idx+1, company, position, location, href))
                            if is_india:
                                india_count += 1
                            if is_remote:
                                remote_count += 1
                            break # Only need one link per row
                            
    print(f"Found {len(lever_greenhouse_matches)} Greenhouse/Lever links for India/Remote in international repo.")
    print(f"India: {india_count}, Remote: {remote_count}")
    for idx, (line_num, comp, pos, loc, url_val) in enumerate(lever_greenhouse_matches[:30]):
        print(f"[{idx+1}] Line {line_num}: Company='{comp}' | Position='{pos}' | Location='{loc}' | URL='{url_val}'")

if __name__ == '__main__':
    test()

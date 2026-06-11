import urllib.parse
import requests
from bs4 import BeautifulSoup

def test():
    queries = [
        'site:jobs.lever.co Bengaluru',
        'site:jobs.lever.co Hyderabad',
        'site:boards.greenhouse.io Bengaluru',
        'site:boards.greenhouse.io Hyderabad'
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.0.0 Safari/537.36'
    }
    
    for q in queries:
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(q)}"
        try:
            r = requests.get(url, headers=headers, timeout=10)
            print(f"\nQuery: {q} | Status: {r.status_code}")
            if r.status_code == 200:
                soup = BeautifulSoup(r.content, 'html.parser')
                links = soup.find_all('a', class_='result__url')
                print(f"Found {len(links)} class='result__url' links:")
                for l in links[:5]:
                    print("  ", l.text.strip(), " | ", l.get('href'))
                
                snippets = soup.find_all('a', class_='result__snippet')
                print(f"Found {len(snippets)} class='result__snippet' links:")
                for s in snippets[:5]:
                    print("  ", s.get('href'))
        except Exception as e:
            print("Error:", e)

if __name__ == '__main__':
    test()

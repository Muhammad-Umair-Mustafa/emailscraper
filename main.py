from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, urlparse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

app = FastAPI()

class ScrapeRequest(BaseModel):
    url: str

def extract_emails(text):
    email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    return list(set(re.findall(email_pattern, text)))

def scrape_website(url, depth=1):
    try:
        visited = set()
        emails = set()
        urls_to_scrape = [url]

        for _ in range(depth):  # Control depth to avoid infinite loops
            new_urls = []
            for current_url in urls_to_scrape:
                if current_url in visited:
                    continue
                visited.add(current_url)

                response = requests.get(current_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
                soup = BeautifulSoup(response.text, "html.parser")
                emails.update(extract_emails(soup.get_text()))

                # Extract internal links
                for link in soup.find_all("a", href=True):
                    full_url = urljoin(url, link["href"])
                    parsed_main = urlparse(url).netloc
                    parsed_link = urlparse(full_url).netloc

                    if parsed_main == parsed_link and full_url not in visited:
                        new_urls.append(full_url)

            urls_to_scrape = new_urls  # Move to next depth level
        
        # Also check common contact pages
        common_paths = ["/contact", "/about", "/support", "/help"]
        for path in common_paths:
            full_url = urljoin(url, path)
            emails.update(scrape_website(full_url, depth=0))
        
        return list(emails)
    except requests.RequestException:
        return []

def scrape_js_website(url):
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")  # Run in headless mode
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    driver.get(url)
    page_source = driver.page_source
    driver.quit()

    emails = extract_emails(page_source)
    return emails

@app.post("/scrape")
def scrape(request: ScrapeRequest):
    emails = scrape_website(request.url)
    if not emails:
        # Try using Selenium for JavaScript-heavy websites
        emails = scrape_js_website(request.url)
    
    if not emails:
        raise HTTPException(status_code=404, detail="No emails found.")
    return {"emails": emails}

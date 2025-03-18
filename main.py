from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, urlparse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time

app = FastAPI()

class ScrapeRequest(BaseModel):
    url: str
    max_depth: int = 3  # You can adjust this depth to crawl more pages

def extract_emails(text):
    """Extracts email addresses using regex."""
    email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    return set(re.findall(email_pattern, text))

def is_internal_url(base, target):
    """Check if target URL is internal (same domain as base)."""
    base_domain = urlparse(base).netloc
    target_domain = urlparse(target).netloc
    return base_domain == target_domain

def crawl_website(start_url, max_depth):
    """Crawls the website breadth-first up to max_depth to collect emails."""
    visited = set()
    emails_found = set()
    queue = [(start_url, 0)]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    
    while queue:
        current_url, depth = queue.pop(0)
        if current_url in visited or depth > max_depth:
            continue
        visited.add(current_url)
        print(f"Crawling: {current_url} at depth {depth}")
        try:
            response = requests.get(current_url, timeout=10, headers=headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            page_text = soup.get_text(separator=" ", strip=True)
            emails_found.update(extract_emails(page_text))
            
            # Enqueue internal links
            for link in soup.find_all("a", href=True):
                full_url = urljoin(current_url, link["href"])
                if is_internal_url(start_url, full_url) and full_url not in visited:
                    queue.append((full_url, depth + 1))
            
            # Also try common pages if not visited (e.g., /contact, /about)
            for suffix in ["/contact", "/about", "/support", "/help"]:
                common_url = urljoin(start_url, suffix)
                if common_url not in visited:
                    queue.append((common_url, depth + 1))
                    
        except Exception as e:
            print(f"Error fetching {current_url}: {e}")
            # If a page fails, attempt to use Selenium as a fallback
            selenium_emails = scrape_js_website(current_url)
            if selenium_emails:
                emails_found.update(selenium_emails)
    return emails_found

def scrape_js_website(url):
    """Uses Selenium (with Chromium) to scrape a page that might use JavaScript."""
    try:
        options = webdriver.ChromeOptions()
        # Use the Chromium binary installed on Render (ensure it's installed via your build script)
        options.binary_location = "/usr/bin/chromium"  
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        driver.get(url)
        # Wait for dynamic content to load
        time.sleep(3)
        page_source = driver.page_source
        driver.quit()

        return extract_emails(page_source)
    except Exception as e:
        print(f"Selenium Error for {url}: {e}")
        return set()

@app.post("/scrape")
def scrape(request: ScrapeRequest):
    try:
        print(f"Starting crawl for: {request.url} with max_depth={request.max_depth}")
        emails = crawl_website(request.url, request.max_depth)
        if not emails:
            print("No emails found via crawl. Trying Selenium on the main page...")
            emails = scrape_js_website(request.url)
        if not emails:
            raise HTTPException(status_code=404, detail="No emails found.")
        print(f"Found emails: {emails}")
        return {"emails": list(emails)}
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

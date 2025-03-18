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

def scrape_website(url, depth=1, visited=None):
    if visited is None:
        visited = set()
    
    if url in visited or depth <= 0:
        return set()
    
    visited.add(url)
    
    try:
        emails = set()
        response = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(response.text, "html.parser")
        emails.update(extract_emails(soup.get_text()))

        new_urls = []
        for link in soup.find_all("a", href=True):
            full_url = urljoin(url, link["href"])
            parsed_main = urlparse(url).netloc
            parsed_link = urlparse(full_url).netloc

            if parsed_main == parsed_link and full_url not in visited:
                new_urls.append(full_url)

        for new_url in new_urls:
            emails.update(scrape_website(new_url, depth - 1, visited))

        return emails
    except requests.RequestException:
        return set()

def scrape_js_website(url):
    try:
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        driver.get(url)
        page_source = driver.page_source
        driver.quit()

        emails = extract_emails(page_source)
        return emails
    except Exception as e:
        print(f"Selenium Error: {e}")
        return []

@app.post("/scrape")
def scrape(request: ScrapeRequest):
    try:
        print(f"Scraping URL: {request.url}")

        emails = scrape_website(request.url)
        if not emails:
            print("Trying JavaScript Scraper...")
            emails = scrape_js_website(request.url)

        if not emails:
            raise HTTPException(status_code=404, detail="No emails found.")

        print(f"Found emails: {emails}")
        return {"emails": emails}

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

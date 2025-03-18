from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin

app = FastAPI()

class ScrapeRequest(BaseModel):
    url: str

def extract_emails(text):
    email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    return list(set(re.findall(email_pattern, text)))

def scrape_website(url):
    try:
        response = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        emails = extract_emails(soup.get_text())
        
        # Extract emails from linked pages (optional, uncomment if needed)
        # for link in soup.find_all("a", href=True):
        #     full_url = urljoin(url, link['href'])
        #     try:
        #         sub_response = requests.get(full_url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
        #         emails.extend(extract_emails(sub_response.text))
        #     except:
        #         pass
        
        return list(set(emails))
    except requests.RequestException:
        return []

@app.post("/scrape")
def scrape(request: ScrapeRequest):
    emails = scrape_website(request.url)
    if not emails:
        raise HTTPException(status_code=404, detail="No emails found.")
    return {"emails": emails}

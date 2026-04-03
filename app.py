import os
import asyncio
import random
import base64
import json
import io
import aiohttp
from collections import deque
from bs4 import BeautifulSoup
from telegram import Bot
from telegram.constants import ParseMode
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

# --- CONFIG ---
TG_TOKEN = os.getenv("TG_TOKEN")
CH_ID = os.getenv("CH_ID")
LINKVERTISE_ID = os.getenv("LINKVERTISE_ID")
GDRIVE_JSON = os.getenv("GDRIVE_JSON")
FILE_NAME = "posted_news.txt"

posted_urls = deque(maxlen=5000)

# --- 45+ ELITE SOURCES ---
SCRAPE_TARGETS = [
    {"url": "https://www.reuters.com/world/", "tag": "h3", "name": "Reuters"},
    {"url": "https://apnews.com/hub/world-news", "tag": "h3", "name": "Associated Press"},
    {"url": "https://www.bloomberg.com/world", "tag": "h2", "name": "Bloomberg"},
    {"url": "https://www.bbc.com/news/world", "tag": "h2", "name": "BBC World"},
    {"url": "https://www.dw.com/en/world/s-1429", "tag": "h2", "name": "DW News"},
    {"url": "https://www.aljazeera.com/news/", "tag": "h3", "name": "Al Jazeera"},
    {"url": "https://www.nytimes.com/section/world", "tag": "h2", "name": "NY Times"},
    {"url": "https://www.thehindu.com/news/national/", "tag": "h3", "name": "The Hindu"},
    {"url": "https://www.ndtv.com/india", "tag": "h2", "name": "NDTV"},
    {"url": "https://techcrunch.com/", "tag": "h2", "name": "TechCrunch"},
    {"url": "https://www.theverge.com/", "tag": "h2", "name": "The Verge"},
    {"url": "https://hackaday.com/", "tag": "h2", "name": "Hackaday"},
    {"url": "https://arstechnica.com/", "tag": "h2", "name": "Ars Technica"},
    {"url": "https://www.japantimes.co.jp/news/national/", "tag": "h2", "name": "Japan Times"},
    {"url": "https://indianexpress.com/section/india/", "tag": "h2", "name": "Indian Express"},
    {"url": "https://www.theguardian.com/world", "tag": "h3", "name": "The Guardian"}
]

# --- GOOGLE DRIVE CORE ---
def get_gdrive():
    return build('drive', 'v3', credentials=Credentials.from_service_account_info(json.loads(GDRIVE_JSON)))

def sync_drive():
    try:
        service = get_gdrive()
        res = service.files().list(q=f"name='{FILE_NAME}'", fields="files(id)").execute()
        files = res.get('files', [])
        if not files:
            meta = {'name': FILE_NAME, 'mimeType': 'text/plain'}
            media = MediaFileUpload(io.BytesIO(b""), mimetype='text/plain')
            f = service.files().create(body=meta, media_body=media, fields='id').execute()
            return f['id'], []
        fid = files[0]['id']
        req = service.files().get_media(fileId=fid)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, req)
        done = False
        while not done: _, done = downloader.next_chunk()
        return fid, fh.getvalue().decode().splitlines()
    except: return None, []

def update_drive(fid, urls):
    try:
        service = get_gdrive()
        media = MediaFileUpload(io.BytesIO("\n".join(urls).encode()), mimetype='text/plain')
        service.files().update(fileId=fid, media_body=media).execute()
    except: pass

# --- SCRAPER & BOT ---
def monetize(url):
    b64 = base64.b64encode(url.encode()).decode()
    return f"https://link-to.net/{LINKVERTISE_ID}/{random.random()}/dynamic?r={b64}"

async def scrape(session, target):
    ua = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        async with session.get(target["url"], timeout=15, headers=ua) as r:
            soup = BeautifulSoup(await r.text(), 'html.parser')
            headlines = soup.find_all(target["tag"], limit=10)
            random.shuffle(headlines)
            for h in headlines:
                title = h.get_text().strip()
                link_tag = h.find_parent('a') or h.find('a')
                if not link_tag or not link_tag.get('href'): continue
                link = link_tag['href']
                if not link.startswith('http'):
                    link = f"https://{target['url'].split('/')[2]}/{link.lstrip('/')}"
                
                if link not in posted_urls and len(title) > 40:
                    img = None
                    try:
                        async with session.get(link, timeout=7, headers=ua) as ar:
                            asoup = BeautifulSoup(await ar.text(), 'html.parser')
                            m = asoup.find("meta", property="og:image") or asoup.find("meta", attrs={"name": "twitter:image"})
                            if m: img = m.get('content')
                    except: pass
                    return {"title": title, "url": link, "source": target['name'], "image": img}
    except: return None

async def main():
    print("🚀 Starting 24/7 Cycle...")
    fid, history = sync_drive()
    posted_urls.extend(history)
    
    bot = Bot(token=TG_TOKEN)
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=5)) as session:
        # Check 15 random sources per 15-minute run
        selection = random.sample(SCRAPE_TARGETS, k=min(len(SCRAPE_TARGETS), 15))
        results = await asyncio.gather(*[scrape(session, s) for s in selection])
        
        fresh_articles = [r for r in results if r]
        
        if fresh_articles:
            print(f"📰 Found {len(fresh_articles)} new stories.")
            for art in fresh_articles:
                short_link = monetize(art['url'])
                msg = f"🚨 **BREAKING**\n\n📰 **{art['title'].upper()}**\n\n🏛️ {art['source']}\n🔗 [READ]({short_link})"
                
                try:
                    if art['image']:
                        await bot.send_photo(CH_ID, art['image'], caption=msg[:1024], parse_mode=ParseMode.MARKDOWN)
                    else:
                        await bot.send_message(CH_ID, msg, parse_mode=ParseMode.MARKDOWN)
                    
                    posted_urls.append(art['url'])
                    print(f"✅ Posted: {art['source']}")
                    await asyncio.sleep(5) # Anti-spam delay
                except Exception as e:
                    print(f"Error: {e}")
            
            update_drive(fid, list(posted_urls))
        else:
            print("💤 No new updates found.")

if __name__ == "__main__":
    asyncio.run(main())

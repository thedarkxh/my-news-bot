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

# --- CONFIG & SECRETS ---
TG_TOKEN = os.getenv("TG_TOKEN")
CH_ID = os.getenv("CH_ID")
LINKVERTISE_ID = os.getenv("LINKVERTISE_ID")
GDRIVE_JSON = os.getenv("GDRIVE_JSON")
FILE_NAME = "posted_news.txt"

# Linked Post Configuration
SECONDARY_LINK = "https://t.me/tedsxh" 
SECONDARY_NAME = "Join Teds Mordare Official"

posted_urls = deque(maxlen=5000)

# --- 45+ ELITE & TRUSTED SOURCES ---
SCRAPE_TARGETS = [
    {"url": "https://www.reuters.com/world/", "tag": "h3", "name": "Reuters"},
    {"url": "https://apnews.com/hub/world-news", "tag": "h3", "name": "Associated Press"},
    {"url": "https://www.bloomberg.com/world", "tag": "h2", "name": "Bloomberg"},
    {"url": "https://www.bbc.com/news/world", "tag": "h2", "name": "BBC World"},
    {"url": "https://www.dw.com/en/world/s-1429", "tag": "h2", "name": "DW News"},
    {"url": "https://www.aljazeera.com/news/", "tag": "h3", "name": "Al Jazeera"},
    {"url": "https://www.nytimes.com/section/world", "tag": "h2", "name": "NY Times"},
    {"url": "https://www.washingtonpost.com/world/", "tag": "h2", "name": "Washington Post"},
    {"url": "https://www.thehindu.com/news/national/", "tag": "h3", "name": "The Hindu"},
    {"url": "https://www.ndtv.com/india", "tag": "h2", "name": "NDTV"},
    {"url": "https://indianexpress.com/section/india/", "tag": "h2", "name": "Indian Express"},
    {"url": "https://techcrunch.com/", "tag": "h2", "name": "TechCrunch"},
    {"url": "https://www.theverge.com/", "tag": "h2", "name": "The Verge"},
    {"url": "https://arstechnica.com/", "tag": "h2", "name": "Ars Technica"},
    {"url": "https://hackaday.com/", "tag": "h2", "name": "Hackaday"},
    {"url": "https://www.japantimes.co.jp/news/national/", "tag": "h2", "name": "Japan Times"},
    {"url": "https://www.scmp.com/news/asia", "tag": "h2", "name": "SCMP"},
    {"url": "https://www.theguardian.com/world", "tag": "h3", "name": "The Guardian"},
    {"url": "https://www.economist.com/latest/", "tag": "h3", "name": "The Economist"},
    {"url": "https://www.wsj.com/news/world", "tag": "h3", "name": "WSJ"},
    {"url": "https://www.ft.com/world", "tag": "h3", "name": "Financial Times"}
    # Note: You can expand this list up to 45+ as long as you follow the {"url", "tag", "name"} format.
]

# --- GOOGLE DRIVE PERSISTENCE ---
def get_gdrive():
    creds = Credentials.from_service_account_info(json.loads(GDRIVE_JSON))
    return build('drive', 'v3', credentials=creds)

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
    except Exception as e:
        print(f"Drive Sync Error: {e}")
        return None, []

def update_drive(fid, urls):
    try:
        service = get_gdrive()
        media = MediaFileUpload(io.BytesIO("\n".join(urls).encode()), mimetype='text/plain')
        service.files().update(fileId=fid, media_body=media).execute()
    except: pass

# --- MONETIZATION & SCRAPING ---
def monetize(url):
    b64 = base64.b64encode(url.encode()).decode()
    # Random float in dynamic URL prevents Linkvertise duplicate link detection
    return f"https://link-to.net/{LINKVERTISE_ID}/{random.random()}/dynamic?r={b64}"

async def scrape(session, target):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        async with session.get(target["url"], timeout=15, headers=headers) as r:
            soup = BeautifulSoup(await r.text(), 'html.parser')
            # Look at top 10 headlines per source
            headlines = soup.find_all(target["tag"], limit=10)
            random.shuffle(headlines)
            for h in headlines:
                title = h.get_text().strip()
                link_tag = h.find_parent('a') or h.find('a')
                if not link_tag or not link_tag.get('href'): continue
                
                link = link_tag['href']
                if not link.startswith('http'):
                    link = f"https://{target['url'].split('/')[2]}/{link.lstrip('/')}"
                
                # Check against history
                if link not in posted_urls and len(title) > 40:
                    img = None
                    try:
                        async with session.get(link, timeout=7, headers=headers) as ar:
                            asoup = BeautifulSoup(await ar.text(), 'html.parser')
                            m = asoup.find("meta", property="og:image") or asoup.find("meta", attrs={"name": "twitter:image"})
                            if m: img = m.get('content')
                    except: pass
                    return {"title": title, "url": link, "source": target['name'], "image": img}
    except: return None

# --- MAIN WORKER ---
async def main():
    print("⏳ Starting Aggressive Pulse Cycle...")
    fid, history = sync_drive()
    posted_urls.extend(history)
    
    bot = Bot(token=TG_TOKEN)
    # limit=10 allows faster concurrent scraping
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=10)) as session:
        # Check EVERY target in the list to catch all news
        tasks = [scrape(session, s) for s in SCRAPE_TARGETS]
        results = await asyncio.gather(*tasks)
        
        fresh_articles = [r for r in results if r]
        
        if fresh_articles:
            print(f"📰 Found {len(fresh_articles)} fresh updates!")
            for art in fresh_articles:
                short_link = monetize(art['url'])
                
                # Formatted Message with Linked Post (CTA)
                msg = (
                    f"🚨 **BREAKING NEWS**\n\n"
                    f"📰 **{art['title'].upper()}**\n\n"
                    f"🏛️ Source: {art['source']}\n"
                    f"🔗 [READ FULL STORY]({short_link})\n\n"
                    f"📢 **RELATED:** [{SECONDARY_NAME}]({SECONDARY_LINK})"
                )
                
                try:
                    if art['image']:
                        await bot.send_photo(CH_ID, art['image'], caption=msg[:1024], parse_mode=ParseMode.MARKDOWN)
                    else:
                        await bot.send_message(CH_ID, text=msg, parse_mode=ParseMode.MARKDOWN)
                    
                    # Update local memory
                    posted_urls.append(art['url'])
                    print(f"✅ Posted: {art['source']}")
                    # 3s delay to respect Telegram rate limits
                    await asyncio.sleep(3) 
                except Exception as e:
                    print(f"Telegram Error: {e}")
            
            # Final history sync to Drive
            update_drive(fid, list(posted_urls))
        else:
            print("💤 No new news found in this cycle.")

if __name__ == "__main__":
    asyncio.run(main())

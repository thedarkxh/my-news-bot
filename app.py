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

# PASTE YOUR FOLDER ID HERE FROM DRIVE URL
FOLDER_ID = "1msm9na2P31QXYNjA3JNnuPeUW2TD90Oh" 

# Linked Post Config
SECONDARY_LINK = "https://t.me/tedsxh" 
SECONDARY_NAME = "Join Teds Mordare Official"

posted_urls = deque(maxlen=5000)

# --- TARGET SOURCES ---
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
    {"url": "https://arstechnica.com/", "tag": "h2", "name": "Ars Technica"},
    {"url": "https://hackaday.com/", "tag": "h2", "name": "Hackaday"},
    {"url": "https://www.japantimes.co.jp/news/national/", "tag": "h2", "name": "Japan Times"},
    {"url": "https://www.theguardian.com/world", "tag": "h3", "name": "The Guardian"}
]

# --- GOOGLE DRIVE SYNC (FIXED) ---
def get_gdrive():
    creds = Credentials.from_service_account_info(json.loads(GDRIVE_JSON))
    return build('drive', 'v3', credentials=creds)

def sync_drive():
    try:
        service = get_gdrive()
        # Ensure we look ONLY in the specific folder for the txt file
        query = f"name='{FILE_NAME}' and '{FOLDER_ID}' in parents"
        res = service.files().list(q=query, fields="files(id)").execute()
        files = res.get('files', [])
        
        if not files:
            print("📁 File not found in folder. Creating fresh...")
            meta = {'name': FILE_NAME, 'parents': [FOLDER_ID]}
            media = MediaFileUpload(io.BytesIO(b""), mimetype='text/plain')
            f = service.files().create(body=meta, media_body=media, fields='id').execute()
            return f['id'], []
            
        fid = files[0]['id']
        req = service.files().get_media(fileId=fid)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, req)
        done = False
        while not done: _, done = downloader.next_chunk()
        
        history = fh.getvalue().decode().splitlines()
        print(f"✅ Sync Success: {len(history)} URLs loaded from Drive.")
        return fid, history
    except Exception as e:
        print(f"❌ Drive Sync Error: {e}")
        return None, []

def update_drive(fid, urls):
    try:
        service = get_gdrive()
        content = "\n".join(urls)
        media = MediaFileUpload(io.BytesIO(content.encode()), mimetype='text/plain')
        service.files().update(fileId=fid, media_body=media).execute()
        print("💾 Drive History Updated.")
    except Exception as e:
        print(f"❌ Drive Update Failed: {e}")

# --- CORE LOGIC ---
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
    print("🚀 Triggering Pulse Run...")
    fid, history = sync_drive()
    posted_urls.extend(history)
    
    bot = Bot(token=TG_TOKEN)
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=10)) as session:
        # Check all sources to ensure maximum coverage
        tasks = [scrape(session, s) for s in SCRAPE_TARGETS]
        results = await asyncio.gather(*tasks)
        
        fresh_articles = [r for r in results if r]
        
        if fresh_articles:
            # deduplicate batch
            seen_this_run = set()
            unique_articles = []
            for art in fresh_articles:
                if art['url'] not in seen_this_run:
                    unique_articles.append(art)
                    seen_this_run.add(art['url'])

            print(f"📰 Posting {len(unique_articles)} new stories.")
            for art in unique_articles:
                short_link = monetize(art['url'])
                
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
                        await bot.send_message(CH_ID, msg, parse_mode=ParseMode.MARKDOWN)
                    
                    posted_urls.append(art['url'])
                    print(f"✅ Success: {art['source']}")
                    await asyncio.sleep(4) 
                except Exception as e:
                    print(f"❌ Telegram Error: {e}")
            
            update_drive(fid, list(posted_urls))
        else:
            print("💤 No new articles found.")

if __name__ == "__main__":
    asyncio.run(main())

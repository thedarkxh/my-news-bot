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

# Your Folder ID from the screenshot
FOLDER_ID = "1msm9na2P31QXYNjA3JNnuPeUW2TD90Oh" 

# Linked Post Config
SECONDARY_LINK = "https://t.me/tedsxh" 
SECONDARY_NAME = "Join Teds Mordare Official"

# --- GOOGLE DRIVE CORE (RE-ENGINEERED) ---
def get_gdrive():
    creds = Credentials.from_service_account_info(json.loads(GDRIVE_JSON))
    return build('drive', 'v3', credentials=creds)

def sync_drive():
    try:
        service = get_gdrive()
        # Direct query for the file specifically in that folder
        query = f"name='{FILE_NAME}' and '{FOLDER_ID}' in parents and trashed = false"
        res = service.files().list(q=query, fields="files(id)").execute()
        files = res.get('files', [])
        
        if not files:
            print("📁 File not found. Creating a NEW tracking file...")
            meta = {'name': FILE_NAME, 'parents': [FOLDER_ID]}
            media = MediaFileUpload(io.BytesIO(b""), mimetype='text/plain')
            f = service.files().create(body=meta, media_body=media, fields='id').execute()
            return f['id'], []
            
        fid = files[0]['id']
        req = service.files().get_media(fileId=fid)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, req)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        
        # Load and clean history
        content = fh.getvalue().decode('utf-8')
        history = [line.strip() for line in content.splitlines() if line.strip()]
        print(f"📦 Sync Success: Loaded {len(history)} unique URLs.")
        return fid, history
    except Exception as e:
        print(f"❌ DRIVE ERROR: {str(e)}")
        return None, []

def update_drive(fid, urls):
    if not fid: return
    try:
        service = get_gdrive()
        # Keep only the last 1000 URLs to prevent the file from getting too slow
        trimmed_urls = list(dict.fromkeys(urls))[-1000:] 
        content = "\n".join(trimmed_urls)
        media = MediaFileUpload(io.BytesIO(content.encode('utf-8')), mimetype='text/plain')
        service.files().update(fileId=fid, media_body=media).execute()
        print(f"💾 Drive Updated: Saved {len(trimmed_urls)} URLs.")
    except Exception as e:
        print(f"❌ FAILED TO SAVE TO DRIVE: {e}")

# --- SCRAPER LOGIC ---
def monetize(url):
    b64 = base64.b64encode(url.encode()).decode()
    return f"https://link-to.net/{LINKVERTISE_ID}/{random.random()}/dynamic?r={b64}"

async def scrape(session, target, history):
    ua = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        async with session.get(target["url"], timeout=15, headers=ua) as r:
            soup = BeautifulSoup(await r.text(), 'html.parser')
            headlines = soup.find_all(target["tag"], limit=10)
            for h in headlines:
                link_tag = h.find_parent('a') or h.find('a')
                if not link_tag or not link_tag.get('href'): continue
                
                link = link_tag['href']
                if not link.startswith('http'):
                    link = f"https://{target['url'].split('/')[2]}/{link.lstrip('/')}"
                
                # CRITICAL: Duplicate Check
                if link in history: continue
                
                title = h.get_text().strip()
                if len(title) < 35: continue
                
                img = None
                try:
                    async with session.get(link, timeout=5, headers=ua) as ar:
                        asoup = BeautifulSoup(await ar.text(), 'html.parser')
                        m = asoup.find("meta", property="og:image") or asoup.find("meta", attrs={"name": "twitter:image"})
                        if m: img = m.get('content')
                except: pass
                
                return {"title": title, "url": link, "source": target['name'], "image": img}
    except: return None

# --- MAIN ---
async def main():
    fid, history = sync_drive()
    history_set = set(history) # Faster lookup
    
    # Target 45+ Sources (Shortened list for example)
    SCRAPE_TARGETS = [
        {"url": "https://www.reuters.com/world/", "tag": "h3", "name": "Reuters"},
        {"url": "https://apnews.com/hub/world-news", "tag": "h3", "name": "AP News"},
        {"url": "https://www.bloomberg.com/world", "tag": "h2", "name": "Bloomberg"},
        {"url": "https://www.bbc.com/news/world", "tag": "h2", "name": "BBC News"},
        {"url": "https://www.dw.com/en/world/s-1429", "tag": "h2", "name": "DW News"},
        # ... Add your other 40 targets here
    ]

    bot = Bot(token=TG_TOKEN)
    async with aiohttp.ClientSession() as session:
        tasks = [scrape(session, t, history_set) for t in SCRAPE_TARGETS]
        results = await asyncio.gather(*tasks)
        
        fresh_articles = [r for r in results if r]
        if not fresh_articles:
            print("💤 No new news.")
            return

        for art in fresh_articles:
            # Final safety check before posting
            if art['url'] in history_set: continue
            
            msg = (
                f"🚨 **BREAKING NEWS**\n\n"
                f"📰 **{art['title'].upper()}**\n\n"
                f"🏛️ Source: {art['source']}\n"
                f"🔗 [READ FULL STORY]({monetize(art['url'])})\n\n"
                f"📢 **RELATED:** [{SECONDARY_NAME}]({SECONDARY_LINK})"
            )
            
            try:
                if art['image']:
                    await bot.send_photo(CH_ID, art['image'], caption=msg[:1024], parse_mode=ParseMode.MARKDOWN)
                else:
                    await bot.send_message(CH_ID, msg, parse_mode=ParseMode.MARKDOWN)
                
                history.append(art['url'])
                history_set.add(art['url'])
                print(f"✅ Posted: {art['source']}")
                await asyncio.sleep(3) 
            except Exception as e:
                print(f"❌ Telegram Error: {e}")
        
        update_drive(fid, history)

if __name__ == "__main__":
    asyncio.run(main())

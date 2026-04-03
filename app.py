import os
import asyncio
import random
import base64
import json
import io
import aiohttp
from bs4 import BeautifulSoup
from telegram import Bot
from telegram.constants import ParseMode
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload, MediaIoBaseUpload

# --- CONFIG & SECRETS ---
TG_TOKEN = os.getenv("TG_TOKEN")
CH_ID = os.getenv("CH_ID")
LINKVERTISE_ID = os.getenv("LINKVERTISE_ID")
GDRIVE_JSON = os.getenv("GDRIVE_JSON")
FILE_NAME = "posted_news.txt"
FOLDER_ID = "1msm9na2P31QXYNjA3JNnuPeUW2TD90Oh" 

SECONDARY_LINK = "https://t.me/tedsxh" 
SECONDARY_NAME = "Join Teds Mordare Official"

def get_gdrive():
    creds = Credentials.from_service_account_info(json.loads(GDRIVE_JSON))
    return build('drive', 'v3', credentials=creds)

def sync_drive():
    try:
        service = get_gdrive()
        query = f"name='{FILE_NAME}' and trashed = false"
        res = service.files().list(q=query, fields="files(id, name)").execute()
        files = res.get('files', [])
        
        if not files:
            print("⚠️ File not found. Creating a new one...")
            meta = {'name': FILE_NAME, 'parents': [FOLDER_ID]}
            media = MediaIoBaseUpload(io.BytesIO(b""), mimetype='text/plain', resumable=True)
            f = service.files().create(body=meta, media_body=media, fields='id').execute()
            return f['id'], []
            
        fid = files[0]['id']
        print(f"✅ Syncing with File ID: {fid}")
        
        req = service.files().get_media(fileId=fid)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, req)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        
        history = fh.getvalue().decode('utf-8').splitlines()
        history = [line.strip() for line in history if line.strip()]
        print(f"📦 Loaded {len(history)} previous URLs.")
        return fid, history
    except Exception as e:
        print(f"❌ DRIVE SYNC ERROR: {e}")
        return None, []

def update_drive(fid, urls):
    if not fid: return
    try:
        service = get_gdrive()
        # Ensure only unique URLs, keep last 1000 for efficiency
        content = "\n".join(list(dict.fromkeys(urls))[-1000:])
        
        # Use MediaIoBaseUpload instead of MediaFileUpload to fix the BytesIO error
        media = MediaIoBaseUpload(io.BytesIO(content.encode('utf-8')), mimetype='text/plain', resumable=True)
        service.files().update(fileId=fid, media_body=media).execute()
        print("💾 History saved to Drive.")
    except Exception as e:
        print(f"❌ UPDATE ERROR: {e}")

# --- SCRAPER & MONETIZATION ---
def monetize(url):
    b64 = base64.b64encode(url.encode()).decode()
    return f"https://link-to.net/{LINKVERTISE_ID}/{random.random()}/dynamic?r={b64}"

async def scrape(session, target, history_set):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        async with session.get(target["url"], timeout=15, headers=headers) as r:
            soup = BeautifulSoup(await r.text(), 'html.parser')
            headlines = soup.find_all(target["tag"], limit=12)
            for h in headlines:
                link_tag = h.find_parent('a') or h.find('a')
                if not link_tag or not link_tag.get('href'): continue
                
                link = link_tag['href']
                if not link.startswith('http'):
                    link = f"https://{target['url'].split('/')[2]}/{link.lstrip('/')}"
                
                if link in history_set: continue
                
                title = h.get_text().strip()
                if len(title) < 40: continue
                
                img = None
                try:
                    async with session.get(link, timeout=5, headers=headers) as ar:
                        asoup = BeautifulSoup(await ar.text(), 'html.parser')
                        m = asoup.find("meta", property="og:image") or asoup.find("meta", attrs={"name": "twitter:image"})
                        if m: img = m.get('content')
                except: pass
                
                return {"title": title, "url": link, "source": target['name'], "image": img}
    except: return None

async def main():
    fid, history = sync_drive()
    history_set = set(history)
    
    SCRAPE_TARGETS = [
        {"url": "https://www.reuters.com/world/", "tag": "h3", "name": "Reuters"},
        {"url": "https://apnews.com/hub/world-news", "tag": "h3", "name": "AP News"},
        {"url": "https://www.bloomberg.com/world", "tag": "h2", "name": "Bloomberg"},
        {"url": "https://www.bbc.com/news/world", "tag": "h2", "name": "BBC News"},
        {"url": "https://www.dw.com/en/world/s-1429", "tag": "h2", "name": "DW News"},
        {"url": "https://www.thehindu.com/news/national/", "tag": "h3", "name": "The Hindu"},
        {"url": "https://www.ndtv.com/india", "tag": "h2", "name": "NDTV"}
    ]

    bot = Bot(token=TG_TOKEN)
    async with aiohttp.ClientSession() as session:
        results = await asyncio.gather(*[scrape(session, t, history_set) for t in SCRAPE_TARGETS])
        fresh = [r for r in results if r]
        
        if not fresh:
            print("💤 No new content.")
            return

        for art in fresh:
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

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
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

# --- CONFIG & SECRETS ---
TG_TOKEN = os.getenv("TG_TOKEN")
CH_ID = os.getenv("CH_ID")
LINKVERTISE_ID = os.getenv("LINKVERTISE_ID")
GDRIVE_JSON = os.getenv("GDRIVE_JSON")
FILE_NAME = "posted_news.txt"

# Your specific folder ID from Drive
FOLDER_ID = "1msm9na2P31QXYNjA3JNnuPeUW2TD90Oh" 

# CTA for your Telegram channel
SECONDARY_LINK = "https://t.me/tedsxh" 
SECONDARY_NAME = "Join Teds Mordare Official"

# --- GOOGLE DRIVE CORE ---
def get_gdrive():
    creds = Credentials.from_service_account_info(json.loads(GDRIVE_JSON))
    return build('drive', 'v3', credentials=creds)

def sync_drive():
    try:
        service = get_gdrive()
        # Search for the tracking file to prevent duplicates
        query = f"name='{FILE_NAME}' and trashed = false"
        res = service.files().list(q=query, fields="files(id, name)").execute()
        files = res.get('files', [])
        
        if not files:
            print("📁 File not found. Creating a NEW tracking file...")
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
        
        # Load existing URLs into memory
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
        # Keep only the last 1000 unique URLs to maintain speed
        content = "\n".join(list(dict.fromkeys(urls))[-1000:])
        
        # Fixed: Uses MediaIoBaseUpload to avoid PathLike error
        media = MediaIoBaseUpload(io.BytesIO(content.encode('utf-8')), mimetype='text/plain', resumable=True)
        service.files().update(fileId=fid, media_body=media).execute()
        print("💾 History successfully saved to Drive.")
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
            # Scrape up to 12 potential headlines per source
            headlines = soup.find_all(target["tag"], limit=12)
            for h in headlines:
                link_tag = h.find_parent('a') or h.find('a')
                if not link_tag or not link_tag.get('href'): continue
                
                link = link_tag['href']
                if not link.startswith('http'):
                    link = f"https://{target['url'].split('/')[2]}/{link.lstrip('/')}"
                
                # THE DUPLICATE CHECK: Skip if already in Drive history
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

# --- MAIN ENGINE ---
async def main():
    # 1. Start by loading the Drive file to avoid repeats
    fid, history = sync_drive()
    history_set = set(history) # Faster lookup for large lists
    
SCRAPE_TARGETS = [
    {"url": "https://reuters.com", "tag": "h3", "name": "Reuters"},
    {"url": "https://apnews.com", "tag": "h3", "name": "AP News"},
    {"url": "https://bloomberg.com", "tag": "h2", "name": "Bloomberg"},
    {"url": "https://bbc.com", "tag": "h2", "name": "BBC News"},
    {"url": "https://dw.com", "tag": "h2", "name": "DW News"},
    {"url": "https://thehindu.com", "tag": "h3", "name": "The Hindu"},
    {"url": "https://ndtv.com", "tag": "h2", "name": "NDTV"},
    {"url": "https://techcrunch.com", "tag": "h2", "name": "TechCrunch"},
    {"url": "https://nhk.or.jp", "tag": "span", "name": "NHK World-Japan"},
    {"url": "https://japantimes.co.jp", "tag": "h3", "name": "The Japan Times"},
    {"url": "https://scmp.com", "tag": "h2", "name": "South China Morning Post"},
    {"url": "https://news.cn", "tag": "h3", "name": "Xinhua News"},
    {"url": "https://caixinglobal.com", "tag": "h3", "name": "Caixin Global"},
    {"url": "https://meduza.io", "tag": "h3", "name": "Meduza"},
    {"url": "https://themoscowtimes.com", "tag": "h2", "name": "The Moscow Times"},
    {"url": "https://tass.com", "tag": "h3", "name": "TASS News Agency"},
    {"url": "https://tagesschau.de", "tag": "span", "name": "Tagesschau"},
    {"url": "https://spiegel.de", "tag": "h2", "name": "Der Spiegel (International)"},
    {"url": "https://sueddeutsche.de", "tag": "h3", "name": "Süddeutsche Zeitung"},
    {"url": "https://nytimes.com", "tag": "h3", "name": "The New York Times"},
    {"url": "https://washingtonpost.com", "tag": "h2", "name": "The Washington Post"},
    {"url": "https://wsj.com", "tag": "h3", "name": "The Wall Street Journal"},
    {"url": "https://abc.net.au", "tag": "h2", "name": "ABC News (Australia)"},
    {"url": "https://smh.com.au", "tag": "h3", "name": "The Sydney Morning Herald"},
    {"url": "https://theaustralian.com.au", "tag": "h3", "name": "The Australian"},
    {"url": "https://theguardian.com", "tag": "h3", "name": "The Guardian"},
    {"url": "https://thetimes.com", "tag": "h3", "name": "The Times"},
    {"url": "https://cbc.ca", "tag": "h3", "name": "CBC News"},
    {"url": "https://theglobeandmail.com", "tag": "h3", "name": "The Globe and Mail"},
    {"url": "https://nationalpost.com", "tag": "h2", "name": "National Post"},
    {"url": "https://swissinfo.ch", "tag": "h2", "name": "SWI swissinfo.ch"},
    {"url": "https://nzz.ch", "tag": "h2", "name": "Neue Zürcher Zeitung"},
    {"url": "https://letemps.ch", "tag": "h3", "name": "Le Temps"},
    {"url": "https://mainichi.jp", "tag": "h3", "name": "The Mainichi"},
    {"url": "https://nikkei.com", "tag": "h2", "name": "Nikkei Asia"},
    {"url": "https://asahi.com", "tag": "h3", "name": "The Asahi Shimbun (AJW)"},
    # --- 20 NEW RECOMMENDATIONS ---
    # Global & Pan-Regional Powers
    {"url": "https://france24.com", "tag": "h2", "name": "France 24 (English)"},
    {"url": "https://lemonde.fr", "tag": "h3", "name": "Le Monde (English)"},
    {"url": "https://aljazeera.com", "tag": "h2", "name": "Al Jazeera English"},
    {"url": "https://haaretz.com", "tag": "h2", "name": "Haaretz (Israel)"},
    # Northern & Southern Europe
    {"url": "https://elpais.com", "tag": "h2", "name": "El País (Spain)"},
    {"url": "https://corriere.it", "tag": "h3", "name": "Corriere della Sera (Italy)"},
    {"url": "https://thejournal.ie", "tag": "h2", "name": "TheJournal.ie (Ireland)"},
    {"url": "https://yle.fi", "tag": "h3", "name": "YLE News (Finland)"},
    {"url": "https://thelocal.se", "tag": "h2", "name": "The Local Sweden"},
    # Latin America
    {"url": "https://elpais.com", "tag": "h2", "name": "El País Américas"},
    {"url": "https://infobae.com", "tag": "h2", "name": "Infobae (Latin America)"},
    {"url": "https://globo.com", "tag": "h2", "name": "G1 Globo (Brazil)"},
    # Africa
    {"url": "https://news24.com", "tag": "h3", "name": "News24 (South Africa)"},
    {"url": "https://theeastafrican.co.ke", "tag": "h2", "name": "The EastAfrican"},
    {"url": "https://punchng.com", "tag": "h3", "name": "The Punch (Nigeria)"},
    # Asia-Pacific Extensions
    {"url": "https://straitstimes.com", "tag": "h3", "name": "The Straits Times (Singapore)"},
    {"url": "https://channelnewsasia.com", "tag": "h2", "name": "CNA (Channel NewsAsia)"},
    {"url": "https://rnz.co.nz", "tag": "h2", "name": "RNZ (Radio New Zealand)"},
    {"url": "https://koreatimes.co.kr", "tag": "h2", "name": "The Korea Times"},
    {"url": "https://thestar.com.my", "tag": "h2", "name": "The Star (Malaysia)"}
]


    bot = Bot(token=TG_TOKEN)
    async with aiohttp.ClientSession() as session:
        # Run all scraping tasks concurrently
        results = await asyncio.gather(*[scrape(session, t, history_set) for t in SCRAPE_TARGETS])
        fresh = [r for r in results if r]
        
        if not fresh:
            print("💤 All news is currently up to date.")
            return

        for art in fresh:
            # Final safety check before posting to Telegram
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
                
                # Update local history so we don't post it again in the next run
                history.append(art['url'])
                history_set.add(art['url'])
                print(f"✅ Posted: {art['source']}")
                await asyncio.sleep(3) # Anti-spam delay
            except Exception as e:
                print(f"❌ Telegram Error: {e}")
        
        # 2. Save the new history back to Drive
        update_drive(fid, history)

if __name__ == "__main__":
    asyncio.run(main())

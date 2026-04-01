import os
import requests
import google.generativeai as genai
from telegram import Bot
from fastapi import FastAPI
import asyncio

app = FastAPI()

# Cloud Environment Variables
TG_TOKEN = os.getenv("TG_TOKEN")
CH_ID = os.getenv("CH_ID")
NEWS_KEY = os.getenv("NEWS_KEY")
GEMINI_KEY = os.getenv("GEMINI_KEY")

genai.configure(api_key=GEMINI_KEY)
gemini_model = genai.GenerativeModel('gemini-1.5-flash')

async def fetch_and_post():
    # 1. Fetch News (Mainstream Indian Sources)
    domains = "thehindu.com,ndtv.com,timesofindia.indiatimes.com"
    url = f"https://newsapi.org/v2/everything?domains={domains}&pageSize=1&apiKey={NEWS_KEY}"
    data = requests.get(url).json()
    
    if not data.get('articles'): return "No news found"
    article = data['articles'][0]

    # 2. AI Summary
    prompt = f"Summarize this Indian news for a Telegram channel. Use emojis and keep it under 3 bullets: {article['title']} - {article['description']}"
    summary = gemini_model.generate_content(prompt).text

    # 3. Post to Telegram
    bot = Bot(token=TG_TOKEN)
    caption = f"🇮🇳 **{article['title']}**\n\n{summary}\n\n🔗 [Source]({article['url']})"
    
    if article.get('urlToImage'):
        await bot.send_photo(chat_id=CH_ID, photo=article['urlToImage'], caption=caption, parse_mode='Markdown')
    else:
        await bot.send_message(chat_id=CH_ID, text=caption, parse_mode='Markdown')
    return "Posted successfully"

@app.get("/")
async def trigger_bot():
    # This endpoint is what Cron-job.org will hit
    status = await fetch_and_post()
    return {"status": status}

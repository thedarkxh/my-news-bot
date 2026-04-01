import os
import time
import requests
import asyncio
import google.generativeai as genai
from telegram import Bot

# Get secrets from Hugging Face environment
TG_TOKEN = os.getenv("TG_TOKEN")
CH_ID = os.getenv("CH_ID")
NEWS_KEY = os.getenv("NEWS_KEY")
GEMINI_KEY = os.getenv("GEMINI_KEY")

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

async def send_news():
    bot = Bot(token=TG_TOKEN)
    while True:
        try:
            # 1. Fetch News
            url = f"https://newsapi.org/v2/top-headlines?country=in&pageSize=1&apiKey={NEWS_KEY}"
            data = requests.get(url).json()
            article = data['articles'][0]

            # 2. AI Summary
            prompt = f"Summarize this Indian news for Telegram: {article['title']}. Use emojis."
            summary = model.generate_content(prompt).text

            # 3. Post
            caption = f"🇮🇳 **{article['title']}**\n\n{summary}\n\n🔗 [Read More]({article['url']})"
            await bot.send_photo(chat_id=CH_ID, photo=article['urlToImage'], caption=caption, parse_mode='Markdown')
            
            print("News posted! Sleeping for 3 hours...")
            await asyncio.sleep(10800) # Wait 3 hours
            
        except Exception as e:
            print(f"Error: {e}")
            await asyncio.sleep(60) # Retry in a minute if it fails

if __name__ == "__main__":
    asyncio.run(send_news())

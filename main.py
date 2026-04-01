import os
import requests
import google.generativeai as genai
from telegram import Bot
import asyncio

# These will be stored in your Cloud Environment Variables (Safe!)
TG_TOKEN = os.getenv("TG_TOKEN")
CH_ID = os.getenv("CH_ID")
NEWS_KEY = os.getenv("NEWS_KEY")
GEMINI_KEY = os.getenv("GEMINI_KEY")
IMAGE_API_KEY = os.getenv("IMAGE_API_KEY")

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

async def run_bot():
    # 1. Get Indian News
    domains = "thehindu.com,ndtv.com,timesofindia.indiatimes.com"
    url = f"https://newsapi.org/v2/everything?domains={domains}&pageSize=1&apiKey={NEWS_KEY}"
    data = requests.get(url).json()
    article = data['articles'][0]

    # 2. AI Summary
    prompt = f"Summarize this Indian news for Telegram with emojis: {article['title']} - {article['description']}"
    summary = model.generate_content(prompt).text

    # 3. Generate NEW AI Image (Flux Schnell)
    # This makes your bot unique!
    img_resp = requests.post(
        "https://api.pixazo.ai/v1/generate",
        headers={"Authorization": f"Bearer {IMAGE_API_KEY}"},
        json={"prompt": f"Professional news illustration for: {article['title']}", "model": "flux-schnell"}
    ).json()
    ai_img_url = img_resp.get('url')

    # 4. Post
    bot = Bot(token=TG_TOKEN)
    await bot.send_photo(chat_id=CH_ID, photo=ai_img_url, caption=f"🇮🇳 **{article['title']}**\n\n{summary}\n\n🔗 [Read More]({article['url']})", parse_mode='Markdown')

if __name__ == "__main__":
    asyncio.run(run_bot())

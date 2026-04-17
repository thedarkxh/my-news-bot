import os
import asyncio
from instagrapi import Client
# Import your existing generation logic here
# from news_to_gram import create_premium_card 

# --- INSTAGRAM LOGIC ---
def post_to_instagram(image_path, caption):
    username = os.getenv("INSTA_USERNAME")
    password = os.getenv("INSTA_PASSWORD")
    
    cl = Client()
    # Optional: Handle session saving to avoid repetitive logins/blocks
    session_file = "insta_session.json"
    
    try:
        if os.path.exists(session_file):
            cl.load_settings(session_file)
        
        cl.login(username, password)
        cl.dump_settings(session_file)
        
        # Upload photo
        media = cl.photo_upload(image_path, caption)
        print(f"Successfully posted to Instagram! Media ID: {media.pk}")
        return True
    except Exception as e:
        print(f"Error posting to Instagram: {e}")
        return False

# --- THE COMBINED MAIN PIPELINE ---
async def run_automated_pipeline():
    # 1. FETCH (from your my-news-bot logic)
    # headline, brief = fetch_latest_news()
    headline = "New Tech Breakthrough in Tokyo"
    brief = "Researchers have developed a new semiconductor that triples efficiency."
    bg_file = "background.jpg"

    # 2. GENERATE (from News-to-Gram)
    # This creates the 'output/ig_news_card.jpg'
    final_image_path = create_premium_card(headline, brief, bg_file)

    # 3. POST TO TELEGRAM (Existing Logic)
    # await send_to_telegram(final_image_path, headline, brief)

    # 4. POST TO INSTAGRAM (The New Integration)
    insta_caption = f"{headline.upper()}\n\n{brief}\n\n#news #tech #updates"
    post_to_instagram(final_image_path, insta_caption)

if __name__ == "__main__":
    asyncio.run(run_automated_pipeline())

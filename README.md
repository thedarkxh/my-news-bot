# 🚀 Teds Mordare News Bot (@tedsxh)

[![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-24/7_Automation-blue?logo=githubactions&logoColor=white)](https://github.com/features/actions)
[![Python 3.11](https://img.shields.io/badge/Python-3.11-green?logo=python&logoColor=white)](https://www.python.org/)
[![Telegram](https://img.shields.io/badge/Telegram-Channel_Bot-0088cc?logo=telegram&logoColor=white)](https://t.me/tedsxh)

An automated, high-authority news scraper and delivery system designed for the **Teds Mordare** Telegram channel. This bot sources from 45+ elite global news agencies, monetizes links via Linkvertise, and uses Google Drive for persistent memory to ensure zero duplicate posts.

---

## ✨ Features

* **🔍 Elite Scraping:** Monitors 45+ Tier-1 sources (Reuters, AP, Bloomberg, BBC, etc.) for high-factual, low-bias news.
* **🧠 Persistent Memory:** Uses Google Drive API to store a history of posted URLs, preventing duplicates even after server restarts.
* **💰 Auto-Monetization:** Automatically wraps every news link with Linkvertise dynamic aliases.
* **🖼️ Deep Image Scan:** Extracts OpenGraph (OG) and Twitter card images from articles for visually rich Telegram posts.
* **🤖 24/7 Pulse:** Powered by GitHub Actions (Cron) to run every 15 minutes with zero maintenance.

---

## 🛠️ Technology Stack

| Component | Technology |
| :--- | :--- |
| **Language** | Python 3.11 |
| **Automation** | GitHub Actions (Cron) |
| **Database** | Google Drive API (txt-based persistence) |
| **Scraping** | BeautifulSoup4 + Aiohttp |
| **Messaging** | Python-Telegram-Bot (Async) |

---

## 🚀 Setup & Installation

### 1. Repository Secrets
Add the following to your GitHub Repo under **Settings > Secrets and variables > Actions**:

* `TG_TOKEN`: Your Telegram Bot API Token.
* `CH_ID`: Your Telegram Channel ID (e.g., `-100...`).
* `LINKVERTISE_ID`: Your Linkvertise user ID.
* `GDRIVE_JSON`: The full content of your Google Service Account JSON key.

### 2. Google Drive Configuration
1.  Create a folder in Google Drive.
2.  Share the folder with your service account email: `news-bot@news-bot-tg.iam.gserviceaccount.com`.
3.  Ensure the account has **Editor** permissions.

---

## 📁 Project Structure

```text
├── .github/workflows/
│   └── news_bot.yml      # GitHub Actions schedule config
├── app.py                # Main bot logic and scraping engine
├── requirements.txt      # Python dependencies
└── README.md             # Project documentation

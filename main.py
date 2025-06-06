import os
import sys
import json
import requests
import discord
import pytz
from dotenv import load_dotenv
from discord.ext import commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID"))
APIFY_TOKEN = os.getenv("APIFY_TOKEN")

# Apify endpoint and payload
ACTOR_RUN_URL = "https://api.apify.com/v2/acts/apify~instagram-post-scraper/run-sync-get-dataset-items"
payload = {
        "onlyPostsNewerThan": "1 day",
        "skipPinnedPosts": False,
        "username": ["uw.mehfil"]
        }

# JSON file to track sent posts
POSTS_FILE = "sent_posts.json"

def load_sent_post_ids():
    if not os.path.exists(POSTS_FILE):
        return set()
    with open(POSTS_FILE, "r") as f:
        return set(json.load(f))

def save_sent_post_ids(post_ids):
    with open(POSTS_FILE, "w") as f:
        json.dump(list(post_ids), f)

# Discord bot setup
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
scheduler = AsyncIOScheduler(timezone=pytz.timezone("US/Eastern"))

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

    if len(sys.argv) > 1:
        mode = sys.argv[1]
        if mode == "test":
            bot.loop.create_task(run_test_mode())
            return
        elif mode == "send":
            bot.loop.create_task(test_channel_send())
            return

    scheduler.add_job(post_updates, CronTrigger(hour="0,12", minute=0))        # 12AM & 12PM ET
    scheduler.add_job(send_heartbeat, CronTrigger(minute=0, hour="*/2"))       # Every 2 hours
    scheduler.start()

async def run_test_mode():
    print("Running in test mode (last 3 weeks of posts)...")
    test_payload = payload.copy()
    test_payload["onlyPostsNewerThan"] = "21 days"

    try:
        res = requests.post(ACTOR_RUN_URL, params={"token": APIFY_TOKEN}, json=test_payload)
        if res.status_code not in (200, 201):
            raise Exception(f"Apify Error {res.status_code}: {res.text}")

        posts = res.json()
        channel = bot.get_channel(CHANNEL_ID)

        for post in posts:
            caption = post.get("caption", "").strip()
            image_url = post.get("displayUrl", "").strip()
            post_url = post.get("url", "").strip()

            embed = discord.Embed(
                    description=f"{caption}\n\n📎 [More details here]({post_url})",
                    color=0xFFD700
                    )
            if image_url:
                embed.set_image(url=image_url)

            await channel.send(content="@everyone 📣 **New Announcement**", embed=embed)

        await bot.close()

    except Exception as e:
        print("Test mode error:", str(e))
        admin = await bot.fetch_user(ADMIN_USER_ID)
        await admin.send(f"🚨 Error in `run_test_mode()`:\n```{str(e)}```")
        await bot.close()

async def test_channel_send():
    try:
        print("Testing send permissions...")
        channel = await bot.fetch_channel(CHANNEL_ID)
        await channel.send("✅ Test message: Mehfil bot has permission to send messages.")
        print("Send test succeeded.")
        bot.loop.create_task(bot.close())
    except Exception as e:
        print("Send test failed:", str(e))
        admin = await bot.fetch_user(ADMIN_USER_ID)
        await admin.send(f"🚨 Failed to send test message to channel:\n```{str(e)}```")
        bot.loop.create_task(bot.close())

async def post_updates():
    try:
        print("Fetching Instagram posts...")
        res = requests.post(ACTOR_RUN_URL, params={"token": APIFY_TOKEN}, json=payload)
        if res.status_code not in (200, 201):
            raise Exception(f"Apify Error {res.status_code}: {res.text}")

        posts = res.json()
        channel = bot.get_channel(CHANNEL_ID)
        sent_post_ids = load_sent_post_ids()
        new_post_ids = set()

        for post in posts:
            post_id = post.get("id")
            if not post_id or post_id in sent_post_ids:
                continue

            caption = post.get("caption", "").strip()
            image_url = post.get("displayUrl", "").strip()
            post_url = post.get("url", "").strip()

            embed = discord.Embed(
                    description=f"{caption}\n\n📎 [More details here]({post_url})",
                    color=0xFFD700
                    )
            if image_url:
                embed.set_image(url=image_url)

            await channel.send(content="@everyone 📣 **New Announcement**", embed=embed)

            new_post_ids.add(post_id)

        if new_post_ids:
            save_sent_post_ids(sent_post_ids.union(new_post_ids))

    except Exception as e:
        print("Error occurred:", str(e))
        admin = await bot.fetch_user(ADMIN_USER_ID)
        await admin.send(f"🚨 Error in `post_updates()`:\n```{str(e)}```")

async def send_heartbeat():
    try:
        admin = await bot.fetch_user(ADMIN_USER_ID)
        await admin.send("✅ Heartbeat: MehfilBot is alive.")
    except Exception as e:
        print("Failed to send heartbeat:", e)

bot.run(DISCORD_TOKEN)


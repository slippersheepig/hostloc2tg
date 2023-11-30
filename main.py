import requests
import time
import random
import asyncio
import telegram
from dotenv import dotenv_values
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# ...（与现有导入相同）

# ...（与现有配置相同）

async def send_message(msg):
    bot = telegram.Bot(token=BOT_TOKEN)
    await bot.send_message(chat_id=CHANNEL_ID, text=msg, parse_mode='Markdown')

async def parse_post_content(post_link):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(post_link) as response:
                response.raise_for_status()
                html_content = await response.text()

        soup = BeautifulSoup(html_content, 'html.parser')
        post_content_tag = soup.select_one(".t_fsz")

        content = post_content_tag.get_text(strip=True) if post_content_tag else ""
        attachments = soup.select(".pattl+.pattl")
        images = soup.select(".pcb img")

        attachment_urls = [attachment['href'] for attachment in attachments]
        image_urls = [image['file'] for image in images]

        return content, attachment_urls, image_urls

    except (requests.RequestException, ValueError) as e:
        print(f"发生错误: {e}")
        return "", [], []

def parse_relative_time(relative_time_str):
    if "分钟前" in relative_time_str:
        minutes_ago = int(relative_time_str.split()[0])
        return int(time.time()) - minutes_ago * 60
    else:
        return None

async def check_and_send_message(post_link, post_title, post_poster, post_time):
    global last_check
    if (
        post_poster not in BLOCKED_POSTERS
        and post_link not in pushed_posts
        and post_time is not None
        and post_time > last_check
    ):
        if (
            not KEYWORDS_WHITELIST
            or any(keyword in post_title for keyword in KEYWORDS_WHITELIST)
        ) and not any(keyword in post_title for keyword in KEYWORDS_BLACKLIST):
            pushed_posts.add(post_link)

            post_content, attachment_urls, image_urls = await parse_post_content(post_link)

            message = (
                f"*{post_title}*\n[帖子链接]({post_link})\n{post_content}"
            )

            if attachment_urls:
                message += "\n附件：" + ", ".join(attachment_urls)

            if image_urls:
                message += "\n图片：" + ", ".join(image_urls)

            await send_message(message)

    if post_time is not None:
        last_check = post_time

async def check_hostloc():
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        async with aiohttp.ClientSession() as session:
            async with session.get("https://www.hostloc.com/forum.php?mod=guide&view=newthread", headers=headers) as response:
                response.raise_for_status()
                html_content = await response.text()

        soup = BeautifulSoup(html_content, 'html.parser')
        post_links = soup.select(".xst")

        tasks = []
        for link in reversed(post_links):
            post_link = "https://www.hostloc.com/" + link['href']
            post_title = link.string
            post_poster = link.parent.find_previous('a').string
            post_time_str = link.parent.find_next('em').text
            post_time = parse_relative_time(post_time_str)

            tasks.append(check_and_send_message(post_link, post_title, post_poster, post_time))

        await asyncio.gather(*tasks)

    except (requests.RequestException, ValueError, KeyError) as e:
        print(f"发生错误: {e}")

async def run_scheduler():
    while True:
        await asyncio.sleep(random.uniform(60, 120))
        await check_hostloc()

if __name__ == "__main__":
    asyncio.run(run_scheduler())

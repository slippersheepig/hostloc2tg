import requests
import time
import random
import asyncio
import telegram
from dotenv import dotenv_values
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import os
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 从.env文件中读取配置
config = dotenv_values("/opt/h2tg/.env")

# Telegram Bot 的 API Token
BOT_TOKEN = config["BOT_TOKEN"]
# Telegram Channel 的 ID
CHANNEL_ID = config["CHANNEL_ID"]
# 关键字过滤
KEYWORDS_WHITELIST = config.get("KEYWORDS_WHITELIST").split(',') if config.get("KEYWORDS_WHITELIST") else []
KEYWORDS_BLACKLIST = config.get("KEYWORDS_BLACKLIST").split(',') if config.get("KEYWORDS_BLACKLIST") else []

# 创建 Telegram Bot 实例
bot = telegram.Bot(token=BOT_TOKEN)

# 上次检查的时间戳，初始设为当前时间 - 3分钟
last_check = int(time.time()) - 180
# 保存已推送过的新贴链接
pushed_posts = set()

# 创建一个全局的 requests.Session，并启用重试功能
session = requests.Session()
retries = Retry(total=5, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
session.mount("https://", HTTPAdapter(max_retries=retries))

# 检查图片链接是否有效且尺寸大于1x1像素
def is_valid_image(url):
    try:
        response = session.get(url, stream=True, headers={"Referer": "https://www.hostloc.com", "User-Agent": "Mozilla/5.0"}, verify=False)
        if response.status_code == 200 and "image" in response.headers["Content-Type"]:
            response.raw.decode_content = True
            return int(response.headers.get('Content-Length', 0)) > 100  # 简单检查内容长度是否大于100字节
        return False
    except Exception as e:
        print(f"检查图片链接时发生错误: {e}")
        return False

# 下载图片并返回文件路径
def download_image(photo_url):
    try:
        response = session.get(photo_url, headers={"Referer": "https://www.hostloc.com", "User-Agent": "Mozilla/5.0"}, verify=False)
        if response.status_code == 200:
            file_path = "temp_image.jpg"
            with open(file_path, "wb") as f:
                f.write(response.content)
            return file_path
        return None
    except Exception as e:
        print(f"下载图片时发生错误: {e}")
        return None

# 发送消息到 Telegram Channel
async def send_message(msg, photo_urls=[], attachment_urls=[]):
    valid_photo_urls = [url for url in photo_urls if is_valid_image(url)]

    if valid_photo_urls:
        media = []
        for photo_url in valid_photo_urls:
            file_path = download_image(photo_url)
            if file_path:
                with open(file_path, "rb") as f:
                    media.append(telegram.InputMediaPhoto(media=f))
                os.remove(file_path)
            else:
                media.append(telegram.InputMediaPhoto(media=photo_url))
        
        await bot.send_media_group(chat_id=CHANNEL_ID, media=media)
    
    if attachment_urls:
        msg += "\n附件链接:\n" + "\n".join(attachment_urls)

    max_length = 4096
    if len(msg) > max_length:
        msg = msg[:max_length - 3] + "..."

    await bot.send_message(chat_id=CHANNEL_ID, text=msg, parse_mode='Markdown')

# 解析帖子内容（含文字和多张图片）
def parse_post_content(post_link):
    try:
        response = session.get(post_link, verify=False)
        response.raise_for_status()
        html_content = response.text

        soup = BeautifulSoup(html_content, 'html.parser')
        post_content_tag = soup.select_one(".t_fsz")

        content = ""
        photo_urls = []
        attachment_urls = []

        if post_content_tag:
            content = post_content_tag.get_text("\n", strip=True)
            photo_tags = post_content_tag.find_all("img")
            photo_urls = [tag["src"] if tag["src"].startswith("http") else urljoin(post_link, tag['src']) for tag in photo_tags if "src" in tag.attrs]

            attachment_tags = post_content_tag.select("a[href*='forum.php?mod=attachment']")
            attachment_urls = [urljoin(post_link, tag['href']) for tag in attachment_tags]

        return content, photo_urls, attachment_urls

    except (requests.RequestException, ValueError) as e:
        print(f"发生错误: {e}")
        return "", [], []

def parse_relative_time(relative_time_str):
    if "分钟前" in relative_time_str:
        minutes_ago = int(relative_time_str.split()[0])
        return int(time.time()) - minutes_ago * 60
    else:
        return None

# 检查 hostloc.com 的新贴子
async def check_hostloc():
    global last_check
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = session.get("https://www.hostloc.com/forum.php?mod=guide&view=newthread", headers=headers, verify=False)
        response.raise_for_status()
        html_content = response.text

        soup = BeautifulSoup(html_content, 'html.parser')
        post_links = soup.select(".xst")

        for link in reversed(post_links):
            post_link = "https://www.hostloc.com/" + link['href']
            post_title = link.string

            post_time_str = link.parent.find_next('em').text
            post_time = parse_relative_time(post_time_str)

            if post_link not in pushed_posts and post_time is not None and post_time > last_check:
                if (not KEYWORDS_WHITELIST or any(keyword in post_title for keyword in KEYWORDS_WHITELIST)) and not any(keyword in post_title for keyword in KEYWORDS_BLACKLIST):
                    pushed_posts.add(post_link)

                    post_content, photo_urls, attachment_urls = parse_post_content(post_link)
                    message = f"*{post_title}*\n{post_link}\n{post_content}"

                    await send_message(message, photo_urls, attachment_urls)

        if post_links and post_time is not None:
            last_check = post_time

    except (requests.RequestException, ValueError, KeyError) as e:
        print(f"发生错误: {e}")

async def run_scheduler():
    while True:
        await asyncio.sleep(random.uniform(60, 120))
        asyncio.create_task(check_hostloc())

if __name__ == "__main__":
    asyncio.run(run_scheduler())

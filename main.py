import asyncio
import requests
import random
import telegram
import time
from dotenv import dotenv_values
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from html import unescape

# 从.env文件中读取配置
config = dotenv_values("/opt/h2tg/.env")

# Telegram Bot 的 API Token 和 Channel 的 ID
BOT_TOKEN, CHANNEL_ID = config["BOT_TOKEN"], config["CHANNEL_ID"]

# 其他配置项
KEYWORDS_WHITELIST, KEYWORDS_BLACKLIST, BLOCKED_POSTERS = map(lambda x: config.get(x, "").split(','), ["KEYWORDS_WHITELIST", "KEYWORDS_BLACKLIST", "BLOCKED_POSTERS"])

# 时间戳和已推送链接集合
last_check, pushed_posts = int(time.time()) - 180, set()

# 发送消息到 Telegram Channel
async def send_message(msg):
    await telegram.Bot(token=BOT_TOKEN).send_message(chat_id=CHANNEL_ID, text=msg, parse_mode=telegram.ParseMode.MARKDOWN)

# 解析帖子内容
def parse_post_content(post_link):
    try:
        soup = BeautifulSoup(requests.get(post_link).text, 'html.parser')
        post_content = soup.select_one(".t_fsz")
        return post_content.get_text(strip=True) if post_content else ""

    except (requests.RequestException, ValueError):
        return ""

# 转义特殊字符
def escape_special_characters(text):
    special_characters = ['[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_characters:
        text = text.replace(char, f'\\{char}')
    return text

# 检查 hostloc.com 的新贴子
async def check_hostloc():
    global last_check
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get("https://www.hostloc.com/forum.php?mod=guide&view=newthread", headers=headers)
        response.raise_for_status()
        soup, post_links = BeautifulSoup(response.text, 'html.parser'), soup.select(".xst")[::-1]

        for link in post_links:
            post_link, post_title = "https://www.hostloc.com/" + link['href'], escape_special_characters(unescape(link.string))
            post_poster = unescape(link.parent.find_previous('a').string) if link.parent.find_previous('a') else ""

            post_time_str, post_time = link.parent.find_next('em').text, parse_relative_time(post_time_str)
            
            if post_poster not in BLOCKED_POSTERS and post_link not in pushed_posts and post_time is not None and post_time > last_check:
                if (not KEYWORDS_WHITELIST or any(keyword in post_title for keyword in KEYWORDS_WHITELIST)) and not any(keyword in post_title for keyword in KEYWORDS_BLACKLIST):
                    pushed_posts.add(post_link)
                    post_content = parse_post_content(post_link)
                    message = f"*{post_title}*\n[帖子链接]({post_link})\n{post_content}"

                    attachments, images = soup.select(".pattl+.pattl"), soup.select(".pcb img")
                    if attachments:
                        attachment_urls = [attachment['href'] for attachment in attachments]
                        message += "\n附件：" + "\n".join(f"[附件 {i+1}]({url})" for i, url in enumerate(attachment_urls))
                    if images:
                        image_urls = [image['file'] for image in images]
                        message += "\n图片：" + "\n".join(f"![图片 {i+1}]({url})" for i, url in enumerate(image_urls))

                    await send_message(message)

        if post_links and post_time is not None:
            last_check = post_time

    except (requests.RequestException, ValueError, KeyError):
        pass

# 定时任务
async def run_scheduler():
    while True:
        await asyncio.sleep(random.uniform(60, 120))
        asyncio.create_task(check_hostloc())

# 启动定时任务
if __name__ == "__main__":
    asyncio.run(run_scheduler())

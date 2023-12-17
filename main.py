import requests
import time
import random
import asyncio
import telegram
from dotenv import dotenv_values
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# 从.env文件中读取配置
config = dotenv_values("/opt/h2tg/.env")

# Telegram Bot 的 API Token
BOT_TOKEN = config["BOT_TOKEN"]
# Telegram Channel 的 ID
CHANNEL_ID = config["CHANNEL_ID"]
# 关键字过滤
KEYWORDS_WHITELIST = config.get("KEYWORDS_WHITELIST").split(',') if config.get("KEYWORDS_WHITELIST") else []
KEYWORDS_BLACKLIST = config.get("KEYWORDS_BLACKLIST").split(',') if config.get("KEYWORDS_BLACKLIST") else []
# 发帖人屏蔽名单
BLOCKED_POSTERS = config.get("BLOCKED_POSTERS").split(',') if config.get("BLOCKED_POSTERS") else []

# 上次检查的时间戳，初始设为当前时间 - 3分钟
last_check = int(time.time()) - 180
# 保存已推送过的新贴链接
pushed_posts = set()

# 发送消息到 Telegram Channel
async def send_message(msg, photo_urls=[]):
    bot = telegram.Bot(token=BOT_TOKEN)
    
    # 如果有图片链接，发送带图片的消息
    if photo_urls:
        media = [telegram.InputMediaPhoto(media=photo_url) for photo_url in photo_urls]
        await bot.send_media_group(chat_id=CHANNEL_ID, media=media, caption=msg, parse_mode='Markdown')
    else:
        # 否则发送文本消息
        await bot.send_message(chat_id=CHANNEL_ID, text=msg, parse_mode='Markdown')

# 解析帖子内容（含文字和多张图片）
def parse_post_content(post_link):
    try:
        response = requests.get(post_link)
        response.raise_for_status()  # 检查请求是否成功
        html_content = response.text

        soup = BeautifulSoup(html_content, 'html.parser')
        post_content_tag = soup.select_one(".t_fsz")

        # 提取发帖内容
        content = ""
        photo_urls = []
        if post_content_tag:
            content = post_content_tag.get_text("\n", strip=True)
            # 提取所有图片链接
            photo_tags = post_content_tag.find_all("img")
            photo_urls = [tag["src"] if tag["src"].startswith("http") else f"https://hostloc.com{tag['src']}" for tag in photo_tags if "src" in tag.attrs]

        return content, photo_urls

    except (requests.RequestException, ValueError) as e:
        print(f"发生错误: {e}")
        return "", []

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
        # 发送请求，获取最新的帖子链接和标题
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get("https://www.hostloc.com/forum.php?mod=guide&view=newthread", headers=headers)
        response.raise_for_status()  # 检查请求是否成功
        html_content = response.text

        # 解析HTML内容，提取最新的帖子链接和标题
        soup = BeautifulSoup(html_content, 'html.parser')
        post_links = soup.select(".xst")

        # 遍历最新的帖子链接
        for link in reversed(post_links):
            post_link = "https://www.hostloc.com/" + link['href']
            post_title = link.string
            post_poster = link.parent.find_previous('a').string

            # 获取帖子发布时间
            post_time_str = link.parent.find_next('em').text
            post_time = parse_relative_time(post_time_str)

            # 如果没有发布人屏蔽，且没有指定关键字或帖子链接不在已推送过的新贴集合中，
            # 并且发布时间在上次检查时间之后，发送到Telegram Channel并将链接加入已推送集合
            if post_poster not in BLOCKED_POSTERS and post_link not in pushed_posts and post_time is not None and post_time > last_check:
                if (not KEYWORDS_WHITELIST or any(keyword in post_title for keyword in KEYWORDS_WHITELIST)) and not any(keyword in post_title for keyword in KEYWORDS_BLACKLIST):
                    pushed_posts.add(post_link)

                    # 解析帖子内容（含文字和多张图片）
                    post_content, photo_urls = parse_post_content(post_link)

                    # 构建消息文本
                    message = f"*{post_title}*\n{post_link}\n{post_content}"

                    # 发送整合后的消息到Telegram Channel
                    await send_message(message, photo_urls)

        # 更新上次检查的时间为最后一个帖子的发布时间
        if post_links and post_time is not None:
            last_check = post_time

    except (requests.RequestException, ValueError, KeyError) as e:
        print(f"发生错误: {e}")

# 使用 asyncio.create_task() 来运行 check_hostloc() 作为异步任务
async def run_scheduler():
    # 每隔1-2分钟执行一次检查
    while True:
        await asyncio.sleep(random.uniform(60, 120))
        asyncio.create_task(check_hostloc())

# 启动定时任务
if __name__ == "__main__":
    asyncio.run(run_scheduler())

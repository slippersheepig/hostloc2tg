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

# 上次检查的时间戳，初始设为当前时间 - 3分钟
last_check = int(time.time()) - 180
# 保存已推送过的新贴链接
pushed_posts = set()
# 保存上一次遍历的新贴链接
previous_posts = set()

# 发送消息到 Telegram Channel
async def send_message(msg):
    bot = telegram.Bot(token=BOT_TOKEN)
    await bot.send_message(chat_id=CHANNEL_ID, text=msg)

# 检查 hostloc.com 的新帖子
async def check_hostloc():
    global last_check
    global previous_posts
    # 对hostloc.com发起请求，获取最新的帖子链接和标题
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    response = requests.get("https://www.hostloc.com/forum.php?mod=guide&view=newthread", headers=headers)
    html_content = response.text

    # 解析HTML内容，提取最新的帖子链接和标题
    soup = BeautifulSoup(html_content, 'html.parser')
    post_links = soup.select(".xst")

    # 遍历最新的帖子链接
    for link in reversed(post_links):  # 遍历最新的帖子链接，从后往前
        post_link = "https://www.hostloc.com/" + link['href']
        post_title = link.string

        # 检查链接是否在上一次遍历的新贴集合中
        if post_link in previous_posts:
            # 遇到重复链接，发送未推送过的新贴链接并停止遍历
            for new_post_link in set(post_links) - previous_posts:
                await send_message(f"{post_title}\n{post_link}")
                pushed_posts.add(post_link)
        else:
            # 链接不在上一次遍历的新贴集合中
            post_time = int(time.time())
            # 如果帖子链接不在已推送过的新贴集合中，并且发布时间在上次检查时间之后，发送到Telegram Channel并将链接加入已推送集合
            if post_link not in pushed_posts and post_time > last_check:
                pushed_posts.add(post_link)
                await send_message(f"{post_title}\n{post_link}")
        
        # 更新上一次遍历的新贴集合
        previous_posts.add(post_link)

    # 更新上次检查的时间为当前时间
    last_check = int(time.time())

# 使用 asyncio.create_task() 来运行 check_hostloc() 作为异步任务
async def run_scheduler():
    # 首次运行获取最新的3条新帖
    await check_hostloc()
    await asyncio.sleep(random.uniform(60, 120))

    # 每隔1-2分钟执行一次检查
    while True:
        asyncio.create_task(check_hostloc())
        await asyncio.sleep(random.uniform(60, 120))

# 启动定时任务
if __name__ == "__main__":
    asyncio.run(run_scheduler())

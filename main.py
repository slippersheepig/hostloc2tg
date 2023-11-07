import requests
import time
import random
from datetime import datetime, timedelta
import schedule
import asyncio
import telegram
from pathlib import Path
from dotenv import dotenv_values
from bs4 import BeautifulSoup

parent_dir = Path(__file__).resolve().parent
config = dotenv_values(f"/opt/h2tg/.env")

# Telegram Bot 的 API Token
BOT_TOKEN = config["BOT_TOKEN"]
# Telegram Channel 的 ID
CHANNEL_ID = config["CHANNEL_ID"]
# 上次检查的时间戳，初始设为当前时间
last_check = int(time.time())
# 保存已推送过的新贴链接
pushed_posts = set()

# 发送消息到 Telegram Channel
async def send_message(msg):
    bot = telegram.Bot(token=BOT_TOKEN)
    await bot.send_message(chat_id=CHANNEL_ID, text=msg)

# 获取帖子的阅读权限
def get_post_permission(link):
    response = requests.get(link)
    html_content = response.text

    soup = BeautifulSoup(html_content, 'html.parser')
    permission = soup.select('.authi > .xw1')[0].get_text()
    return permission

# 检查 hostloc.com 的新帖子
async def check_hostloc():
    global last_check
    # 获取当前时间
    current_time = int(time.time())
    # 计算上次检查到当前时间之间的时间差
    time_diff = current_time - last_check
    # 设置一个时间阈值，例如每隔5分钟检查一次
    time_threshold = timedelta(minutes=5).seconds

    # 如果距离上次检查的时间超过时间阈值，则进行检查
    if time_diff > time_threshold:
        # 更新上次检查的时间为当前时间
        last_check = current_time

        # 对hostloc.com发起请求，获取最新的帖子链接和标题
        response = requests.get("https://www.hostloc.com/forum.php?mod=guide&view=newthread")
        html_content = response.text

        # 解析HTML内容，提取最新的帖子链接和标题
        soup = BeautifulSoup(html_content, 'html.parser')
        post_links = soup.select(".xst")
        latest_post_link = "https://www.hostloc.com/" + post_links[0]['href']
        latest_post_title = post_links[0].string

        # 如果最新的帖子链接不在已推送过的新贴集合中，则发送到Telegram Channel
        if latest_post_link not in pushed_posts:
            pushed_posts.add(latest_post_link)
            permission = get_post_permission(latest_post_link)
            await send_message(f"{latest_post_title}\n阅读权限：{permission}\n{latest_post_link}")

# 使用 schedule 库来定时执行检查
async def run_scheduler():
    # 每隔1-2分钟钟执行一次检查
    def check_hostloc_callback():
        asyncio.create_task(check_hostloc())
    schedule.every(random.uniform(60, 120)).seconds.do(check_hostloc_callback)

    while True:
        schedule.run_pending()
        await asyncio.sleep(1)

# 启动定时任务
if __name__ == "__main__":
    asyncio.run(run_scheduler())

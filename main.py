import requests
import time
import random
import asyncio
import telegram
from pathlib import Path
from dotenv import dotenv_values
from bs4 import BeautifulSoup

# 获取当前文件的父目录路径
parent_dir = Path(__file__).resolve().parent
# 从.env文件中读取配置
config = dotenv_values(parent_dir / ".env")

# Telegram Bot 的 API Token
BOT_TOKEN = config["BOT_TOKEN"]
# Telegram Channel 的 ID
CHANNEL_ID = config["CHANNEL_ID"]

# 上次检查的时间戳，初始设为当前时间
last_check = int(time.time())
# 保存已推送过的新贴链接
pushed_posts = set()
last_post = ""

# 发送消息到 Telegram Channel
async def send_message(msg):
    bot = telegram.Bot(token=BOT_TOKEN)
    await bot.send_message(chat_id=CHANNEL_ID, text=msg)

# 获取帖子的阅读权限
def get_post_permission(link):
    response = requests.get(link)
    html_content = response.text

    soup = BeautifulSoup(html_content, 'html.parser')
    permission_element = soup.select_one('.authi > .xw1')
    permission = permission_element.get_text() if permission_element else "0"
    return permission

# 检查 hostloc.com 的新帖子
async def check_hostloc():
    global last_check, last_post  # 声明要使用的全局变量
    # 获取当前时间
    current_time = int(time.time())
    # 计算上次检查到当前时间之间的时间差
    time_diff = current_time - last_check
    # 设置一个时间阈值，例如每隔5分钟检查一次
    time_threshold = 300

    # 如果距离上次检查的时间超过时间阈值，则进行检查
    if time_diff > time_threshold:
        # 对hostloc.com发起请求，获取最新的帖子链接和标题
        response = requests.get("https://www.hostloc.com/forum.php?mod=guide&view=newthread")
        html_content = response.text

        # 解析HTML内容，提取最新的帖子链接和标题
        soup = BeautifulSoup(html_content, 'html.parser')
        post_links = soup.select(".xst")

        # 找到上一次获取到的新帖子的位置
        last_post_index = None
        for i, link in enumerate(post_links):
            post_link = "https://www.hostloc.com/" + link['href']
            if post_link == last_post:
                last_post_index = i
                break

        # 如果找到上一次获取到的新帖子的位置，从该位置开始遍历新的帖子链接
        if last_post_index is not None:
            for link in post_links[:last_post_index + 1]:
                post_link = "https://www.hostloc.com/" + link['href']
                post_title = link.string

                # 如果帖子链接不在已推送过的新贴集合中，则发送到Telegram Channel并将链接加入已推送集合
                if post_link not in pushed_posts:
                    pushed_posts.add(post_link)
                    permission = get_post_permission(post_link)
                    display_permission = f"阅读权限：{permission}" if permission != "0" else ""
                    await send_message(f"{post_title}\n{display_permission}\n{post_link}")

            # 更新上次检查的时间为当前时间
            last_check = current_time

# 使用 asyncio.create_task() 来运行 check_hostloc() 作为异步任务
async def run_scheduler():
    # 每隔1-2分钟执行一次检查
    while True:
        await asyncio.sleep(random.uniform(60, 120))
        asyncio.create_task(check_hostloc())

# 启动定时任务
if __name__ == "__main__":
    asyncio.run(run_scheduler())

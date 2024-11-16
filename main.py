import asyncio
from playwright.async_api import async_playwright
import random
import json
import time

# Global variables for last load time and config
last_load_time = 0
config = None

# Load configuration from config.json periodically
def load_config():
    global last_load_time, config
    current_time = time.monotonic()
    # Reload config every 10 seconds
    if current_time - last_load_time > 10:
        with open("config.json", "r") as f:
            config = json.load(f)
        last_load_time = current_time
    return config

def read_accounts():
    accounts = []
    with open("accounts.txt", "r") as f:
        for line in f:
            number, username, password = line.strip().split(":")
            accounts.append({"number": number, "username": username, "password": password, 'last_chat_time': 0})
    return accounts

def read_chat_messages():
    with open("chatmessages.txt", "r") as f:
        return [line.strip() for line in f]

def read_proxies():
    proxies = []
    with open("proxies.txt", "r") as f:
        for line in f:
            ip, port, _, _ = line.strip().split(":")  # Ignore username and password
            proxies.append(f"{ip}:{port}")
    return proxies

async def login_to_rumble(playwright, account, semaphore, chat_messages, followed_channels, liked_videos, proxy, headless):
    async with semaphore:
        browser = await playwright.firefox.launch(
            headless=headless,
            proxy={"server": f"http://{proxy}"}
        )
        context = await browser.new_context(java_script_enabled=True, viewport={"width": 1280, "height": 720})
        page = await context.new_page()

        try:
            current_config = load_config()  # Load the latest config

            print(f"[DEBUG] Bot {account['number']} is navigating to {current_config['channel_url']} using proxy {proxy}.")
            await page.goto("https://rumble.com/", wait_until="domcontentloaded")
            await asyncio.sleep(5)

            # Log in process
            await page.click("button.round-button.btn-grey")
            await asyncio.sleep(3)
            await page.fill("#login-username", account["username"])
            await asyncio.sleep(3)
            await page.fill("#login-password", account["password"])
            await asyncio.sleep(3)
            await page.click("button[type='submit']")
            await asyncio.sleep(5)
            print(f"[DEBUG] Bot {account['number']} logged in successfully using proxy {proxy}.")

            # Navigate to channel URL from the current config
            await page.goto(current_config["channel_url"], wait_until="domcontentloaded")
            await asyncio.sleep(5)

            view_time = random.randint(current_config["view_time_range"][0], current_config["view_time_range"][1])
            print(f"[DEBUG] Bot {account['number']} will watch the video for {view_time} seconds.")

            start_time = time.monotonic()
            while True:
                elapsed_time = time.monotonic() - start_time
                if elapsed_time >= view_time:
                    print(f"[DEBUG] Bot {account['number']} finished its viewing time.")
                    break

                await interact_with_channel(page, account, followed_channels, liked_videos, chat_messages)
                await asyncio.sleep(2)

        except Exception as e:
            print(f"[ERROR] Error with bot {account['number']} using proxy {proxy}: {e}")
        finally:
            await asyncio.sleep(5)
            await context.close()
            await browser.close()

async def interact_with_channel(page, account, followed_channels, liked_videos, chat_messages):
    current_config = load_config()  # Load latest config
    channel_selector = "button"  # Simplified for general channel follow button
    like_selector = "button.rumbles-vote-pill-up"  # Simplified like button selector

    # Follow the channel based on frequency in current config
    if random.random() < current_config["follow_frequency"] and channel_selector not in followed_channels:
        try:
            await page.wait_for_selector(channel_selector, timeout=10000)
            await page.click(channel_selector)
            followed_channels.add(channel_selector)
            print(f"[INFO] Bot {account['number']} followed the channel.")
        except Exception as e:
            print(f"[ERROR] Error following channel for bot {account['number']}: {e}")

    # Like the video based on frequency in current config
    if random.random() < current_config["like_frequency"] and like_selector not in liked_videos:
        try:
            await page.wait_for_selector(like_selector, timeout=10000)
            await page.click(like_selector)
            liked_videos.add(like_selector)
            print(f"[INFO] Bot {account['number']} liked the video.")
        except Exception as e:
            print(f"[ERROR] Error liking video for bot {account['number']}: {e}")

    await chat_with_viewers(page, account, chat_messages)

async def chat_with_viewers(page, account, chat_messages):
    current_config = load_config()  # Load latest config
    chat_input_selector = "#chat-message-text-input"
    send_button_selector = ".chat--send"

    try:
        await page.wait_for_selector(chat_input_selector, timeout=10000)
        message = random.choice(chat_messages)
        cooldown_time = random.randint(current_config["chat_cooldown"][0], current_config["chat_cooldown"][1])
        current_time = time.monotonic()

        if (current_time - account['last_chat_time']) >= cooldown_time and random.random() < current_config["chat_frequency"]:
            await page.fill(chat_input_selector, message)
            await asyncio.sleep(2)
            await page.click(send_button_selector)
            print(f"[INFO] Bot {account['number']} sent the message: {message}")
            account['last_chat_time'] = current_time
    except Exception:
        pass

async def manage_bots():
    accounts = read_accounts()
    chat_messages = read_chat_messages()
    proxies = read_proxies()
    current_config = load_config()  # Initial config load
    semaphore = asyncio.Semaphore(current_config["max_concurrent_bots"])

    random.shuffle(accounts)
    random.shuffle(proxies)

    followed_channels = set()
    liked_videos = set()

    async with async_playwright() as playwright:
        tasks = []
        for i, account in enumerate(accounts):
            proxy = proxies[i % len(proxies)]
            task = asyncio.create_task(login_to_rumble(
                playwright,
                account=account,
                semaphore=semaphore,
                chat_messages=chat_messages,
                followed_channels=followed_channels,
                liked_videos=liked_videos,
                proxy=proxy,
                headless=False
            ))
            tasks.append(task)

        await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(manage_bots())

"""
Telegram Waifu Grabber Bot - Railway Compatible Version
A fun bot for collecting anime waifus in Telegram groups
"""

from pyrogram import Client, filters
from pyrogram.types import Message
import json
import random
import time
from datetime import datetime, timedelta
from database import Database
from config import API_ID, API_HASH, BOT_TOKEN, ADMIN_IDS

# Initialize bot
app = Client("waifu_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
db = Database()

# Load waifu data
try:
    with open('waifus.json', 'r', encoding='utf-8') as f:
        WAIFUS = json.load(f)
    print(f"✅ Loaded {len(WAIFUS)} waifus")
except Exception as e:
    print(f"❌ Error loading waifus.json: {e}")
    WAIFUS = []

# Tracking message counts per group
message_counts = {}
active_spawns = {}  # group_id: {waifu, claimed}
user_cooldowns = {}  # user_id: last_claim_time
command_cooldowns = {}  # user_id: last_command_time

# Configuration
SPAWN_MIN = 80
SPAWN_MAX = 120
CLAIM_COOLDOWN = 10  # seconds
COMMAND_COOLDOWN = 3  # seconds


def check_cooldown(user_id, cooldown_type='command'):
    """Check if user is on cooldown"""
    cooldowns = command_cooldowns if cooldown_type == 'command' else user_cooldowns
    cooldown_time = COMMAND_COOLDOWN if cooldown_type == 'command' else CLAIM_COOLDOWN
    
    if user_id in cooldowns:
        time_passed = time.time() - cooldowns[user_id]
        if time_passed < cooldown_time:
            return False, int(cooldown_time - time_passed)
    return True, 0


def get_rarity_emoji(rarity):
    """Get emoji for rarity"""
    emojis = {
        'Common': '⚪',
        'Rare': '🔵',
        'Epic': '🟣',
        'Legendary': '🟡',
        'Mythic': '🔴'
    }
    return emojis.get(rarity, '⚪')


async def spawn_waifu(client, chat_id):
    """Spawn a random waifu in the group"""
    if not WAIFUS:
        print("❌ No waifus loaded!")
        return
    
    # Weighted random based on rarity
    rarity_weights = {
        'Common': 50,
        'Rare': 30,
        'Epic': 15,
        'Legendary': 4,
        'Mythic': 1
    }
    
    # Filter waifus by rarity and select based on weights
    all_waifus = []
    for waifu in WAIFUS:
        weight = rarity_weights.get(waifu['rarity'], 1)
        all_waifus.extend([waifu] * weight)
    
    selected = random.choice(all_waifus)
    
    # Store active spawn
    active_spawns[chat_id] = {
        'waifu': selected,
        'claimed': False,
        'spawn_time': time.time()
    }
    
    # Create spawn message
    message = f"""✨ **A mysterious waifu appeared!**

💭 Guess her name to claim her!
👤 Anime: `{selected['anime']}`
⭐ Rarity: `Hidden`

🎯 Type the character's name to claim!"""
    
    try:
        await client.send_photo(
            chat_id,
            photo=selected.get('image', 'https://via.placeholder.com/400x600?text=Waifu'),
            caption=message
        )
    except Exception as e:
        print(f"Image send failed: {e}")
        await client.send_message(chat_id, message)


@app.on_message(filters.group & filters.text)
async def handle_messages(client: Client, message: Message):
    """Handle group messages for spawning and claiming"""
    
    # Ignore commands
    if message.text and message.text.startswith('/'):
        return
    
    chat_id = message.chat.id
    
    # Check for active spawn and name guessing
    if chat_id in active_spawns and not active_spawns[chat_id]['claimed']:
        spawn_data = active_spawns[chat_id]
        waifu = spawn_data['waifu']
        
        # Check if message matches waifu name (case insensitive)
        if message.text.lower().strip() == waifu['name'].lower().strip():
            # Check cooldown
            can_claim, wait_time = check_cooldown(message.from_user.id, 'claim')
            if not can_claim:
                try:
                    await message.reply(f"⏳ You're on cooldown! Wait {wait_time}s")
                except:
                    pass
                return
            
            # Claim the waifu
            user_cooldowns[message.from_user.id] = time.time()
            active_spawns[chat_id]['claimed'] = True
            
            username = message.from_user.username or message.from_user.first_name or "User"
            db.add_waifu_to_user(message.from_user.id, username, waifu)
            
            rarity_emoji = get_rarity_emoji(waifu['rarity'])
            try:
                await message.reply(
                    f"🎉 **Congratulations!**\n\n"
                    f"{rarity_emoji} @{username} claimed **{waifu['name']}**!\n"
                    f"📺 From: `{waifu['anime']}`\n"
                    f"⭐ Rarity: `{waifu['rarity']}`"
                )
            except:
                pass
            return
    
    # Increment message count for spawning
    if chat_id not in message_counts:
        message_counts[chat_id] = {
            'count': 0,
            'target': random.randint(SPAWN_MIN, SPAWN_MAX)
        }
    
    message_counts[chat_id]['count'] += 1
    
    # Check if should spawn
    if message_counts[chat_id]['count'] >= message_counts[chat_id]['target']:
        if chat_id not in active_spawns or active_spawns[chat_id]['claimed']:
            await spawn_waifu(client, chat_id)
            message_counts[chat_id] = {
                'count': 0,
                'target': random.randint(SPAWN_MIN, SPAWN_MAX)
            }


@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    """Start command"""
    welcome = f"""👋 **Welcome to Waifu Grabber Bot!**

🎮 **How to Play:**
• Wait for waifus to spawn in groups
• Guess the character's name to claim
• Collect and trade with friends!

📋 **Commands:**
/mywaifus - View your collection
/waifu <name> - Info about a waifu
/top - Leaderboard
/drop <name> - Drop a waifu
/daily - Get daily waifu
/help - Show this message

💎 **Rarities:**
⚪ Common | 🔵 Rare | 🟣 Epic | 🟡 Legendary | 🔴 Mythic

Add me to a group to start collecting! 🎌"""
    
    try:
        await message.reply(welcome)
    except Exception as e:
        print(f"Start command error: {e}")


@app.on_message(filters.command("mywaifus"))
async def my_waifus_command(client: Client, message: Message):
    """Show user's waifu collection"""
    can_use, wait_time = check_cooldown(message.from_user.id)
    if not can_use:
        try:
            await message.reply(f"⏳ Cooldown: {wait_time}s")
        except:
            pass
        return
    
    command_cooldowns[message.from_user.id] = time.time()
    
    try:
        waifus = db.get_user_waifus(message.from_user.id)
        
        if not waifus:
            await message.reply("📭 You don't have any waifus yet!\n\nWait for spawns in groups to start collecting! 🎌")
            return
        
        # Group by rarity
        by_rarity = {}
        for waifu in waifus:
            rarity = waifu['rarity']
            if rarity not in by_rarity:
                by_rarity[rarity] = []
            by_rarity[rarity].append(waifu)
        
        username = message.from_user.first_name or "User"
        response = f"🎌 **{username}'s Collection**\n\n"
        response += f"📊 Total: **{len(waifus)}** waifus\n\n"
        
        for rarity in ['Mythic', 'Legendary', 'Epic', 'Rare', 'Common']:
            if rarity in by_rarity:
                emoji = get_rarity_emoji(rarity)
                response += f"{emoji} **{rarity}** ({len(by_rarity[rarity])})\n"
                for waifu in by_rarity[rarity][:5]:  # Show max 5 per rarity
                    response += f"  • {waifu['name']} ({waifu['anime']})\n"
                if len(by_rarity[rarity]) > 5:
                    response += f"  ... and {len(by_rarity[rarity]) - 5} more\n"
                response += "\n"
        
        await message.reply(response)
    except Exception as e:
        print(f"Mywaifus error: {e}")
        await message.reply("❌ Error fetching collection. Try again later!")


@app.on_message(filters.command("waifu"))
async def waifu_info_command(client: Client, message: Message):
    """Show information about a specific waifu"""
    can_use, wait_time = check_cooldown(message.from_user.id)
    if not can_use:
        try:
            await message.reply(f"⏳ Cooldown: {wait_time}s")
        except:
            pass
        return
    
    command_cooldowns[message.from_user.id] = time.time()
    
    try:
        if len(message.command) < 2:
            await message.reply("❌ Usage: /waifu <name>\n\nExample: `/waifu Mikasa Ackerman`")
            return
        
        name = ' '.join(message.command[1:])
        
        # Search for waifu
        waifu = None
        for w in WAIFUS:
            if w['name'].lower() == name.lower():
                waifu = w
                break
        
        if not waifu:
            await message.reply(f"❌ Waifu **{name}** not found in database!")
            return
        
        emoji = get_rarity_emoji(waifu['rarity'])
        info = f"""🎌 **{waifu['name']}**

📺 Anime: `{waifu['anime']}`
⭐ Rarity: {emoji} `{waifu['rarity']}`

💬 *"{waifu.get('quote', 'A beloved character!')}"*"""
        
        try:
            await message.reply_photo(photo=waifu.get('image', 'https://via.placeholder.com/400x600?text=Waifu'), caption=info)
        except:
            await message.reply(info)
    except Exception as e:
        print(f"Waifu info error: {e}")
        await message.reply("❌ Error fetching waifu info!")


@app.on_message(filters.command("drop"))
async def drop_command(client: Client, message: Message):
    """Drop a waifu from collection"""
    can_use, wait_time = check_cooldown(message.from_user.id)
    if not can_use:
        try:
            await message.reply(f"⏳ Cooldown: {wait_time}s")
        except:
            pass
        return
    
    command_cooldowns[message.from_user.id] = time.time()
    
    try:
        if len(message.command) < 2:
            await message.reply("❌ Usage: /drop <name>\n\nExample: `/drop Mikasa Ackerman`")
            return
        
        name = ' '.join(message.command[1:])
        
        if db.remove_waifu_from_user(message.from_user.id, name):
            await message.reply(f"✅ Dropped **{name}** from your collection!")
        else:
            await message.reply(f"❌ You don't have **{name}** in your collection!")
    except Exception as e:
        print(f"Drop error: {e}")
        await message.reply("❌ Error dropping waifu!")


@app.on_message(filters.command("top"))
async def top_command(client: Client, message: Message):
    """Show leaderboard"""
    can_use, wait_time = check_cooldown(message.from_user.id)
    if not can_use:
        try:
            await message.reply(f"⏳ Cooldown: {wait_time}s")
        except:
            pass
        return
    
    command_cooldowns[message.from_user.id] = time.time()
    
    try:
        top_users = db.get_leaderboard(10)
        
        if not top_users:
            await message.reply("📊 No users in leaderboard yet!")
            return
        
        response = "🏆 **TOP COLLECTORS**\n\n"
        
        medals = ['🥇', '🥈', '🥉']
        for i, user in enumerate(top_users):
            medal = medals[i] if i < 3 else f"{i+1}."
            username = user['username'] if user['username'] else "Anonymous"
            response += f"{medal} @{username} — **{user['count']}** waifus\n"
        
        await message.reply(response)
    except Exception as e:
        print(f"Top error: {e}")
        await message.reply("❌ Error fetching leaderboard!")


@app.on_message(filters.command("daily"))
async def daily_command(client: Client, message: Message):
    """Get daily free waifu"""
    try:
        user_id = message.from_user.id
        
        # Check if already claimed today
        last_daily = db.get_last_daily(user_id)
        if last_daily:
            next_daily = last_daily + timedelta(days=1)
            if datetime.now() < next_daily:
                time_left = next_daily - datetime.now()
                hours = int(time_left.total_seconds() // 3600)
                minutes = int((time_left.total_seconds() % 3600) // 60)
                await message.reply(f"⏳ Daily already claimed!\n\nNext daily in: {hours}h {minutes}m")
                return
        
        # Give random waifu (higher chance for common)
        if not WAIFUS:
            await message.reply("❌ No waifus available!")
            return
            
        waifu = random.choices(
            WAIFUS,
            weights=[50 if w['rarity'] == 'Common' else 20 if w['rarity'] == 'Rare' else 5 for w in WAIFUS]
        )[0]
        
        username = message.from_user.username or message.from_user.first_name or "User"
        db.add_waifu_to_user(user_id, username, waifu)
        db.update_last_daily(user_id)
        
        emoji = get_rarity_emoji(waifu['rarity'])
        await message.reply(
            f"🎁 **Daily Waifu Claimed!**\n\n"
            f"{emoji} You received: **{waifu['name']}**\n"
            f"📺 From: `{waifu['anime']}`\n"
            f"⭐ Rarity: `{waifu['rarity']}`\n\n"
            f"Come back tomorrow for another! 🌸"
        )
    except Exception as e:
        print(f"Daily error: {e}")
        await message.reply("❌ Error claiming daily waifu!")


@app.on_message(filters.command("forcespawn"))
async def force_spawn_command(client: Client, message: Message):
    """Admin command to force spawn"""
    try:
        # Check if user is admin
        if message.from_user.id not in ADMIN_IDS:
            await message.reply("❌ This command is for admins only!")
            return
        
        if message.chat.type == "private":
            await message.reply("❌ This command only works in groups!")
            return
        
        await spawn_waifu(client, message.chat.id)
        await message.reply("✅ Waifu spawned!")
    except Exception as e:
        print(f"Forcespawn error: {e}")
        await message.reply("❌ Error spawning waifu!")


@app.on_message(filters.command("help"))
async def help_command(client: Client, message: Message):
    """Show help message"""
    help_text = """📚 **WAIFU GRABBER COMMANDS**

👤 **User Commands:**
/mywaifus - View your collection
/waifu <name> - Info about a waifu
/drop <name> - Drop a waifu
/top - View leaderboard
/daily - Get daily free waifu
/help - Show this message

🎮 **How to Play:**
1. Wait for waifus to spawn in groups
2. Type the character's name to claim
3. Build your collection!

💎 **Rarities:**
⚪ Common - 50%
🔵 Rare - 30%
🟣 Epic - 15%
🟡 Legendary - 4%
🔴 Mythic - 1%

⏱️ **Cooldowns:**
• Claim: 10 seconds
• Commands: 3 seconds

Need help? Just ask! 🌸"""
    
    try:
        await message.reply(help_text)
    except Exception as e:
        print(f"Help error: {e}")


# Run the bot
if __name__ == "__main__":
    print("🤖 Waifu Grabber Bot Starting...")
    print(f"✅ Loaded {len(WAIFUS)} waifus")
    print("✅ Bot is running!")
    app.run()

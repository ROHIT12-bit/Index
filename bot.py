from telegram.ext import Application, MessageHandler, CommandHandler, filters
from telegram import Update
import logging
import re
import json
import os
from datetime import datetime

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN = '7591153782:AAHq-K_OZ2C7hMMYLag3zj8j02yWJNzPlqs'
ADMIN_ID = '7845335174'
CHAT_ID = '-1002827963898'
BACKUP_FILE = 'anime_index_backup.json'
PERMANENT_BACKUP = 'permanent_anime_backup.json'
LAST_MESSAGE_FILE = 'last_processed_message.json'

def clean_anime_name(text):
    """Keep only English letters and spaces"""
    return re.sub(r'[^a-zA-Z\s]', '', text).strip()

def save_to_backup(data, filename):
    """Save data to specified backup file"""
    try:
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Backup failed ({filename}): {str(e)}")

def load_from_backup(filename):
    """Load data from specified backup file"""
    if not os.path.exists(filename):
        return {'posts': []}

    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Restore failed ({filename}): {str(e)}")
        return {'posts': []}

def save_last_message_id(message_id):
    """Save the last processed message ID"""
    try:
        with open(LAST_MESSAGE_FILE, 'w') as f:
            json.dump({'last_message_id': message_id}, f)
    except Exception as e:
        logger.error(f"Failed to save last message ID: {str(e)}")

def get_last_message_id():
    """Get the last processed message ID"""
    if not os.path.exists(LAST_MESSAGE_FILE):
        return None
    try:
        with open(LAST_MESSAGE_FILE, 'r') as f:
            data = json.load(f)
            return data.get('last_message_id')
    except Exception as e:
        logger.error(f"Failed to load last message ID: {str(e)}")
        return None

async def handle_new_message(update: Update, context):
    """Process new channel posts"""
    try:
        if not update.channel_post or str(update.channel_post.chat_id) != CHAT_ID:
            return

        # Skip if we've already processed this message
        last_id = get_last_message_id()
        if last_id and update.channel_post.message_id <= int(last_id):
            return

        # Load both current and permanent backups
        current_data = load_from_backup(BACKUP_FILE)
        permanent_data = load_from_backup(PERMANENT_BACKUP)

        try:
            if not update.channel_post.caption:
                return

            # Process the anime name (English letters only)
            raw_name = update.channel_post.caption.splitlines()[0].strip()
            anime_name = clean_anime_name(raw_name)

            # Skip if name is empty after cleaning
            if not anime_name:
                save_last_message_id(update.channel_post.message_id)
                return

            # Create post link
            post_link = f"https://t.me/c/{str(CHAT_ID).replace('-100', '')}/{update.channel_post.message_id}"

            # Add to both current and permanent backups
            new_entry = {
                'name': anime_name, 
                'link': post_link,
                'timestamp': datetime.now().isoformat(),
                'message_id': update.channel_post.message_id
            }

            current_data.setdefault('posts', []).append(new_entry)
            permanent_data.setdefault('posts', []).append(new_entry)

            save_to_backup(current_data, BACKUP_FILE)
            save_to_backup(permanent_data, PERMANENT_BACKUP)
            save_last_message_id(update.channel_post.message_id)

        except Exception as e:
            logger.error(f"Skipped message {update.channel_post.message_id}: {str(e)}")
            save_last_message_id(update.channel_post.message_id)

    except Exception as e:
        logger.error(f"Error in message handler: {str(e)}")

async def send_index(update: Update, context):
    """Send combined index from both current and permanent backups"""
    if str(update.effective_user.id) != ADMIN_ID:
        return

    try:
        # Load all posts from both backups
        current_data = load_from_backup(BACKUP_FILE)
        permanent_data = load_from_backup(PERMANENT_BACKUP)

        # Combine all posts, newest first
        all_posts = permanent_data.get('posts', []) + current_data.get('posts', [])
        all_posts.sort(key=lambda x: x.get('message_id', 0), reverse=True)

        if not all_posts:
            await update.message.reply_text("✨ No posts indexed yet")
            return

        # Create clean, simple formatted message
        message = ""
        for post in all_posts:
            message += f"<a href='{post['link']}'>{post['name']}</a>\n\n"

        # Send the message with HTML formatting
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=message,
            parse_mode='HTML',
            disable_web_page_preview=True
        )

        # Clear only the current backup after sending
        save_to_backup({'posts': []}, BACKUP_FILE)
        await update.message.reply_text(f"✅ Sent {len(all_posts)} anime posts")

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
        logger.error(f"Index sending failed: {str(e)}")

async def start(update: Update, context):
    """Bot status information"""
    if str(update.effective_user.id) != ADMIN_ID:
        return

    current_data = load_from_backup(BACKUP_FILE)
    permanent_data = load_from_backup(PERMANENT_BACKUP)

    stats = (
        "🤖 Bot Status 🤖\n\n"
        f"📌 New posts waiting: {len(current_data.get('posts', []))}\n"
        f"📚 Permanent archive: {len(permanent_data.get('posts', []))}\n"
        f"⏱ Last update: {datetime.now().strftime('%d %b %Y %H:%M')}\n\n"
        "Use /sendindex to get complete anime collection! MADE BY @CLUTCH008"
    )
    await update.message.reply_text(stats)

async def clear_index(update: Update, context):
    """Clear current index (admin only)"""
    if str(update.effective_user.id) != ADMIN_ID:
        return

    save_to_backup({'posts': []}, BACKUP_FILE)
    await update.message.reply_text("🧹 Current index cleared (permanent archive remains)")

def main():
    """Initialize and run the bot"""
    # Create backup files if they don't exist
    if not os.path.exists(BACKUP_FILE):
        save_to_backup({'posts': []}, BACKUP_FILE)
    if not os.path.exists(PERMANENT_BACKUP):
        save_to_backup({'posts': []}, PERMANENT_BACKUP)
    if not os.path.exists(LAST_MESSAGE_FILE):
        save_last_message_id(0)

    application = Application.builder() \
        .token(BOT_TOKEN) \
        .build()

    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("sendindex", send_index))
    application.add_handler(CommandHandler("clear", clear_index))
    application.add_handler(MessageHandler(
        filters.Chat(int(CHAT_ID)) & filters.UpdateType.CHANNEL_POSTS,
        handle_new_message
    ))

    logger.info("Bot starting with permanent archive...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()

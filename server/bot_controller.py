import time
import asyncio
import logging
from datetime import datetime
from typing import List, Dict
from groupme.groupme_interface import GroupMeInterface
from server.message_manager import MessageManager

# Configure logging
logger = logging.getLogger(__name__)

class BotController:
    """Controls the bot's behavior and GroupMe interaction."""
    
    def __init__(self, bot_group_id: str = None):
        self.groupme_interface = GroupMeInterface(bot_group_id)
        self.message_manager = MessageManager()
        self.running = False
        self.polling_task = None
        
        # Set bot server if provided
        if bot_group_id:
            self.groupme_interface.set_bot_server(bot_group_id)
    
    async def set_bot_server(self, group_id: str):
        """Set the bot server group ID."""
        self.groupme_interface.set_bot_server(group_id)
    
    async def start_polling(self):
        """Start the async polling task."""
        if self.running:
            logger.warning("⚠️ Bot is already running")
            return
        
        logger.info("🚀 Starting bot polling...")
        self.running = True
        self.polling_task = asyncio.create_task(self._polling_loop())
        logger.info("✅ Bot polling started successfully")
    
    async def stop_polling(self):
        """Stop the async polling task."""
        if not self.running:
            logger.warning("⚠️ Bot is not running")
            return
            
        logger.info("🛑 Stopping bot polling...")
        self.running = False
        if self.polling_task:
            self.polling_task.cancel()
            try:
                await self.polling_task
            except asyncio.CancelledError:
                pass
        logger.info("✅ Bot polling stopped successfully")
    
    async def _polling_loop(self):
        """Main async polling loop that runs at configurable intervals."""
        last_polling_interval = None
        initial_polling_interval = self.message_manager.config.get("polling_interval_seconds", 120)
        logger.info(f"🔄 Polling loop started - running every {initial_polling_interval} seconds ({initial_polling_interval/60:.1f} minutes)")
        while self.running:
            try:
                # Get current polling interval from config
                polling_interval = self.message_manager.config.get("polling_interval_seconds", 120)  # Default to 120 seconds (2 minutes)
                
                # Log if polling interval changed
                if last_polling_interval != polling_interval:
                    logger.info(f"🔄 Polling interval updated to {polling_interval} seconds ({polling_interval/60:.1f} minutes)")
                    last_polling_interval = polling_interval
                
                # Process one polling cycle
                await self._process_polling_cycle()
                
                # Wait for the configured interval
                logger.debug(f"⏰ Waiting {polling_interval} seconds until next polling cycle...")
                await asyncio.sleep(polling_interval)
                
            except asyncio.CancelledError:
                logger.info("🛑 Polling loop cancelled")
                break
            except Exception as e:
                logger.error(f"💥 Error in polling loop: {e}")
                logger.info("⏰ Waiting 1 minute before retrying...")
                await asyncio.sleep(60)  # Wait 1 minute on error
    
    async def _process_polling_cycle(self):
        """Process one polling cycle."""
        try:
            logger.info("🔄 Starting polling cycle...")
            
            # Get new messages from GroupMe
            new_messages = self.groupme_interface.poll_new_messages()
            logger.info(f"📨 Found {len(new_messages)} new messages from GroupMe")
            
            # Process each new message
            for msg in new_messages:
                await self._process_incoming_message(msg)
            
            # Check if we should send a random message
            if self.message_manager.should_send_random_message():
                logger.info("🎲 Random message generation triggered - starting async generation")
                # Create task for async generation
                asyncio.create_task(self.message_manager.generate_random_message())
            else:
                logger.debug(f"⏸️ Random message generation skipped - probability check failed")
            
            logger.info("✅ Polling cycle completed")
                
        except Exception as e:
            logger.error(f"💥 Error processing polling cycle: {e}")
    
    async def _process_incoming_message(self, message_data: Dict):
        """Process an incoming message and potentially generate a reply."""
        try:
            # Check if we should reply based on likes
            likes = message_data.get('likes', 0)
            reply_to_id = message_data.get('id')
            original_text = message_data.get('text', '')
            
            logger.info(f"💭 Processing incoming message {reply_to_id} with {likes} likes")
            logger.info(f"  📝 Text: {original_text[:100]}...")
            
            # Generate reply message if probability allows
            # Create task for async generation
            logger.info(f"🎯 Starting async reply generation for message {reply_to_id}")
            username = message_data.get('username', 'Unknown')
            asyncio.create_task(self.message_manager.generate_reply_message(
                reply_to_id, original_text, likes, username
            ))
            
        except Exception as e:
            logger.error(f"💥 Error processing incoming message: {e}")
    
    async def send_selected_message(self, message_id: str) -> bool:
        """Send a selected message to GroupMe."""
        try:
            message_obj = self.message_manager.get_message_by_id(message_id)
            if not message_obj or not message_obj.selected_message:
                logger.warning(f"⚠️ Cannot send message {message_id} - no message object or selected message")
                return False
            
            logger.info(f"📤 Sending message {message_id} to GroupMe")
            logger.info(f"  📝 Content: {message_obj.selected_message[:100]}...")
            
            # Send the message
            if message_obj.reply_to_id:
                # Send as reply with proper GroupMe reply attachment
                logger.info(f"  🔄 Sending as reply to message {message_obj.reply_to_id}")
                response = self.groupme_interface.send_message(
                    message_obj.selected_message, 
                    message_obj.reply_to_id
                )
            else:
                # Send as regular message
                logger.info(f"  📨 Sending as regular message")
                response = self.groupme_interface.send_message(
                    message_obj.selected_message
                )
            
            # Mark as sent
            self.message_manager.mark_message_sent(message_id)
            logger.info(f"✅ Message {message_id} sent successfully")
            return True
            
        except Exception as e:
            logger.error(f"💥 Error sending message {message_id}: {e}")
            return False
    
    async def get_pending_messages(self) -> List[Dict]:
        """Get all pending messages for the frontend."""
        pending = self.message_manager.get_pending_messages()
        return [msg.to_dict() for msg in pending]
    
    async def get_config(self) -> Dict:
        """Get current configuration."""
        return self.message_manager.config.copy()
    
    async def update_config(self, new_config: Dict):
        """Update configuration."""
        self.message_manager.update_config(new_config)
    
    async def generate_introduction(self) -> Dict:
        """Generate an introduction message asynchronously."""
        message_obj = await self.message_manager.generate_introduction_message()
        return message_obj.to_dict()
    
    async def generate_test_message(self) -> Dict:
        """Generate a test message asynchronously."""
        message_obj = await self.message_manager.generate_manual_message()
        return message_obj.to_dict()
    
    async def select_message_option(self, message_id: str, option_index: int) -> bool:
        """Select a specific message option."""
        message_obj = self.message_manager.get_message_by_id(message_id)
        if message_obj:
            return message_obj.select_message(option_index)
        return False
    
    async def delete_message(self, message_id: str):
        """Delete a message."""
        self.message_manager.delete_message(message_id)
    
    async def get_bot_status(self) -> Dict:
        """Get bot status information."""
        try:
            bot_info = self.groupme_interface.get_bot_server_info()
            
            # Calculate current probability for random message generation
            polling_interval = self.message_manager.config.get("polling_interval_seconds", 120)  # Default to 120 seconds (2 minutes)
            seconds_per_day = 24 * 60 * 60  # 24 hours * 60 minutes * 60 seconds
            cycles_per_day = seconds_per_day / polling_interval
            target_messages = self.message_manager.config['random_messages_per_day']
            probability_per_cycle = target_messages / cycles_per_day
            
            return {
                'bot_server_set': self.groupme_interface.bot_group_id is not None,
                'bot_server_info': bot_info,
                'messages_per_day': self.message_manager.messages_per_day,
                'target_messages_per_day': target_messages,
                'polling_interval_seconds': polling_interval,
                'probability_per_cycle': round(probability_per_cycle, 4),
                'pending_messages': len(self.message_manager.get_pending_messages()),
                'generating_messages': self.message_manager.get_generating_messages_count()
            }
        except Exception as e:
            return {
                'error': str(e)
            }

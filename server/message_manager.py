import json
import time
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from message_gen.message_generator import MessageGenerator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class MessageObject:
    """Represents a message with multiple generation attempts and metadata."""
    
    def __init__(self, message_type: str, reply_to_id: str = None, original_message: str = None, username: str = None):
        self.id = str(int(time.time() * 1000))  # Unique ID
        self.message_type = message_type  # 'random', 'reply', 'introduction', 'manual'
        self.reply_to_id = reply_to_id
        self.original_message = original_message
        self.username = username  # Username of the person being replied to
        self.timestamp = datetime.now()
        self.generated_messages = []
        self.selected_message = None
        self.sent = False
        self.deleted = False
        self.generating = False
    
    def add_generated_message(self, message: str):
        """Add a generated message option."""
        self.generated_messages.append(message)
    
    def start_generation(self):
        """Mark message as currently generating."""
        self.generating = True
    
    def stop_generation(self):
        """Mark message as finished generating."""
        self.generating = False
    
    def select_message(self, message_index: int):
        """Select a specific generated message."""
        if 0 <= message_index < len(self.generated_messages):
            self.selected_message = self.generated_messages[message_index]
            return True
        return False
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'message_type': self.message_type,
            'reply_to_id': self.reply_to_id,
            'original_message': self.original_message,
            'username': self.username,
            'timestamp': self.timestamp.isoformat(),
            'generated_messages': self.generated_messages,
            'selected_message': self.selected_message,
            'sent': self.sent,
            'deleted': self.deleted,
            'generating': self.generating
        }

class MessageManager:
    """Manages message generation, storage, and selection."""
    
    def __init__(self, config_path: str = "server/config.json"):
        self.config_path = config_path
        self.config = self.load_config()
        self.message_generator = MessageGenerator()
        self.messages: List[MessageObject] = []
        self.last_random_message_time = datetime.now()
        self.messages_per_day = 0
        self.reset_daily_counter()
    
    def load_config(self) -> Dict:
        """Load configuration from JSON file."""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {
                "random_messages_per_day": 5,
                "reply_chance_per_like": 0.3,
                "minimum_reply_chance": 0.01,
                "message_generation_tries": 3,
                "polling_interval_seconds": 120,
                "introduction_prompt": "Introduce yourself as a friendly bot that's here to chat and help out!"
            }
    
    def save_config(self):
        """Save current configuration to JSON file."""
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def update_config(self, new_config: Dict):
        """Update configuration and save to file."""
        # Validate polling interval
        if 'polling_interval_seconds' in new_config:
            polling_interval = new_config['polling_interval_seconds']
            if polling_interval <= 0:
                raise ValueError("Polling interval must be greater than 0 seconds")
            if polling_interval > 3600:
                raise ValueError("Polling interval cannot be more than 3600 seconds (1 hour)")
        
        self.config.update(new_config)
        self.save_config()
    
    def reset_daily_counter(self):
        """Reset daily message counter."""
        self.messages_per_day = 0
        self.last_random_message_time = datetime.now()
    
    def should_send_random_message(self) -> bool:
        """Check if it's time to send a random message based on probability."""
        now = datetime.now()
        
        # Reset counter if it's a new day
        if (now - self.last_random_message_time).days >= 1:
            self.reset_daily_counter()
        
        # Calculate probability based on desired messages per day
        # Use configurable polling interval to calculate cycles per day
        polling_interval = self.config.get("polling_interval_seconds", 120)  # Default to 120 seconds (2 minutes)
        seconds_per_day = 24 * 60 * 60  # 24 hours * 60 minutes * 60 seconds
        cycles_per_day = seconds_per_day / polling_interval
        target_messages = self.config["random_messages_per_day"]
        probability_per_cycle = target_messages / cycles_per_day
        
        # Use random chance to determine if we should send a message
        import random
        should_send = random.random() < probability_per_cycle
        
        if should_send:
            logger.info(f"🎲 Random message generation triggered - probability {probability_per_cycle:.4f} ({target_messages} messages per day target)")
        else:
            logger.debug(f"🎲 Random message generation skipped - probability {probability_per_cycle:.4f} too low")
        
        return should_send
    
    async def _execute_generation_tasks(self, message_obj: MessageObject, tasks: List, message_type: str) -> None:
        """Shared helper function to execute generation tasks and process results."""
        logger.info(f"⏳ Waiting for {len(tasks)} concurrent {message_type} generation tasks to complete...")
        
        try:
            messages = await asyncio.gather(*tasks, return_exceptions=True)
            
            success_count = 0
            error_count = 0
            
            for i, message in enumerate(messages):
                if isinstance(message, Exception):
                    error_msg = f"Error generating {message_type}: {message}"
                    message_obj.add_generated_message(error_msg)
                    error_count += 1
                    logger.error(f"  ❌ {message_type.capitalize()} task {i+1} failed: {message}")
                else:
                    message_obj.add_generated_message(message)
                    success_count += 1
                    logger.info(f"  ✅ {message_type.capitalize()} task {i+1} completed: {message[:50]}...")
            
            logger.info(f"🎯 {message_type.capitalize()} generation completed - {success_count} successful, {error_count} failed")
            
        except Exception as e:
            error_msg = f"Error in {message_type} generation: {e}"
            message_obj.add_generated_message(error_msg)
            logger.error(f"💥 Critical error in {message_type} generation: {e}")
    
    async def generate_random_message(self) -> MessageObject:
        """Generate a random message object."""
        message_obj = MessageObject("random")
        message_obj.start_generation()
        self.messages.append(message_obj)
        
        logger.info(f"🚀 Starting random message generation (ID: {message_obj.id}) - {self.config['message_generation_tries']} attempts")
        
        # Create all generation tasks concurrently
        tasks = []
        for i in range(self.config["message_generation_tries"]):
            logger.info(f"  📝 Creating generation task {i+1}/{self.config['message_generation_tries']}")
            tasks.append(self.message_generator.generate_message())
        
        # Execute tasks using shared helper
        await self._execute_generation_tasks(message_obj, tasks, "random")
        
        message_obj.stop_generation()
        self.messages_per_day += 1
        self.last_random_message_time = datetime.now()
        
        logger.info(f"🏁 Random message generation finished (ID: {message_obj.id}) - Total messages today: {self.messages_per_day}")
        
        return message_obj
    
    async def generate_reply_message(self, reply_to_id: str, original_message: str, likes: int, username: str = None) -> Optional[MessageObject]:
        """Generate a reply message based on like count and chance."""
        # Calculate reply probability based on likes
        reply_probability = min(self.config["reply_chance_per_like"] * likes, 1.0)

        # higher probability if message references Keller
        if "Keller" in original_message or "keller" in original_message:
            reply_probability += 1
        
        if reply_probability < self.config["minimum_reply_chance"]:
            reply_probability = self.config["minimum_reply_chance"]
        
        # Random decision based on probability
        import random
        if random.random() > reply_probability:
            logger.info(f"🎲 Reply generation skipped - probability {reply_probability:.2f} too low (likes: {likes})")
            return None
        
        message_obj = MessageObject("reply", reply_to_id, original_message, username)
        message_obj.start_generation()
        self.messages.append(message_obj)
        
        logger.info(f"💬 Starting reply generation (ID: {message_obj.id}) to message {reply_to_id} with {likes} likes - {self.config['message_generation_tries']} attempts")
        logger.info(f"  📖 Original message: {original_message[:100]}...")
        
        # Create all generation tasks concurrently
        tasks = []
        for i in range(self.config["message_generation_tries"]):
            logger.info(f"  📝 Creating reply generation task {i+1}/{self.config['message_generation_tries']}")
            tasks.append(self.message_generator.generate_reply(original_message, username))
        
        # Execute tasks using shared helper
        await self._execute_generation_tasks(message_obj, tasks, "reply")
        
        message_obj.stop_generation()
        logger.info(f"🏁 Reply generation finished (ID: {message_obj.id})")
        
        return message_obj
    
    async def generate_introduction_message(self) -> MessageObject:
        """Generate an introduction message."""
        message_obj = MessageObject("introduction")
        message_obj.start_generation()
        self.messages.append(message_obj)
        
        prompt = self.config["introduction_prompt"]
        
        logger.info(f"👋 Starting introduction generation (ID: {message_obj.id}) - {self.config['message_generation_tries']} attempts")
        logger.info(f"  📝 Prompt: {prompt[:100]}...")
        
        # Create all generation tasks concurrently
        tasks = []
        for i in range(self.config["message_generation_tries"]):
            logger.info(f"  📝 Creating introduction generation task {i+1}/{self.config['message_generation_tries']}")
            tasks.append(self.message_generator.generate_introduction(prompt))
        
        # Execute tasks using shared helper
        await self._execute_generation_tasks(message_obj, tasks, "introduction")
        
        message_obj.stop_generation()
        logger.info(f"🏁 Introduction generation finished (ID: {message_obj.id})")
        
        return message_obj
    
    async def generate_manual_message(self) -> MessageObject:
        """Generate a manual test message."""
        message_obj = MessageObject("manual")
        message_obj.start_generation()
        self.messages.append(message_obj)
        
        logger.info(f"🧪 Starting manual test message generation (ID: {message_obj.id}) - {self.config['message_generation_tries']} attempts")
        
        # Create all generation tasks concurrently
        tasks = []
        for i in range(self.config["message_generation_tries"]):
            logger.info(f"  📝 Creating manual generation task {i+1}/{self.config['message_generation_tries']}")
            tasks.append(self.message_generator.generate_message())
        
        # Execute tasks using shared helper
        await self._execute_generation_tasks(message_obj, tasks, "manual")
        
        message_obj.stop_generation()
        logger.info(f"🏁 Manual message generation finished (ID: {message_obj.id})")
        
        return message_obj
    
    def get_pending_messages(self) -> List[MessageObject]:
        """Get all messages that haven't been sent or deleted."""
        return [msg for msg in self.messages if not msg.sent and not msg.deleted]
    
    def get_generating_messages_count(self) -> int:
        """Get count of messages currently being generated."""
        return len([msg for msg in self.messages if msg.generating])
    
    def get_message_by_id(self, message_id: str) -> Optional[MessageObject]:
        """Get a specific message by ID."""
        for msg in self.messages:
            if msg.id == message_id:
                return msg
        return None
    
    def mark_message_sent(self, message_id: str):
        """Mark a message as sent."""
        msg = self.get_message_by_id(message_id)
        if msg:
            msg.sent = True
    
    def delete_message(self, message_id: str):
        """Mark a message as deleted."""
        msg = self.get_message_by_id(message_id)
        if msg:
            msg.deleted = True
    
    def cleanup_old_messages(self, days: int = 7):
        """Remove messages older than specified days."""
        cutoff_time = datetime.now() - timedelta(days=days)
        self.messages = [msg for msg in self.messages if msg.timestamp > cutoff_time]

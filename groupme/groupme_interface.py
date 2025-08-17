import requests
import json
import time
from datetime import datetime
from typing import List, Dict, Optional
from env import GROUPME_ACCESS_TOKEN

class GroupMeInterface:
    """
    Interface for interacting with GroupMe API, specifically designed for bot operations.
    Tracks a specific bot server and provides message polling and sending capabilities.
    """
    
    def __init__(self, bot_group_id: str = None, access_token: str = None):
        """
        Initialize the GroupMe interface.
        
        Args:
            bot_group_id (str): The GroupMe group ID for the bot server. If None, will try to load from env.
            access_token (str): GroupMe API access token. If None, will load from env.
        """
        self.access_token = access_token or GROUPME_ACCESS_TOKEN
        if not self.access_token:
            raise ValueError("GroupMe access token is required. Set GROUPME_ACCESS_TOKEN in .env file or pass as parameter.")
        
        self.bot_group_id = bot_group_id
        self.last_message_time = 0
        self.current_user_id = None
        
        self.base_url = "https://api.groupme.com/v3"
        self.headers = {
            'X-Access-Token': self.access_token,
            'Content-Type': 'application/json'
        }
        
        # Get current user info on initialization
        self._get_current_user()
    
    def _get_current_user(self) -> None:
        """Get and store the current authenticated user's information."""
        url = f"{self.base_url}/users/me"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            user_info = data.get('response', {})
            self.current_user_id = user_info.get('id')
            
            if not self.current_user_id:
                raise ValueError("Could not determine current user ID")
                
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Error fetching current user info: {e}")
    
    def set_bot_server(self, group_id: str) -> None:
        """
        Set the bot server group ID.
        
        Args:
            group_id (str): The GroupMe group ID for the bot server
        """
        self.bot_group_id = group_id
        self.last_message_time = 0  # Reset last message time when changing servers
    
    def get_user_groups(self) -> List[Dict]:
        """
        Get a list of all groups the current user is a member of.
        
        Returns:
            List[Dict]: List of group information dictionaries
            
        Raises:
            ValueError: If access token is invalid or API request fails
        """
        if not self.access_token:
            raise ValueError("GroupMe access token is required")
        
        url = f"{self.base_url}/groups"
        params = {'per_page': 100}
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get('response', [])
            
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Error fetching groups: {e}")
    
    def poll_new_messages(self) -> List[Dict]:
        """
        Poll for new messages in the bot server since last check.
        Only returns messages from other users (filters out current user).
        
        Returns:
            List[Dict]: List of new message dictionaries with reply information
            
        Raises:
            ValueError: If bot server is not set or access token is invalid
        """
        if not self.bot_group_id:
            raise ValueError("Bot server group ID not set. Use set_bot_server() first.")
        
        if not self.access_token:
            raise ValueError("GroupMe access token is required")
        
        url = f"{self.base_url}/groups/{self.bot_group_id}/messages"
        params = {'limit': 100}
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()
            messages = data.get('response', {}).get('messages', [])
            
            first_run = self.last_message_time == 0
            new_messages = []
            for msg in messages:
                # Check if message is newer than last check
                if msg.get('created_at', 0) > self.last_message_time:
                    # Filter out messages from current user
                    if msg.get('user_id') != self.current_user_id:
                        # Extract only necessary information for replies
                        message_info = {
                            'id': msg.get('id'),
                            'text': msg.get('text', ''),
                            'user_id': msg.get('user_id'),
                            'name': msg.get('name', 'Unknown'),
                            'created_at': msg.get('created_at'),
                            'likes': len(msg.get('favorited_by', [])),
                            'group_id': self.bot_group_id,
                            'reply_to_id': msg.get('id'),  # For API reply functionality
                            'username': msg.get('name', 'Unknown')  # Username for reply formatting
                        }
                        new_messages.append(message_info)
            
            # Update last message time if we found new messages
            if new_messages:
                self.last_message_time = max(msg['created_at'] for msg in new_messages)
            
            if first_run:
                print("First run, returning empty list")
                return []
            return new_messages
            
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Error fetching messages from bot server: {e}")
    
    def send_message(self, text: str, reply_to_id: str = None) -> Dict:
        """
        Send a message in the bot server.
        
        Args:
            text (str): The message text to send
            reply_to_id (str): Optional message ID to reply to
            
        Returns:
            Dict: Response from the API containing message details
            
        Raises:
            ValueError: If bot server is not set, access token is invalid, or API request fails
        """
        if not self.bot_group_id:
            raise ValueError("Bot server group ID not set. Use set_bot_server() first.")
        
        if not self.access_token:
            raise ValueError("GroupMe access token is required")
        
        if not text.strip():
            raise ValueError("Message text cannot be empty")
        
        url = f"{self.base_url}/groups/{self.bot_group_id}/messages"
        
        # Prepare message data
        message_data = {
            'message': {
                'source_guid': str(int(time.time())),  # Unique identifier
                'text': text
            }
        }
        
        # Add reply attachment if specified
        if reply_to_id:
            message_data['message']['attachments'] = [
                {
                    'type': 'reply',
                    'reply_id': reply_to_id,
                    'base_reply_id': reply_to_id
                }
            ]
        
        try:
            response = requests.post(url, headers=self.headers, json=message_data)
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Error sending message: {e}")
    
    def get_bot_server_info(self) -> Optional[Dict]:
        """
        Get information about the currently set bot server.
        
        Returns:
            Dict: Bot server information or None if not set
        """
        if not self.bot_group_id:
            return None
        
        try:
            url = f"{self.base_url}/groups/{self.bot_group_id}"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            return data.get('response', {})
            
        except requests.exceptions.RequestException:
            return None


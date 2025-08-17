import requests
import json
import time
import pandas as pd
from datetime import datetime
from typing import List, Dict
import os
from dotenv import load_dotenv
from env import GROUPME_ACCESS_TOKEN

class GroupMeScraper:
    """
    A simple GroupMe scraper that can retrieve messages from groups with batch processing.
    """
    
    def __init__(self, access_token: str = None):
        """
        Initialize the GroupMe scraper.
        
        Args:
            access_token (str): GroupMe API access token. If None, will try to load from config or .env file.
        """
        self.access_token = access_token or GROUPME_ACCESS_TOKEN
        if not self.access_token:
            raise ValueError("GroupMe access token is required. Set GROUPME_ACCESS_TOKEN in .env file or pass as parameter.")
        
        self.base_url = "https://api.groupme.com/v3"
        self.headers = {
            'X-Access-Token': self.access_token,
            'Content-Type': 'application/json'
        }
    
    def display_groups(self) -> List[Dict]:
        """
        Display a list of all groups the user is a member of.
        
        Returns:
            List[Dict]: List of group information dictionaries
        """
        url = f"{self.base_url}/groups"
        params = {'per_page': 100}
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()
            groups = data.get('response', [])
            
            print(f"\nFound {len(groups)} groups:")
            for i, group in enumerate(groups, 1):
                group_name = group.get('name', 'Unknown')
                group_id = group.get('id')
                print(f"{i}. {group_name} (ID: {group_id})")
            
            return groups
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching groups: {e}")
            return []
    
    def get_group_messages(self, group_id: str, limit: int = 100, before_id: str = None) -> List[Dict]:
        """
        Get a batch of messages from a specific group.
        
        Args:
            group_id (str): The GroupMe group ID
            limit (int): Number of messages to retrieve (max 100)
            before_id (str): Message ID to get messages before (for pagination)
            
        Returns:
            List[Dict]: List of message dictionaries
        """
        url = f"{self.base_url}/groups/{group_id}/messages"
        params = {'limit': min(limit, 100)}
        
        if before_id:
            params['before_id'] = before_id
            
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get('response', {}).get('messages', [])
        except requests.exceptions.RequestException as e:
            print(f"Error fetching messages for group {group_id}: {e}")
            return []
    
    def get_all_messages_and_save_to_csv(self, group_id: str, group_name: str = None, filename: str = None) -> str:
        """
        Get all messages from a specific group using batch processing and save to CSV.
        Only retrieves the current user's messages and stops at July 2021.
        This method can handle tens of thousands of messages by loading in batches of 100.
        
        Args:
            group_id (str): The GroupMe group ID
            group_name (str): Name of the group (for filename if not provided)
            filename (str): Output CSV filename (auto-generated if None)
            
        Returns:
            str: Path to the exported CSV file
        """
        all_messages = []
        before_id = None
        batch_count = 0
        
        # Get current user info to filter messages
        current_user = self.get_current_user()
        if not current_user:
            print("Could not determine current user. Stopping.")
            return ""
        
        current_user_id = current_user.get('id')
        current_user_name = current_user.get('name', 'Unknown')
        
        print(f"Starting to retrieve YOUR messages from group {group_id}...")
        print(f"User: {current_user_name} (ID: {current_user_id})")
        print("Will stop when reaching messages from July 2021 or earlier...")
        
        # July 2021 timestamp (July 1, 2021)
        july_2021_timestamp = 1625097600
        
        while True:
            batch_count += 1
            print(f"Fetching batch {batch_count}...")
            
            try:
                messages = self.get_group_messages(group_id, limit=100, before_id=before_id)
                
                if not messages:
                    print(f"Batch {batch_count} returned no messages - reached the end")
                    break
                
                # Filter to only current user's messages
                user_messages = [msg for msg in messages if msg.get('user_id') == current_user_id]
                
                # Check if any messages are from July 2021 or earlier
                old_messages = [msg for msg in user_messages if msg.get('created_at', 0) <= july_2021_timestamp]
                
                if old_messages:
                    print(f"Batch {batch_count}: Found messages from July 2021 or earlier. Stopping.")
                    # Add only the newer messages from this batch
                    newer_messages = [msg for msg in user_messages if msg.get('created_at', 0) > july_2021_timestamp]
                    all_messages.extend(newer_messages)
                    break
                
                all_messages.extend(user_messages)
                print(f"Batch {batch_count}: Retrieved {len(user_messages)} of your messages. Total so far: {len(all_messages)}")
                
                # Get the ID of the oldest message for next pagination
                before_id = messages[-1]['id']
                
                # Rate limiting - GroupMe allows 60 requests per minute
                time.sleep(1.1)
                
            except Exception as e:
                print(f"Error fetching batch {batch_count}: {e}")
                break
        
        print(f"\nRetrieved {len(all_messages)} of your messages in {batch_count} batches")
        
        if not all_messages:
            print("No messages to save")
            return ""
        
        # Format messages for CSV
        formatted_messages = []
        for msg in all_messages:
            formatted_msg = {
                'message_id': msg.get('id'),
                'timestamp': msg.get('created_at'),
                'datetime': datetime.fromtimestamp(msg.get('created_at', 0)).isoformat(),
                'user_name': msg.get('name', 'Unknown'),
                'user_id': msg.get('user_id'),
                'text': msg.get('text', ''),
                'attachments': len(msg.get('attachments', [])),
                'likes': len(msg.get('favorited_by', [])),
                'group_id': msg.get('group_id'),
                'source': msg.get('source', {}).get('type', 'unknown')
            }
            formatted_messages.append(formatted_msg)
        
        # Generate filename if not provided
        if not filename:
            if not group_name:
                group_name = f"group_{group_id}"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{current_user_name}_{group_name}_messages_{timestamp}.csv"
        
        # Save to CSV
        df = pd.DataFrame(formatted_messages)
        df.to_csv(filename, index=False)
        print(f"Messages saved to: {filename}")
        
        return filename
    
    def get_current_user(self) -> Dict:
        """
        Get the current authenticated user's information.
        
        Returns:
            Dict: User information dictionary with 'id' and 'name'
        """
        url = f"{self.base_url}/users/me"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            user_info = data.get('response', {})
            return {
                'id': user_info.get('id'),
                'name': user_info.get('name', 'Unknown')
            }
        except requests.exceptions.RequestException as e:
            print(f"Error fetching current user info: {e}")
            return {}


def main():
    """
    Main execution function for the GroupMe scraper.
    This function demonstrates the two core functions:
    1. Display a list of groups
    2. Get YOUR messages from a specific group (stopping at July 2021) and save to CSV
    """
    # Load environment variables
    load_dotenv()
    
    # Initialize the scraper
    scraper = GroupMeScraper()
    
    print("=== Simple GroupMe Scraper ===")
    print("This scraper will:")
    print("- Only get YOUR messages (not all group messages)")
    print("- Stop when reaching messages from July 2021 or earlier")
    print("- Handle groups with tens of thousands of messages!")
    
    # Function 1: Display all groups
    print("\n--- Function 1: Display Groups ---")
    groups = scraper.display_groups()
    
    if not groups:
        print("No groups found. Make sure you have access to at least one GroupMe group.")
        return
    
    # Function 2: Get YOUR messages from a specific group and save to CSV
    print("\n--- Function 2: Get YOUR Messages and Save to CSV ---")
    
    try:
        # Let user choose a group
        choice = int(input(f"\nEnter group number to scrape (1-{len(groups)}): ")) - 1
        if choice < 0 or choice >= len(groups):
            print("Invalid choice!")
            return
        
        selected_group = groups[choice]
        group_name = selected_group.get('name', 'Unknown')
        group_id = selected_group.get('id')
        
        print(f"\nSelected: {group_name}")
        print(f"Group ID: {group_id}")
        print(f"Note: Only YOUR messages will be retrieved, stopping at July 2021")
        
        # Ask for custom filename (optional)
        custom_filename = input("Enter custom CSV filename (or press Enter for auto-generated): ").strip()
        filename = custom_filename if custom_filename else None
        
        # Get all YOUR messages and save to CSV
        print(f"\nStarting to retrieve YOUR messages from {group_name}...")
        print("This may take a while for large groups...")
        print("Will automatically stop when reaching July 2021 messages...")
        
        csv_file = scraper.get_all_messages_and_save_to_csv(
            group_id=group_id,
            group_name=group_name,
            filename=filename
        )
        
        if csv_file:
            print(f"\n✅ Success! Your messages saved to: {csv_file}")
            print(f"You can now open this CSV file in Excel, Google Sheets, or any spreadsheet application.")
        else:
            print("\n❌ No messages were retrieved or saved.")
    
    except ValueError:
        print("Please enter a valid number.")
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nGoodbye!")
    except Exception as e:
        print(f"Unexpected error: {e}") 
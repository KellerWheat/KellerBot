"""
Environment configuration for KellerBot.
Contains essential access tokens and API keys.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# GroupMe API access token
GROUPME_ACCESS_TOKEN = os.getenv('GROUPME_ACCESS_TOKEN')

# OpenAI API key for message generation
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

BOT_GROUP_ID = os.getenv('BOT_GROUP_ID', None)

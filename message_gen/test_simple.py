#!/usr/bin/env python3
"""
Simple test script for the message generator.
"""

import os
import asyncio
from message_generator import MessageGenerator

async def main():
    """Test the message generator."""
    
    # Check if OpenAI API key is set
    if not os.getenv('OPENAI_API_KEY'):
        print("❌ OPENAI_API_KEY not found. Please set it in your .env file")
        return
    
    try:
        # Initialize the message generator
        generator = MessageGenerator()
        print("✅ Message generator initialized successfully!")
        
        # Show loaded data
        print(f"Loaded {len(generator.common_phrases)} common phrases")
        print(f"Loaded {len(generator.message_types)} message types")
        
        # Generate a few messages
        print("\n🧪 Generating messages...")
        i = 1
        for message_type in generator.message_types:
            message = await generator.generate_message(message_type)
            print(f"{i}. {message}")
            i += 1
        
        # Test reply generation
        print("\n💬 Testing reply generation...")
        test_message = "Hey everyone, what's up?"
        reply = await generator.generate_reply(test_message)
        print(f"Reply to '{test_message}':")
        print(f"'{reply}'")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())

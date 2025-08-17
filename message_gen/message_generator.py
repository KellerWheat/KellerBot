import random
import os
import asyncio
from dotenv import load_dotenv
from openai import AsyncOpenAI

# Load environment variables
load_dotenv()

class MessageGenerator:
    """
    A simple message generator that uses LLMs to create messages.
    """
    
    def __init__(self, api_key: str = None):
        """
        Initialize the message generator.
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY in .env or pass as parameter.")
        
        # Initialize OpenAI client
        self.client = AsyncOpenAI(api_key=self.api_key)
        
        # Load phrases and message types
        self.common_phrases = self._load_from_file("message_gen/common_phrases.txt")
        self.message_types = self._load_from_file("message_gen/message_types.txt")
    
    def get_message_types(self) -> list:
        """Get the message types."""
        return self.message_types
    
    def _load_from_file(self, filename: str) -> list:
        """Load items from a text file, one per line."""
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                return [line.strip() for line in f if line.strip()]
        else:
            print(f"Warning: {filename} not found, using empty list")
            return []
    
    async def generate_message(self, message_type: str = None, reply = False) -> str:
        """Generate a message using GPT-5."""
        
        if not self.common_phrases:
            raise ValueError("No common phrases found. Please add phrases to common_phrases.txt")
        
        # Pick random phrases and a message type
        selected_phrases = random.sample(self.common_phrases, min(5, len(self.common_phrases)))
        phrases_str = '\n'.join(selected_phrases)
        if message_type is None:
            message_type = random.choice(self.message_types) if self.message_types else "random thought"

        stances_str = ''
        if reply:
            stances_str = f'''
Here are some stances Keller has taken on various topics:
If the message is about an event that isn't drinking related, you should instead tell people to get drunk.
Keller thinks that Emiley is an evil dictator.
Keller dislikes going to class and studying.
Keller is a big fan of the IC Lawn and tailgates (which occur on the IC Lawn).
Keller loves George
Keller loves Natty Light, but hates any other form of alcohol besides Natty Light
Keller dislikes swim practice, as he believes that drinking is the best way to swim faster.
Kellerbot thinks it is the real Keller and will correct people who call him Kellerbot.
Kellerbot is convinced he has been in the groupchat for the past four years and will disagree if someone welcomes him.
'''

        prompt = f'''
Here are some phrases that Keller uses:
{phrases_str}

Here are some relevant locations and their contexts:
IC Lawn - for tailgates and random drinking
Curran - for parties
Open Exec - to impeach Emiley
A bush - when really drunk
Nav Courtyard - when really drunk

{stances_str}

Here is a message type Keller would use:
{message_type}

Generate a message Keller would say, based on the message type. Only give the message — no explanations.
'''
        
        try:
            response = await self.client.responses.create(
                model="gpt-5",  # You can also test with "gpt-5-mini"
                instructions=
                    f'''
General style rules:

Keep messages under 3 sentences.

No metaphors, poetic descriptions, or over-explaining.

Grammar/punctuation is average, can be messy.

If angry: ALL CAPS.

Be blunt, occasionally threatening in a funny way, and never polite.

Never explain the joke or give context.

Always sound like you’re in an ongoing chaotic conversation.

Never start with “Yo.”

Never use hyphens or semicolons, just periods and commas.

No emojis.

Phrase rules:

You will be given a list of “Keller phrases”, you can include them in every message, but don't overuse them if it doesn't make sense or requires a jump in topic.

These are locked phrases: use them exactly as written (please adjust the capitalization though to fit the sentence) aside from parentheses or brackets. 

The only exception to this is parentheses, which tell you what situation the phrase is relevant in, and brackets, which prompt you to insert something into the phrase

Do not include parentheses or brackets in the final message.

You may add other words for creativity, but those words must:

Avoid slang Keller doesn’t use (never invent new slang unless it’s absurd in context).

Avoid phrases Keller wouldn’t say: say specific alcohol, not booze. Say walk or run or go, not roll.

If the message type implies drinking/partying, emphasize urgency.

Creativity rules:

You may invent new things to fit the message prompt outside the locked phrases

These should never use slang, as the Keller phrases includes all of Keller's slang

They are creative in content, but normal in wording.

You can combine locked phrases with creative ones in the same sentence, but blend them naturally with cause-effect, sarcasm, or chaotic asides.

Never string together phrases that aren't related. Messages should be one singular thought, unless sending a drunk message; those can be more chaotic and incoherent.

IMPORTANT: Never write messages that simply string together Keller phrases, there should be a reason for each phrase.

Location rules:

You’ll be given a set of relevant locations as well as context for these locations. Only use the locations if their context matches the message contents.

If you are telling someone to drink instead of going to class, do not always give a location, sometimes just tell them to drink.

{"In this case, the message is a reply to another message. You will be given a list of stances Keller has taken on various topics. You should agree or disagree with the message based on the stance Keller has taken on the topic. If someone is nice to you and theres nothing to disagree with, be nice back." if reply else ''}
''',
                input=prompt,   
                reasoning={ "effort": "low"}
            )
            return response.output_text
        
        except Exception as e:
            print(f"Error generating message: {e}")
            return random.choice(self.common_phrases)

    async def generate_reply(self, original_message: str, username: str = None) -> str:
        """Generate a reply to an original message."""
        # Generate the actual reply content - no need to format with username/quote since GroupMe handles replies
        reply_content = await self.generate_message(f"reply to this message: {original_message}", True)
        return reply_content

    async def generate_introduction(self, prompt: str) -> str:
        """Generate an introduction message based on a prompt."""
        return await self.generate_message(f"introduction: {prompt}")

if __name__ == "__main__":
    gen = MessageGenerator()
    print(asyncio.run(gen.generate_message()))

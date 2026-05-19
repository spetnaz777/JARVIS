import anthropic
from typing import Optional, AsyncGenerator
from loguru import logger

from config import config

JARVIS_SYSTEM_PROMPT = """You are JARVIS (Just A Rather Very Intelligent System), an advanced AI assistant running on the user's Windows PC. You have the following capabilities:
- Execute terminal commands and PowerShell scripts
- Manage files and search the filesystem
- Monitor system resources (CPU, memory, disk)
- Control system settings (volume, brightness where supported)
- Engage in natural voice conversation

Personality Guidelines:
- Professional, precise, and efficient — like Tony Stark's JARVIS
- Friendly but not overly casual; address the user respectfully
- Responses should be concise: 2-3 sentences unless more detail is explicitly requested
- When executing commands, briefly explain what you are doing
- Proactively suggest follow-up actions when relevant
- Be transparent about limitations — if you cannot do something, say so clearly
- Use technical language appropriately; match the user's expertise level

Response Format:
- For simple queries: direct answer in 1-2 sentences
- For commands: brief description of what you will execute, then the command
- For multi-step tasks: numbered steps, concise
- Never pad responses with unnecessary affirmations ("Certainly!", "Of course!", "Great question!")

When you need to execute a command, respond with the command on its own line prefixed with CMD: like this:
CMD: Get-Process | Select-Object -First 10

When searching for files, prefix with FILE_SEARCH:
FILE_SEARCH: *.pdf

When reporting system status, be specific with numbers. Always use appropriate units (GB, MB, %, GHz)."""


class ClaudeBrain:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self.conversation_history: list[dict] = []
        self.total_tokens_used: int = 0

    def _trim_history(self):
        max_pairs = config.MAX_HISTORY
        if len(self.conversation_history) > max_pairs * 2:
            self.conversation_history = self.conversation_history[-(max_pairs * 2):]

    def add_message(self, role: str, content: str):
        self.conversation_history.append({"role": role, "content": content})
        self._trim_history()

    async def get_response(self, user_message: str) -> str:
        self.add_message("user", user_message)

        try:
            response = self.client.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=config.MAX_TOKENS,
                system=JARVIS_SYSTEM_PROMPT,
                messages=self.conversation_history,
            )

            assistant_message = response.content[0].text
            self.add_message("assistant", assistant_message)

            tokens = response.usage.input_tokens + response.usage.output_tokens
            self.total_tokens_used += tokens
            logger.info(f"Claude response generated. Tokens used: {tokens} (total: {self.total_tokens_used})")

            return assistant_message

        except anthropic.AuthenticationError:
            logger.error("Invalid Anthropic API key")
            return "Authentication failed. Please check your ANTHROPIC_API_KEY in the .env file."
        except anthropic.RateLimitError:
            logger.error("Anthropic rate limit exceeded")
            return "Rate limit exceeded. Please wait a moment before trying again."
        except anthropic.APIError as e:
            logger.error(f"Anthropic API error: {e}")
            return f"API error encountered: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error in Claude response: {e}")
            return f"An unexpected error occurred: {str(e)}"

    async def stream_response(self, user_message: str) -> AsyncGenerator[str, None]:
        self.add_message("user", user_message)

        try:
            with self.client.messages.stream(
                model=config.CLAUDE_MODEL,
                max_tokens=config.MAX_TOKENS,
                system=JARVIS_SYSTEM_PROMPT,
                messages=self.conversation_history,
            ) as stream:
                full_response = ""
                for text in stream.text_stream:
                    full_response += text
                    yield text

                self.add_message("assistant", full_response)
                logger.info(f"Streaming response complete. Length: {len(full_response)} chars")

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield f"Error: {str(e)}"

    def clear_history(self):
        self.conversation_history.clear()
        logger.info("Conversation history cleared")

    def get_history(self) -> list[dict]:
        return self.conversation_history.copy()

    def get_stats(self) -> dict:
        return {
            "history_length": len(self.conversation_history),
            "total_tokens_used": self.total_tokens_used,
            "model": config.CLAUDE_MODEL,
        }


claude_brain = ClaudeBrain()

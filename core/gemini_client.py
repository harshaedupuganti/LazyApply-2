import time
import asyncio
from collections import deque
import google.generativeai as genai
import config

class GeminiClient:
    def __init__(self, api_keys: list[str]):
        self.api_keys = api_keys
        # We store keys to configure the google.generativeai client per call
        self.call_timestamps = [deque(maxlen=100) for _ in api_keys]
        self.daily_token_count = [0 for _ in api_keys]
        self.current_key_index = 0
        self.depleted_until = [0 for _ in api_keys]

    def _get_available_key(self) -> int:
        now = time.time()
        for _ in range(len(self.api_keys)):
            idx = self.current_key_index
            self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
            
            # Skip if this key is marked as exhausted (429)
            if now < self.depleted_until[idx]:
                continue
                
            # Count timestamps in its deque that are within the last 60 seconds
            recent_calls = sum(1 for ts in self.call_timestamps[idx] if now - ts < 60)
            if recent_calls < config.RPM_LIMIT:
                return idx
        return -1

    async def generate(self, prompt: str, system_prompt: str = None, max_tokens: int = 800, json_mode: bool = False) -> str | None:
        key_idx = self._get_available_key()
        if key_idx == -1:
            print("All keys rate limited, waiting 15 seconds")
            await asyncio.sleep(15)
            key_idx = self._get_available_key()
            if key_idx == -1:
                return None

        if json_mode:
            prompt += "\n\nRespond with ONLY valid JSON. No markdown code fences. No explanation. Just the raw JSON object."

        # Configure the selected key
        genai.configure(api_key=self.api_keys[key_idx])
        
        # Build the GenerativeModel with the selected key's configuration
        model = genai.GenerativeModel(model_name=config.PRIMARY_MODEL)
        
        generation_config = genai.types.GenerationConfig(
            max_output_tokens=max_tokens,
            temperature=0.3
        )

        contents = [system_prompt + "\n\n" + prompt] if system_prompt else [prompt]

        try:
            response = await model.generate_content_async(
                contents,
                generation_config=generation_config
            )
            
            # Record the timestamp in the key's deque
            self.call_timestamps[key_idx].append(time.time())
            
            # Extract text safely against SAFETY blocks
            try:
                text = response.text
            except ValueError:
                print("Warning: Response blocked due to SAFETY (ValueError on text extraction).")
                return None
                
            if response.candidates:
                candidate = response.candidates[0]
                if candidate.finish_reason.name == "SAFETY":
                    print("Warning: Response blocked due to SAFETY finish_reason.")
                    return None

            # Add estimated token count to daily_token_count (estimate: len(prompt)/4 + len(response)/4)
            est_tokens = len(prompt) // 4 + len(text) // 4
            self.daily_token_count[key_idx] += est_tokens
            
            # Strip any ```json or ``` fences from response text before returning
            text = text.strip()
            if text.startswith("```"):
                if text.startswith("```json"):
                    text = text[7:]
                else:
                    text = text[3:]
                text = text.strip()
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()
                
            return text

        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "ResourceExhausted" in e.__class__.__name__ or "ResourceExhausted" in error_msg:
                print(f"ResourceExhausted exception: Key {key_idx} depleted for 1 hour. Switching key, retry...")
                self.depleted_until[key_idx] = time.time() + 3600
                return await self.generate(prompt, system_prompt, max_tokens, json_mode)
            else:
                print(f"Exception in generate: {e}")
                return None

    def get_status(self) -> list[dict]:
        now = time.time()
        return [
            {
                "key_index": i,
                "rpm_used": sum(1 for ts in self.call_timestamps[i] if now - ts < 60),
                "rpm_limit": config.RPM_LIMIT,
                "daily_tokens": self.daily_token_count[i]
            }
            for i in range(len(self.api_keys))
        ]

gemini = None
import os
import re
from dotenv import load_dotenv

load_dotenv()


class Settings:
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    @staticmethod
    def _looks_like_supabase_url(url: str) -> bool:
        return bool(re.match(r"^https://[a-z0-9-]+\.supabase\.co/?$", url.strip(), re.IGNORECASE))

    @staticmethod
    def _looks_like_jwt(token: str) -> bool:
        token = token.strip()
        if "..." in token:
            return False
        parts = token.split(".")
        return len(parts) == 3 and all(len(p) >= 10 for p in parts)

    def validate(self):
        missing = []
        for field in ["TELEGRAM_BOT_TOKEN", "SUPABASE_URL", "SUPABASE_ANON_KEY", "GEMINI_API_KEY"]:
            if not getattr(self, field):
                missing.append(field)
        if missing:
            raise ValueError(f"Missing required env vars: {', '.join(missing)}")

        # Friendly validations to avoid confusing runtime errors.
        if not self.TELEGRAM_BOT_TOKEN.strip().count(":") == 1:
            raise ValueError("Invalid TELEGRAM_BOT_TOKEN format. Expected something like '<digits>:<token>'.")

        if not self._looks_like_supabase_url(self.SUPABASE_URL):
            raise ValueError(
                "Invalid SUPABASE_URL. Expected format like 'https://<project-ref>.supabase.co'."
            )

        if not self._looks_like_jwt(self.SUPABASE_ANON_KEY):
            raise ValueError(
                "Invalid SUPABASE_ANON_KEY. It must be the full 'anon public' JWT (three dot-separated parts) "
                "from Supabase Project Settings → API. Don't use '...' placeholder."
            )

        if "..." in self.GEMINI_API_KEY.strip():
            raise ValueError("Invalid GEMINI_API_KEY (contains '...'). Paste the full API key.")


settings = Settings()

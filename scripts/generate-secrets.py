#!/usr/bin/env python3
"""Print secrets for a private .env file; the LiveKit key ID is a public identifier."""
import secrets

for name in ("POSTGRES_PASSWORD", "REDIS_PASSWORD", "JWT_SECRET", "LIVEKIT_API_SECRET"):
    print(f"{name}={secrets.token_urlsafe(48)}")
print("LIVEKIT_API_KEY=horizon_voice")

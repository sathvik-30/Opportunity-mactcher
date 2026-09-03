"""
backend/app/rate_limit.py
─────────────────────────────────────────────────────────────────
Shared slowapi Limiter instance. One instance for the whole app —
imported by main.py (to register it + its exception handler) and by
any route module that wants to decorate an endpoint with @limiter.limit().

Keyed by client IP (get_remote_address). Currently applied to
/register and /login (routes/auth.py) to blunt credential-stuffing
and registration spam; add it to any other route that needs it the
same way.
─────────────────────────────────────────────────────────────────
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

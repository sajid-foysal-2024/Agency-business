"""A small rate limiter using Django's cache (no extra package).

@rate_limit("checkout", limit=10, window=60) allows 10 POSTs per minute per IP.
Note: the default local-memory cache is per process; use a shared cache
(Redis/Memcached) in production for limits across several workers.
"""
from functools import wraps

from django.core.cache import cache
from django.http import HttpResponse


def client_ip(request):
    return request.META.get("REMOTE_ADDR", "unknown")


def rate_limit(name, limit=10, window=60, methods=("POST",)):
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.method in methods:
                key = f"rl:{name}:{client_ip(request)}"
                added = cache.add(key, 1, timeout=window)
                count = 1 if added else cache.incr(key)
                if count > limit:
                    return HttpResponse("Too many requests. Please wait a minute and try again.",
                                        status=429, content_type="text/plain")
            return view(request, *args, **kwargs)
        return wrapped
    return decorator

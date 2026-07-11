from rest_framework.throttling import UserRateThrottle


class ChatRateThrottle(UserRateThrottle):
    """
    Stricter limit for endpoints that spend AI-provider money per request.

    Rate comes from DEFAULT_THROTTLE_RATES['chat'] (env THROTTLE_CHAT).
    Keys by user id when authenticated, by client IP otherwise — so the
    dev-open /api/chat/ is covered too. Note: @throttle_classes REPLACES
    the default anon/user throttles on the decorated view, so this scope
    is the only limit on chat endpoints.
    """

    scope = 'chat'

"""Request middleware for the selected current household member."""

from chores.current_member import get_single_household, load_current_member


class CurrentMemberMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.household = get_single_household()
        request.current_member = load_current_member(request, request.household)
        return self.get_response(request)

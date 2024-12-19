from django.utils import translation


class LanguageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Use 'lang' parameter in URL if provided, else fallback to user's language
        lang_code = request.GET.get('lang')

        if not lang_code and request.user.is_authenticated:
            lang_code = request.user.language  # User's profile language

        # Default to English if no language code found
        lang_code = lang_code if lang_code in ['en', 'ru', 'uz'] else 'en'
        translation.activate(lang_code)
        request.session['django_language'] = lang_code
        response = self.get_response(request)
        translation.deactivate()
        return response

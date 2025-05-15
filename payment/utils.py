# payme/utils.py
import base64
from django.conf import settings
from click_app.views import SUBSCRIPTION_COSTS

def generate_payme_docs_style_url(subscription_type: str, user_program_id: int) -> str:
    """
    Builds a Payme checkout URL in the doc style by Base64-encoding
    the "m=...;ac.id=...;a=...;c=..." string and appending it to the domain.

    Example result:
      https://checkout.paycom.uz/bT01ODdmNzJjNzJjYWMwZDE2MmM3MjJhZTI7YWMub3JkZXJfaWQ9MTk3O2E9NTAw
    """
    payme_id = settings.PAYME_ID
    cost_in_soum = SUBSCRIPTION_COSTS[subscription_type]
    callback_timeout = 600000
    cost_in_tiyin = cost_in_soum * 100
    return_url = "https://owntrainer.uz/payment-success"

    # Build the raw semicolon-separated params, e.g. "m=...;ac.id=...;a=...;c=..."
    raw_params = (
        f"m={payme_id};"
        f"ac.id={user_program_id};"
        f"ac.sub_type={subscription_type};"
        f"a={cost_in_tiyin};"
        f"ct={callback_timeout};"
        f"c={return_url}"
    )

    # Base64-encode the string
    encoded_params = base64.b64encode(raw_params.encode()).decode()

    # Append the encoded params to the domain
    payme_url = f"https://checkout.paycom.uz/{encoded_params}"
    return payme_url
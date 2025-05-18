import base64
from django.conf import settings
from click_app.views import SUBSCRIPTION_COSTS
import logging

logger = logging.getLogger(__name__)

def generate_payme_docs_style_url(subscription_type: str, user_program_id: int) -> str:
    """
    Builds a Payme checkout URL with account ID and amount.
    Example result: https://checkout.paycom.uz/bT02NzQ1ZWY1M2U2NGQ5MjliMGU0NjBkODE7YWMuaWQ9NzI7YWMuc3ViX3R5cGU9bW9udGg7YT0xMDAwMDA7Y3Q9NjAwMDAwO2M9aHR0cHM6Ly9vd250cmFpbmVyLnV6L3BheW1lbnQtc3VjY2Vzcw==
    """
    payme_id = settings.PAYME_ID
    cost_in_soum = SUBSCRIPTION_COSTS[subscription_type]
    callback_timeout = 600000
    cost_in_tiyin = cost_in_soum * 100  # Convert to tiyins
    return_url = "https://owntrainer.uz/payment-success"

    # Build the raw semicolon-separated params
    raw_params = (
        f"m={payme_id};"
        f"ac.id={user_program_id};"
        f"ac.sub_type={subscription_type};"
        f"a={str(cost_in_tiyin)};"  # Explicitly convert to string
        f"ct={callback_timeout};"
        f"c={return_url}"
    )

    # Log the raw params for debugging
    logger.info(f"Generated raw Payme params: {raw_params}")

    # Base64-encode the string
    encoded_params = base64.b64encode(raw_params.encode()).decode()

    # Append the encoded params to the domain
    payme_url = f"https://checkout.paycom.uz/{encoded_params}"
    logger.info(f"Final Payme URL: {payme_url}")
    return payme_url
import base64
from django.conf import settings
from click_app.views import SUBSCRIPTION_COSTS
import logging
import uuid

logger = logging.getLogger(__name__)

def generate_payme_docs_style_url(subscription_type: str, user_program_id: int) -> str:
    """
    Builds a Payme checkout URL with only the account ID.
    Example result: https://checkout.paycom.uz/bT01ODdmNzJjNzJjYWMwZDE2MmM3MjJhZTI7YWMuaWQ9NzI=
    """
    payme_id = settings.PAYME_ID
    return_url = "https://owntrainer.uz/payment-success"
    # Generate a unique transaction reference to track on the server side
    transaction_ref = str(uuid.uuid4())

    # Store the transaction reference with the subscription ID (e.g., in a session or database)
    # For now, log it; implement storage as needed
    logger.info(f"Generated transaction reference: {transaction_ref} for subscription ID: {user_program_id}")

    # Build the raw semicolon-separated params with only ac.id
    raw_params = f"m={payme_id};ac.id={user_program_id}"

    # Log the raw params for debugging
    logger.info(f"Generated raw Payme params: {raw_params}")

    # Base64-encode the string
    encoded_params = base64.b64encode(raw_params.encode()).decode()

    # Append the encoded params to the domain
    payme_url = f"https://checkout.paycom.uz/{encoded_params}"
    logger.info(f"Final Payme URL: {payme_url}")
    return payme_url
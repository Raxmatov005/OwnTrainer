import base64
import json
from django.conf import settings


def generate_payme_base64_url(amount_in_soum: int, user_program_id: int) -> str:
    """
    Generates a Payme checkout URL using the base64-encoded JSON payload method.

    :param amount_in_soum: The amount in so'm (will be converted to tiyin).
    :param user_program_id: The ID for the user program (passed as account[id]).
    :return: A full URL for redirecting the user to Payme.
    """
    # Build the payload: amount must be in tiyin (so'm * 100)
    payload = {
        "amount": amount_in_soum * 100,
        "account": {
            "id": user_program_id
        }
    }

    # Convert the payload to JSON and then base64-encode it.
    raw_json = json.dumps(payload)
    encoded_params = base64.b64encode(raw_json.encode()).decode()

    # Read the merchant ID from your settings (loaded from .env)
    merchant_id = settings.PAYME_ID  # Make sure your .env has PAYME_MERCHANT_ID defined.

    # Construct the final Payme URL using the CreateTransaction method.
    payme_url = (
        f"https://checkout.paycom.uz/{payme_id}"
        f"?method=CreateTransaction&params={encoded_params}"
    )

    return payme_url

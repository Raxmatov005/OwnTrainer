import base64
import logging

logger = logging.getLogger(__name__)


def generate_payme_docs_style_url(subscription_type, user_program_id):
    merchant_id = "6745ef53e64d929b0e460d81"  # Replace with your actual merchant ID
    amount = 1000  # In so'm, adjust as needed
    amount_in_tiyins = amount * 100  # Convert to tiyins
    callback_url = "https://owntrainer.uz/payment-success"
    timeout = 600000  # 10 minutes in milliseconds

    # Ensure user_program_id is a clean string
    clean_user_program_id = str(user_program_id)

    raw_params = (
        f"m={merchant_id};"
        f"ac.id={clean_user_program_id};"
        f"ac.sub_type={subscription_type};"
        f"a={amount_in_tiyins};"
        f"ct={timeout};"
        f"c={callback_url}"
    )

    logger.info(f"Generated raw Payme params: {raw_params}")
    encoded_params = base64.urlsafe_b64encode(raw_params.encode()).decode().rstrip("=")
    final_url = f"https://checkout.paycom.uz/{encoded_params}"
    logger.info(f"Final Payme URL: {final_url}")
    return final_url
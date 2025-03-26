from django.conf import settings
from click_app.views import SUBSCRIPTION_COSTS  # or wherever you define subscription costs

def generate_payme_docs_style_url(subscription_type: str, user_program_id: int) -> str:
    """
    Builds a Payme checkout URL in the doc style:
      https://checkout.paycom.uz/base64(m=PAYME_ID;ac.id=123;ac.sub_type=month;a=50000)

    :param subscription_type: e.g. "month", "quarter", "year"
    :param user_program_id: The ID you want to track (account field) in Payme
    :return: The final URL to open in a browser (GET).
    """
    payme_id = settings.PAYME_ID  # loaded from .env in settings.py
    cost_in_soum = SUBSCRIPTION_COSTS[subscription_type]
    cost_in_tiyin = cost_in_soum * 100

    # Decide how you want to pass data to Payme. For example:
    #  - "ac.id" could be your user_program_id
    #  - "ac.sub_type" could store the chosen subscription type
    #  - "a" is always the amount in tiyin
    #
    # Format: m=PAYME_ID;ac.id=USER_PROGRAM_ID;ac.sub_type=SUB_TYPE;a=AMOUNT_TIYIN
    # Then wrap in base64(...), per Payme doc style.

    params_str = (
        f"m={payme_id};"
        f"ac.id={user_program_id};"
        f"ac.sub_type={subscription_type};"
        f"a={cost_in_tiyin}"
    )

    # According to the docs, we do:
    #   https://checkout.paycom.uz/base64(m=...,ac.x=...,a=...)
    # It's not "real" base64; it's just how Payme names this approach.
    payme_url = f"https://checkout.paycom.uz/base64({params_str})"
    return payme_url

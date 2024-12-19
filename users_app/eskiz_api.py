import requests
import logging

logger = logging.getLogger(__name__)

class EskizAPI:
    BASE_URL = "https://notify.eskiz.uz"

    def __init__(self, email, password):
        self.email = email
        self.password = password
        self.token = None
        self.authenticate()

    def authenticate(self):
        """Eskiz API uchun autentifikatsiya va token olish"""
        try:
            response = requests.post(f"{self.BASE_URL}/api/auth/login", data={
                "email": self.email,
                "password": self.password
            })
            data = response.json()

            if response.status_code == 200 and data.get("message") == "token_generated":
                self.token = data["data"]["token"]
                logger.info("Eskiz API token muvaffaqiyatli olindi.")
            else:
                logger.error(f"Eskiz API bilan autentifikatsiya xatosi: {data}")
                self.token = None
        except Exception as e:
            logger.error(f"Eskiz API bilan ulanishda xatolik: {str(e)}")
            self.token = None

    def send_sms(self, phone, message):
        """SMS yuborish funksiyasi."""
        if not self.token:
            logger.error("Eskiz API token yo'q yoki yaroqsiz.")
            return {"error": "Token mavjud emas"}

        headers = {"Authorization": f"Bearer {self.token}"}
        data = {
            "mobile_phone": phone,
            "message": message,
            "from": "4546"  # Test rejimi uchun eskizdan tasdiqlangan 'from' qiymati
        }

        try:
            response = requests.post(f"{self.BASE_URL}/api/message/sms/send", headers=headers, data=data)
            if response.status_code == 200:
                logger.info(f"SMS yuborildi: {phone}")
                return response.json()
            else:
                logger.error(f"SMS yuborish xatosi: {response.json()}")
                return {"error": response.json()}
        except Exception as e:
            logger.error(f"Eskiz API orqali SMS yuborishda xatolik: {str(e)}")
            return {"error": str(e)}

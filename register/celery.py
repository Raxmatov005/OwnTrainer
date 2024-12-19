import os
from celery import Celery

# Django sozlamalarini aniqlash
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'register.settings')

app = Celery('register')

# Django settings'dan Celery konfiguratsiyasini yuklash
app.config_from_object('django.conf:settings', namespace='CELERY')

# Django app'larining tasks'larini avtomatik yuklash
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')

import os
import sys
import django

# Dynamically resolve root project directory
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(BASE_DIR)

os.environ['DJANGO_SETTINGS_MODULE'] = 'braincom_project.settings'
django.setup()
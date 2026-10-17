from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create the demo user (demo / demo) if it does not exist."

    def handle(self, *args, **options):
        user_model = get_user_model()
        if not user_model.objects.filter(username="demo").exists():
            user_model.objects.create_user("demo", "demo@example.com", "demo")
            self.stdout.write("Created user demo / demo")

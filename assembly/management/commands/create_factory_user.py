from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from assembly.models import UserProfile

ROLES = [value for value, _ in UserProfile.USER_TYPE_CHOICES]


class Command(BaseCommand):
    help = "Create a factory user with a role (SUPERVISOR, OPERATOR, TECHNICIAN, ENGINEER)."

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("password")
        parser.add_argument("user_type", choices=ROLES)

    def handle(self, username, password, user_type, **options):
        User = get_user_model()
        if User.objects.filter(username=username).exists():
            raise CommandError(f"User {username} already exists")
        user = User.objects.create_user(username=username, password=password)
        UserProfile.objects.create(user=user, user_type=user_type)
        self.stdout.write(self.style.SUCCESS(f"Created {username} ({user_type})"))

import factory
from allauth.account.models import EmailAddress

from workshop_manager.accounts.models import User


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"osoba{n}@example.com")
    first_name = "Anna"
    last_name = factory.Sequence(lambda n: f"Kowalska{n}")

    @factory.post_generation
    def verified_email(self, create, extracted, **kwargs):
        """Every factory user owns their address, as if they had signed in with a code once."""
        if create:
            EmailAddress.objects.create(user=self, email=self.email, verified=True, primary=True)


class AdminFactory(UserFactory):
    is_staff = True
    is_superuser = True

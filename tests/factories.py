from datetime import date, time

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


class WorkshopTypeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "workshops.WorkshopType"
        django_get_or_create = ("name",)

    name = "Ikonopisanie"
    default_levels = "Początkujący\nZaawansowani"


class LocationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "workshops.Location"

    name = "Pracownia"
    address = "ul. Przykładowa 1, Kraków"


class WorkshopFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "workshops.Workshop"

    type = factory.SubFactory(WorkshopTypeFactory)
    title = factory.Sequence(lambda n: f"Rekolekcje z ikoną {n}")
    location = factory.SubFactory(LocationFactory)


class SessionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "workshops.Session"

    workshop = factory.SubFactory(WorkshopFactory)
    date = date(2026, 11, 28)
    start_time = time(10, 0)
    end_time = time(16, 0)


class LevelFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "workshops.Level"

    workshop = factory.SubFactory(WorkshopFactory)
    name = "Początkujący"
    capacity = 12


class QuestionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "forms_builder.Question"

    workshop = factory.SubFactory(WorkshopFactory)
    label = factory.Sequence(lambda n: f"Pytanie {n}")
    order = factory.Sequence(lambda n: n)

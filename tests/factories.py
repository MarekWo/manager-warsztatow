from datetime import date, time

import factory
from allauth.account.models import EmailAddress
from django.utils import timezone

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


class ParticipantFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = "applications.Participant"

    email = factory.Sequence(lambda n: f"uczestnik{n}@example.com")
    first_name = "Jan"
    last_name = factory.Sequence(lambda n: f"Nowak{n}")


class ApplicationFactory(factory.django.DjangoModelFactory):
    """An application as the public form stores it; pass `level` (its workshop is used)."""

    class Meta:
        model = "applications.Application"

    level = factory.SubFactory(LevelFactory)
    workshop = factory.LazyAttribute(lambda o: o.level.workshop)
    participant = factory.SubFactory(ParticipantFactory)
    first_name = factory.LazyAttribute(lambda o: o.participant.first_name)
    last_name = factory.LazyAttribute(lambda o: o.participant.last_name)
    email = factory.LazyAttribute(lambda o: o.participant.email)
    privacy_consent_at = factory.LazyFunction(timezone.now)
    privacy_consent_version = "1"

from uuid import uuid4
from typing import Any, TYPE_CHECKING

from . import Settings

from django.contrib.auth.models import Group
from social_core.pipeline.social_auth import social_user
from social_core.backends.keycloak import KeycloakOAuth2
from social_django.models import UserSocialAuth, DjangoStorage
from social_django.strategy import DjangoStrategy
from nautobot.users.models import User


from social_django.models import UserSocialAuth, DjangoStorage
from social_django.strategy import DjangoStrategy
from nautobot.users.models import User

if TYPE_CHECKING:
    class Strategy(DjangoStrategy):
        storage = DjangoStorage

    class Keycloak(KeycloakOAuth2):
        strategy: Strategy


def get_username(
    details: dict,
    storage: DjangoStorage,
    user: User | None = None,
    *args,
    **kwargs,
):
    # custom reimplementation of social_core.pipeline.user.get_username
    # we want to be able to map usernames from keycload to existing users if they exist

    if not user:
        if details.get("username"):
            username = details["username"]
        else:
            username = uuid4().hex
    else:
        username = storage.user.get_username(user)
    return dict(username=username)


def map_groups(
    response: dict,
    user: User,
    *args,
    **kwargs,):
    s = Settings.from_cache()
    groups_from_keycloak = response.get("userGroup", [])

    # add user to groups, creating them if they don't exist
    for group_name in s.all_groups():
        group, _ = Group.objects.get_or_create(name=group_name)
        if group_name in groups_from_keycloak:
            user.groups.add(group) # pyright: ignore[reportAttributeAccessIssue]

    # set user-level permissions based on group membership
    print(groups_from_keycloak)
    if s.groups_active in groups_from_keycloak:
        print('f{user} is active')
        user.is_active = True # pyright: ignore[reportAttributeAccessIssue]
    if s.groups_staff in groups_from_keycloak:
        print('f{user} is staff')
        user.is_staff = True # pyright: ignore[reportAttributeAccessIssue]
    if s.groups_superuser in groups_from_keycloak:
        print('f{user} is superuser')
        user.is_superuser = True # pyright: ignore[reportAttributeAccessIssue]
    user.validated_save()
    return {}

from uoft_core.types import SecretStr

from django import forms
from nautobot.apps.secrets import SecretsProvider
from nautobot.extras.secrets.exceptions import SecretParametersError, SecretValueNotFoundError
from nautobot.core.forms import BootstrapMixin

from . import Settings


class EncryptedConfigSecretsProvider(SecretsProvider):
    """
    Encrypted Config SecretsProvider

    This SecretsProvider is used to retrieve secrets from the Nautobot configuration Settings class.
    """

    slug = "encrypted-config"  # pyright: ignore[reportIncompatibleMethodOverride, reportAssignmentType]
    name = "Encrypted Config"   # pyright: ignore[reportIncompatibleMethodOverride, reportAssignmentType]

    class ParametersForm(BootstrapMixin, forms.Form):  # pyright: ignore[reportIncompatibleMethodOverride]
        """
        User-friendly form for specifying the required parameters of this provider.
        """
        config_key = forms.CharField(
            required=True,
            help_text="dotted path to the key in the `uoft_nautobot.Settings` class"
        )

    @classmethod
    def get_value_for_secret(cls, secret, obj=None, **kwargs): # pyright: ignore[reportIncompatibleMethodOverride]
        """Retrieve the appropriate Settings class variable's value."""
        rendered_parameters = secret.rendered_parameters(obj=obj)
        if "config_key" not in rendered_parameters:
            raise SecretParametersError(secret, cls, 'The "config_key" parameter is mandatory!')
        key_path = rendered_parameters["config_key"].split(".")
        s = Settings.from_cache()
        try:
            for key in key_path:
                s = getattr(s, key)
        except KeyError:
            raise SecretValueNotFoundError(
                secret, cls, f'Undefined key "{rendered_parameters["config_key"]}"!'
            )
        if isinstance(s, SecretStr):
            s = s.get_secret_value()
        return s


secrets_providers = [EncryptedConfigSecretsProvider]

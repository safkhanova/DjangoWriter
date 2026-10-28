from django import forms
from django.core.cache import cache
from django.core.validators import MaxLengthValidator

from emailotp.services import client_ip

from .models import ContactMessage, ContactTopic


class HoneypotMixin(forms.Form):
    """Hidden field humans never fill; bots usually do."""

    website = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"}),
    )

    def is_spam(self) -> bool:
        return bool(self.cleaned_data.get("website"))


def rate_limited(request, scope: str, limit: int = 5, window: int = 600) -> bool:
    """True once this IP has done `scope` `limit` times within `window` seconds."""
    key = f"rl:{scope}:{client_ip(request)}"
    count = cache.get(key, 0)
    if count >= limit:
        return True
    cache.set(key, count + 1, window)
    return False


MESSAGE_MAX_LENGTH = 5000


def single_line(value: str) -> str:
    """Collapse whitespace/newlines: user text that ends up in an e-mail subject."""
    return " ".join(str(value).split())[:120]


class ContactForm(HoneypotMixin, forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ["name", "email", "phone", "topic", "message"]
        labels = {
            "name": "Adınız",
            "email": "E-poçtunuz",
            "phone": "Telefon (istəyə görə)",
            "topic": "Mövzu",
            "message": "Mesaj",
        }
        widgets = {"message": forms.Textarea(attrs={"rows": 5, "maxlength": MESSAGE_MAX_LENGTH})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["message"].max_length = MESSAGE_MAX_LENGTH
        self.fields["message"].validators.append(MaxLengthValidator(MESSAGE_MAX_LENGTH))
        self.fields["topic"].queryset = ContactTopic.objects.filter(is_visible=True)
        self.fields["topic"].empty_label = "Mövzu seçin"

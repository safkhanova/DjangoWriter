from django import forms

from content.models import Section
from core.forms import HoneypotMixin


class SectionChoiceMixin(forms.Form):
    sections = forms.ModelMultipleChoiceField(
        label="Hansı bölmələr maraqlıdır?",
        queryset=Section.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Heç birini seçməsəniz, bütün yeni yazılar haqqında xəbər alacaqsınız.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sections"].queryset = Section.objects.filter(is_visible=True)


class SubscribeForm(HoneypotMixin, SectionChoiceMixin):
    email = forms.EmailField(label="E-poçtunuz")
    name = forms.CharField(label="Adınız (istəyə görə)", max_length=120, required=False)

    field_order = ["email", "name", "sections"]

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()


class PreferencesForm(SectionChoiceMixin):
    pass

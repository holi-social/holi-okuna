from django.forms.models import BaseInlineFormSet


class UserProfileFormSet(BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        super(UserProfileFormSet, self).__init__(*args, **kwargs)
        for form in self.forms:
            form.fields["avatar"].required = False
            form.fields["cover"].required = False
            form.fields["badges"].required = False
            form.fields["url"].required = False
            form.fields["engagement_level"].required = False
            form.fields["about_me"].required = False

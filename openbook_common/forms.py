from django import forms

from openbook_common.models import AppVersion


class AppVersionForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(AppVersionForm, self).__init__(*args, **kwargs)
        self.fields["version"].help_text = "Displayed version of the app (x.y.z) (e.g. 1.1.1)"
        self.fields["build_number"].help_text = (
            "ios.buildNumber for iOS (e.g. 1.2.3), android.versionCode for Android (e.g. 12), "
            "values can be found inside the app.config.js expo configuration file"
        )

    class Meta:
        model = AppVersion
        exclude = ()

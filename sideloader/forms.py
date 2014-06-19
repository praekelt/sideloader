from django.contrib.auth.models import User
from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
import models

class BaseModelForm(forms.ModelForm):
    helper = FormHelper()
    helper.form_class = 'form-horizontal'
    helper.add_input(Submit('submit', 'Submit'))

class BaseForm(forms.Form):
    helper = FormHelper()
    helper.form_class = 'form-horizontal'
    helper.add_input(Submit('submit', 'Submit'))

class ReleaseForm(BaseModelForm):
    class Meta:
        model = models.ReleaseStream

class ReleasePushForm(BaseModelForm):
    tz = forms.CharField(widget=forms.HiddenInput())

    class Meta:
        model = models.Release
        exclude = ('release_date', 'flow', 'build', 'waiting')

class FlowForm(BaseModelForm):
    require_signoff = forms.BooleanField(
        label="Require sign-off",
        required=False)

    signoff_list = forms.CharField(
        widget=forms.Textarea,
        label="Sign-off list",
        required=False,
        help_text="List email addresses on a new line")

    auto_release = forms.BooleanField(
        help_text="Automatically deploy builds to this release stream", 
        required=False)

    quorum = forms.IntegerField(
        required=False,
        initial=0,
        help_text="Required number of sign-offs before release. 0 means <strong>all</strong> are required")

    class Meta:
        exclude = ('project',)
        model = models.ReleaseFlow

class ProjectForm(BaseModelForm):
    github_url = forms.CharField(label="Git checkout URL")
    allowed_users = forms.ModelMultipleChoiceField(
        queryset=User.objects.all().order_by('username'),
        required=False,
        widget=forms.widgets.CheckboxSelectMultiple
    )
    class Meta:
        model = models.Project
        exclude = ('idhash', 'created_by_user', 'release_stream')

    def clean(self):
        cleaned_data = super(ProjectForm, self).clean()

        uri = cleaned_data['github_url'].strip()
        if not (uri[-4:] == '.git'):
            raise forms.ValidationError("Not a valid Git URI")

        cleaned_data['github_url'] = uri

        return cleaned_data

class UserForm(BaseModelForm):
    password = forms.CharField(widget=forms.PasswordInput(), initial='')
    class Meta:
        model = User
        exclude = (
            'email', 'username', 'is_staff', 'is_active', 'is_superuser',
            'last_login', 'date_joined', 'groups', 'user_permissions'
        )

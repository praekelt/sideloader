from django.contrib.auth.models import User
from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
import models

class BaseModelForm(forms.ModelForm):
    helper = FormHelper()
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-lg-2'
    helper.field_class = 'col-lg-8'
    helper.add_input(Submit('submit', 'Submit'))

class BaseForm(forms.Form):
    helper = FormHelper()
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-lg-2'
    helper.field_class = 'col-lg-8'
    helper.add_input(Submit('submit', 'Submit'))

class ModuleForm(BaseModelForm):
    class Meta:
        model = models.ModuleManifest
        fields = ('name', 'key', 'structure',)

class ManifestForm(BaseModelForm):
    class Meta:
        model = models.ServerManifest
        exclude = ('release',)

class ReleaseForm(BaseModelForm):
    class Meta:
        model = models.ReleaseStream
        fields = ('name', 'push_command',)

class ReleasePushForm(BaseModelForm):
    tz = forms.CharField(widget=forms.HiddenInput())

    class Meta:
        model = models.Release
        exclude = ('release_date', 'flow', 'build', 'waiting',)


class WebhookForm(BaseModelForm):
    after = forms.ModelChoiceField(
        queryset=models.WebHook.objects.all().order_by('name'),
        required=False
    )

    content_type = forms.ChoiceField(
        label='Content type',
        choices=(
            ('application/json', 'application/json'),
        )
    )

    method = forms.ChoiceField(
        label='Request Method',
        choices=(
            ('POST', 'POST'),
            ('GET', 'GET'),
        )
    )

    class Meta:
        model = models.Release
        exclude = ('flow', 'last_response',)


class FlowForm(BaseModelForm):
    targets = forms.ModelMultipleChoiceField(
        queryset=models.Server.objects.all().order_by('name'),
        required=False
    )

    targets.help_text = ''

    require_signoff = forms.BooleanField(
        label="Require sign-off",
        required=False)

    signoff_list = forms.CharField(
        widget=forms.Textarea,
        label="Sign-off list",
        required=False,
        help_text="List email addresses on a new line")

    notify = forms.BooleanField(
        label="Send email notifications for releases",
        required=False)

    notify_list = forms.CharField(
        widget=forms.Textarea,
        label="Notification list",
        required=False,
        help_text="List email addresses on a new line")

    auto_release = forms.BooleanField(
        help_text="Automatically deploy new builds to this release workflow", 
        required=False)

    quorum = forms.IntegerField(
        required=False,
        initial=0,
        help_text="Required number of sign-offs before release. 0 means <strong>all</strong> are required")

    stream_mode = forms.ChoiceField(
        label='Release mode',
        widget=forms.RadioSelect,
        choices=((0, 'Stream',), (1, 'Server'), (2, 'Both')))

    puppet_run = forms.BooleanField(
        label='Run Puppet',
        help_text="Force a Puppet run after deployments",
        required=False,
        initial=True)

    service_restart = forms.BooleanField(
        label='Restart services',
        help_text="Restart all services after deployment",
        required=False,
        initial=False)

    service_pre_stop = forms.BooleanField(
        label='Stop/start services',
        help_text="Stop all services before deployment then start them afterwards",
        required=False,
        initial=True)

    class Meta:
        exclude = ('project',)
        model = models.ReleaseFlow
        fields = (
            'name', 'stream_mode', 'stream', 'targets',
            'service_restart', 'service_pre_stop', 'puppet_run',
            'require_signoff', 'signoff_list', 'quorum', 'notify', 
            'notify_list', 'auto_release'
        )

class ProjectForm(BaseModelForm):
    github_url = forms.CharField(label="Git checkout URL")

    deploy_type = forms.ChoiceField(
        label='Deploy type',
        widget=forms.RadioSelect,
        choices=(
            ('virtualenv', 'Virtualenv'),
            ('python', 'Python package'), 
            ('flat', 'Flat'),
            ('docker', 'Docker')
        )
    )

    package_manager = forms.ChoiceField(
        label='Package manager target',
        widget=forms.RadioSelect,
        choices=(('deb', 'Debian'),('rpm', 'Redhat'), ('docker', 'Docker Registry')))

    allowed_users = forms.ModelMultipleChoiceField(
        queryset=User.objects.all().order_by('username'),
        required=False
    )
    allowed_users.help_text = ''

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

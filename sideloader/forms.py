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

class ProjectForm(BaseModelForm):
    github_url = forms.CharField(label="Git checkout URL")
    class Meta:
        model = models.Project
        exclude = ('idhash', 'created_by_user',)

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

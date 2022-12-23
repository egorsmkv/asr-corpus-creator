from os.path import exists

from django import forms
from django.forms import ValidationError


class SendLinkForm(forms.Form):
    link = forms.CharField(label='Link')
    collection_key = forms.CharField(label='Collection Key')
    lang = forms.CharField(label='Lang', max_length=2)

    def clean_link(self):
        link = self.cleaned_data['link']

        if not link.startswith('https://youtube.com') and not link.startswith('https://www.youtube.com'):
            raise ValidationError('The link must start with https://youtube.com or https://www.youtube.com')

        return link


class SendYouTubeChannelForm(forms.Form):
    channel_url = forms.CharField(label='Channel URL')
    collection_key = forms.CharField(label='Collection Key')
    lang = forms.CharField(label='Lang', max_length=2)

    def clean_channel_url(self):
        link = self.cleaned_data['channel_url']

        if not link.startswith('https://youtube.com') and not link.startswith('https://www.youtube.com'):
            raise ValidationError('The link must start with https://youtube.com or https://www.youtube.com')

        return link


class SendAudioLinkForm(forms.Form):
    link = forms.CharField(label='Link')
    collection_key = forms.CharField(label='Collection Key')
    lang = forms.CharField(label='Lang', max_length=2)

    def clean_link(self):
        link = self.cleaned_data['link']

        if not link.startswith('http://') and not link.startswith('https://'):
            raise ValidationError('The link must start with http:// or https:/')

        return link


class SendVideoLinkForm(forms.Form):
    link = forms.CharField(label='Link')
    collection_key = forms.CharField(label='Collection Key')
    lang = forms.CharField(label='Lang', max_length=2)

    def clean_link(self):
        link = self.cleaned_data['link']

        if not link.startswith('http://') and not link.startswith('https://'):
            raise ValidationError('The link must start with http:// or https:/')

        return link


class SendLocalFolderForm(forms.Form):
    path = forms.CharField(label='Path')
    collection_key = forms.CharField(label='Collection Key')
    lang = forms.CharField(label='Lang', max_length=2)

    def clean_path(self):
        path = self.cleaned_data['path']

        if not exists(path):
            raise ValidationError('The provided folder does not exist')

        return path

from django.db import models
from django.conf import settings

from .utils import sizeof_fmt


class SearchHistory(models.Model):
    collection_key = models.CharField(max_length=50, default='-')

    def __str__(self):
        return self.collection_key


class YoutubeLink(models.Model):
    link = models.CharField(max_length=500)
    collection_key = models.CharField(max_length=50, default='-')
    is_exported = models.BooleanField(default=False)
    lang = models.CharField(max_length=2, default='-')

    def __str__(self):
        return self.link


class YoutubeChannelLink(models.Model):
    channel_url = models.CharField(max_length=500)
    collection_key = models.CharField(max_length=50, default='-')
    is_exported = models.BooleanField(default=False)
    lang = models.CharField(max_length=2, default='-')

    def __str__(self):
        return self.channel_url


class LocalFolder(models.Model):
    path = models.CharField(max_length=500)
    collection_key = models.CharField(max_length=50, default='-')
    is_exported = models.BooleanField(default=False)
    lang = models.CharField(max_length=2, default='-')

    def __str__(self):
        return self.link


class AudioLink(models.Model):
    link = models.CharField(max_length=500)
    collection_key = models.CharField(max_length=50, default='-')
    is_exported = models.BooleanField(default=False)
    lang = models.CharField(max_length=2, default='-')

    def __str__(self):
        return self.link


class AudioFile(models.Model):
    collection_key = models.CharField(max_length=50)
    link = models.CharField(max_length=500)
    filename = models.CharField(max_length=500)
    length = models.FloatField(default=0)
    lang = models.CharField(max_length=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.filename


class VideoFile(models.Model):
    link = models.CharField(max_length=500)
    collection_key = models.CharField(max_length=50, default='-')
    is_exported = models.BooleanField(default=False)
    lang = models.CharField(max_length=2, default='-')

    def __str__(self):
        return self.link


class AudioChunk(models.Model):
    filename = models.CharField(max_length=500)
    length = models.FloatField(default=0)
    audio = models.ForeignKey(AudioFile, on_delete=models.CASCADE)

    def __str__(self):
        return self.filename


class Utterance(models.Model):
    collection_key = models.CharField(max_length=50)
    label = models.CharField(max_length=500)
    filename = models.CharField(max_length=500, unique=True)
    length = models.FloatField(default=0)
    lang = models.CharField(max_length=2)
    snr = models.FloatField(default=0)
    loudness = models.FloatField(default=0)
    srmr_ratio = models.FloatField(default=0)
    filesize = models.FloatField(default=0)
    label_lang = models.CharField(max_length=2, default='--')
    audio_lang = models.CharField(max_length=2, default='--')
    audio_type = models.CharField(max_length=50, default='--')

    created_at = models.DateTimeField(auto_now_add=True)
    
    audio = models.ForeignKey(AudioFile, on_delete=models.CASCADE)

    def __str__(self):
        return self.label

    def get_filename_path(self):
        return self.filename.replace(settings.MEDIA_ROOT, '').lstrip('/')

    def get_snr_formatted(self):
        return round(self.snr, 4)

    def get_loudness_formatted(self):
        return round(self.loudness, 4)

    def get_srmr_formatted(self):
        return round(self.srmr_ratio, 4)

    def get_duration_formatted(self):
        return round(self.length, 4)

    def get_filesize_formatted(self):
        return sizeof_fmt(self.filesize)


class Proxy(models.Model):
    addr = models.CharField(max_length=500)

    def __str__(self):
        return self.addr



def get_proxies():
    items = [['-', '-']]

    for proxy in Proxy.objects.all():
        items.append([proxy.addr, proxy.addr])

    return items


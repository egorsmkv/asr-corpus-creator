from django.contrib import admin

from .models import *


class UtteranceAdmin(admin.ModelAdmin):
    list_display = ['id', 'collection_key', 'label', 'length', 'snr']
    list_filter = ['collection_key', 'lang']


class YoutubeChannelLinkAdmin(admin.ModelAdmin):
    list_filter = ['is_exported', 'lang', 'collection_key']


class YoutubeLinkAdmin(admin.ModelAdmin):
    list_filter = ['is_exported', 'lang', 'collection_key']


class VideoFileAdmin(admin.ModelAdmin):
    list_filter = ['is_exported', 'lang', 'collection_key']


class AudioLinkAdmin(admin.ModelAdmin):
    list_filter = ['is_exported', 'lang', 'collection_key']


class AudioFileAdmin(admin.ModelAdmin):
    list_filter = ['lang', 'collection_key']


class AudioChunkAdmin(admin.ModelAdmin):
    list_display = ['id', 'filename', 'length']


admin.site.register(YoutubeLink, YoutubeLinkAdmin)
admin.site.register(YoutubeChannelLink, YoutubeChannelLinkAdmin)
admin.site.register(VideoFile, VideoFileAdmin)
admin.site.register(AudioFile, AudioFileAdmin)
admin.site.register(AudioChunk, AudioChunkAdmin)
admin.site.register(Utterance, UtteranceAdmin)
admin.site.register(AudioLink, AudioLinkAdmin)
admin.site.register(SearchHistory)
admin.site.register(Proxy)

from django.contrib import admin

from .models import *


class UtteranceAdmin(admin.ModelAdmin):
    list_display = ['id', 'collection_key', 'label', 'length', 'snr']
    list_filter = ['collection_key']


class YoutubeChannelLinkAdmin(admin.ModelAdmin):
    list_filter = ['is_exported']


class AudioChunkAdmin(admin.ModelAdmin):
    list_display = ['id', 'filename', 'length']


admin.site.register(YoutubeLink)
admin.site.register(YoutubeChannelLink, YoutubeChannelLinkAdmin)
admin.site.register(AudioFile)
admin.site.register(VideoFile)
admin.site.register(AudioChunk, AudioChunkAdmin)
admin.site.register(Utterance, UtteranceAdmin)
admin.site.register(AudioLink)
admin.site.register(SearchHistory)
admin.site.register(Proxy)

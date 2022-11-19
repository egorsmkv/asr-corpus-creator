from django.contrib import admin

from .models import *

class UtteranceAdmin(admin.ModelAdmin):
    list_display = ['id', 'collection_key', 'label', 'length', 'snr']
    list_filter = ['collection_key']
   

admin.site.register(YoutubeLink)
admin.site.register(AudioFile)
admin.site.register(VideoFile)
admin.site.register(AudioChunk)
admin.site.register(Utterance, UtteranceAdmin)
admin.site.register(AudioLink)
admin.site.register(SearchHistory)

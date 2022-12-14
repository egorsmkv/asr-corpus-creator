from django.urls import path

from .views import (
    SendLinkView, SendYouTubeChannelView, SendAudioLinkView, 
    SendVideoLinkView, SearchUtterancesView, SendLocalFolderView,
    SendYouTubeChannelsView, ProxiesView,
    send_video_api,
)

app_name = 'corpus'

urlpatterns = [
    path('send-link/', SendLinkView.as_view(), name='send_link'),
    path('send-youtube-channel/', SendYouTubeChannelView.as_view(), name='send_youtube_channel'),
    path('send-youtube-channels/', SendYouTubeChannelsView.as_view(), name='send_youtube_channels'),
    path('send-video-link/', SendVideoLinkView.as_view(), name='send_video_link'),
    path('send-audio-link/', SendAudioLinkView.as_view(), name='send_audio_link'),
    path('send-local-folder/', SendLocalFolderView.as_view(), name='send_local_folder'),
    path('search-utterances/', SearchUtterancesView.as_view(), name='search_utterances'),
    path('proxies/', ProxiesView.as_view(), name='proxies'),
    path('api/send-video', send_video_api, name='api_send_video')
]

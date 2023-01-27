from django.views.generic import FormView, TemplateView
from django.shortcuts import redirect, render
from django.contrib import messages
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Sum
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse

from .tasks import download_youtube_audio, download_audio, download_video, process_local_folder, download_youtube_channel
from .forms import SendLinkForm, SendYouTubeChannelForm, SendYouTubeChannelsForm, SendAudioLinkForm, SendVideoLinkForm, SendLocalFolderForm, CreateProxiesForm
from .models import YoutubeLink, Utterance, AudioLink, VideoFile, SearchHistory, LocalFolder, YoutubeChannelLink, Proxy
from .utils import sizeof_fmt


class SendLinkView(LoginRequiredMixin, FormView):
    template_name = 'corpus/send_link.html'

    @staticmethod
    def get_form_class(**kwargs):
        return SendLinkForm

    def form_valid(self, form):
        link = form.cleaned_data['link']
        collection_key = form.cleaned_data['collection_key']
        lang = form.cleaned_data['lang']
        proxy = form.cleaned_data['proxy']

        yt = YoutubeLink()
        yt.link = link
        yt.collection_key = collection_key
        yt.lang = lang
        yt.save()

        download_youtube_audio.delay(link, yt.id, proxy)

        messages.success(self.request, 'Link has been sent')

        return redirect('/corpus/send-link/')


class SendYouTubeChannelView(LoginRequiredMixin, FormView):
    template_name = 'corpus/send_youtube_channel.html'

    @staticmethod
    def get_form_class(**kwargs):
        return SendYouTubeChannelForm

    def form_valid(self, form):
        channel_url = form.cleaned_data['channel_url']
        collection_key = form.cleaned_data['collection_key']
        lang = form.cleaned_data['lang']
        proxy = form.cleaned_data['proxy']

        ycl = YoutubeChannelLink()
        ycl.channel_url = channel_url
        ycl.collection_key = collection_key
        ycl.lang = lang
        ycl.save()

        download_youtube_channel.delay(ycl.id, proxy)

        messages.success(self.request, 'Link to the channel has been sent')

        return redirect('/corpus/send-youtube-channel/')


class SendYouTubeChannelsView(LoginRequiredMixin, FormView):
    template_name = 'corpus/send_youtube_channels.html'

    @staticmethod
    def get_form_class(**kwargs):
        return SendYouTubeChannelsForm

    def form_valid(self, form):
        channel_urls = form.cleaned_data['channel_urls']
        collection_key = form.cleaned_data['collection_key']
        lang = form.cleaned_data['lang']
        proxy = form.cleaned_data['proxy']

        channels = channel_urls.split('\n')

        for channel_url in channels:
            ycl = YoutubeChannelLink()
            ycl.channel_url = channel_url
            ycl.collection_key = collection_key
            ycl.lang = lang
            ycl.save()

            download_youtube_channel.delay(ycl.id, proxy)

        messages.success(self.request, 'Links to the channels has been sent')

        return redirect('/corpus/send-youtube-channels/')


class SendLocalFolderView(LoginRequiredMixin, FormView):
    template_name = 'corpus/send_local_folder.html'

    @staticmethod
    def get_form_class(**kwargs):
        return SendLocalFolderForm

    def form_valid(self, form):
        path = form.cleaned_data['path']
        collection_key = form.cleaned_data['collection_key']
        lang = form.cleaned_data['lang']

        lf = LocalFolder()
        lf.path = path
        lf.collection_key = collection_key
        lf.lang = lang
        lf.save()

        process_local_folder.delay(lf.id)

        messages.success(self.request, 'Folder has been sent')

        return redirect('/corpus/send-local-folder/')


class SendAudioLinkView(LoginRequiredMixin, FormView):
    template_name = 'corpus/send_audio_link.html'

    @staticmethod
    def get_form_class(**kwargs):
        return SendAudioLinkForm

    def form_valid(self, form):
        link = form.cleaned_data['link']
        collection_key = form.cleaned_data['collection_key']
        lang = form.cleaned_data['lang']

        yt = AudioLink()
        yt.link = link
        yt.collection_key = collection_key
        yt.lang = lang
        yt.save()

        download_audio.delay(link, yt.id)

        messages.success(self.request, 'Link has been sent')

        return redirect('/corpus/send-audio-link/')


class SendVideoLinkView(LoginRequiredMixin, FormView):
    template_name = 'corpus/send_video_link.html'

    @staticmethod
    def get_form_class(**kwargs):
        return SendVideoLinkForm

    def form_valid(self, form):
        link = form.cleaned_data['link']
        collection_key = form.cleaned_data['collection_key']
        lang = form.cleaned_data['lang']

        vf = VideoFile()
        vf.link = link
        vf.collection_key = collection_key
        vf.lang = lang
        vf.save()

        download_video.delay(link, vf.id)

        messages.success(self.request, 'Link has been sent')

        return redirect('/corpus/send-video-link/')


def send_video_api(request):
    link = request.GET.get('link')
    collection_key = request.GET.get('collection_key')
    lang = request.GET.get('lang')

    if not link:
        return JsonResponse({'success': False})

    if not collection_key:
        return JsonResponse({'success': False})

    if not lang:
        return JsonResponse({'success': False})

    vf = VideoFile()
    vf.link = link
    vf.collection_key = collection_key
    vf.lang = lang
    vf.save()

    download_video.delay(link, vf.id)

    return JsonResponse({'success': True})


class SearchUtterancesView(LoginRequiredMixin, TemplateView):
    template_name = 'corpus/search_utterances.html'

    def get(self, request):
        collection_key = request.GET.get('collection_key')
        audio_type = request.GET.get('audio_type')
        sort = request.GET.get('sort')

        search_history_count_all = SearchHistory.objects.filter(collection_key=collection_key).count()
        if search_history_count_all == 0:
            sh = SearchHistory()
            sh.collection_key = collection_key
            sh.save()
        
        distinct_audio_types = Utterance.objects.filter(collection_key=collection_key).values('audio_type').distinct()

        if audio_type:
            count_all = Utterance.objects.filter(collection_key=collection_key, audio_type=audio_type).count()
            summary = Utterance.objects.filter(collection_key=collection_key, audio_type=audio_type).aggregate(Sum('length'))
        else:
            count_all = Utterance.objects.filter(collection_key=collection_key).count()
            summary = Utterance.objects.filter(collection_key=collection_key).aggregate(Sum('length'))

        if summary['length__sum'] is None:
            messages.warning(self.request, 'No records yet with this collection key')

            return redirect('/')

        summary_time = round(float(summary['length__sum']), 4)
        summary_time_min = round(summary_time/60, 4)
        summary_time_hours = round(summary_time_min/60, 4)

        summary_filesize = 0

        if audio_type:
            summary = Utterance.objects.filter(collection_key=collection_key, audio_type=audio_type).aggregate(Sum('filesize'))
        else:
            summary = Utterance.objects.filter(collection_key=collection_key).aggregate(Sum('filesize'))
        if summary['filesize__sum'] is not None:
            summary_filesize = sizeof_fmt(float(summary['filesize__sum']))

        if sort == 'snr':
            if audio_type:
                rows = Utterance.objects.filter(collection_key=collection_key, audio_type=audio_type).order_by('-snr').all()
            else:
                rows = Utterance.objects.filter(collection_key=collection_key).order_by('-snr').all()
        elif sort == 'length':
            if audio_type:
                rows = Utterance.objects.filter(collection_key=collection_key, audio_type=audio_type).order_by('-length').all()
            else:
                rows = Utterance.objects.filter(collection_key=collection_key).order_by('-length').all()
        else:
            if audio_type:
                rows = Utterance.objects.filter(collection_key=collection_key, audio_type=audio_type).order_by('-id').all()
            else:
                rows = Utterance.objects.filter(collection_key=collection_key).order_by('-id').all()

        paginator = Paginator(rows, 10)

        page = request.GET.get('page')
        try:
            utterances = paginator.page(page)
        except PageNotAnInteger:
            utterances  = paginator.page(1)
        except EmptyPage:
            utterances  = paginator.page(paginator.num_pages)

        ctx = {
            'distinct_audio_types': distinct_audio_types,
            'count_all': count_all,
            'collection_key': collection_key, 
            'audio_type': audio_type,
            'utterances': utterances, 
            'summary_time': summary_time, 
            'summary_filesize': summary_filesize, 
            'summary_time_min': summary_time_min, 
            'summary_time_hours': summary_time_hours,
        }

        return render(request, self.template_name, ctx)



class ProxiesView(LoginRequiredMixin, FormView):
    template_name = 'corpus/proxies.html'

    @staticmethod
    def get_form_class(**kwargs):
        return CreateProxiesForm
    
    def get(self, request):
        proxies = Proxy.objects.all()

        return render(request, self.template_name, {'proxies': proxies, 'form': self.get_form()})

    def form_valid(self, form):
        proxies = form.cleaned_data['proxies'].split('\n')

        for proxy in proxies:
            p = Proxy()
            p.addr = proxy
            p.save()

        messages.success(self.request, 'Proxies have been added')

        return redirect('/corpus/proxies/')

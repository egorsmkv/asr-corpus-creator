import psutil

from django.views.generic import TemplateView
from django.shortcuts import render

from corpus.models import SearchHistory


class IndexPageView(TemplateView):
    template_name = 'main/index.html'

    def get(self, request):
        sysload = psutil.cpu_percent()
        avgload = psutil.getloadavg()

        history_queries = SearchHistory.objects.order_by('-id').all()[:5]

        return render(request, self.template_name, {'history_queries': history_queries, 'sysload': sysload, 'avgload': avgload})



class ChangeLanguageView(TemplateView):
    template_name = 'main/change_language.html'

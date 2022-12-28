def inject_hostname(request):
    return {
        'HOSTNAME': request.get_host(),
    }

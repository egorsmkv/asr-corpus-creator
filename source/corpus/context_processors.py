def inject_hostname(request):
    host = request.get_host()

    if ':' in host:
        parts = host.split(':')
        host = parts[0]

    return {
        'HOSTNAME': host,
    }

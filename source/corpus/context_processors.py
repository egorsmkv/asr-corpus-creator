def inject_hostname(request):
    host = request.get_host()

    if ':' in host:
        parts = host.split(':')
        host = parts[0]

    schema = 'http'
    
    if request.is_secure():
        schema = 'https'

    return {
        'HOSTNAME': f'{schema}://{host}',
    }

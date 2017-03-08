from django import http


class BlockedIpMiddleware(object):
    def process_request(self, request):
        if request.META['PATH_INFO'] == '/dts/login/' and request.META.get('HTTP_HOST') == 'dts.100credit.com':
            return http.HttpResponseForbidden('<h1>Forbidden</h1>')

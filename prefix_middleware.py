class PrefixMiddleware:
    """
    Middleware for stripping a URL prefix when the app is behind a reverse proxy.
    This allows the app to run without prefixes locally, but work correctly
    when deployed behind a reverse proxy that adds a prefix.
    """
    def __init__(self, app, prefix='/'):
        self.app = app
        self.prefix = prefix
        if not self.prefix.endswith('/'):
            self.prefix += '/'

    def __call__(self, environ, start_response):
        # If request path starts with our prefix, strip prefix
        path_info = environ.get('PATH_INFO', '')
        if path_info.startswith(self.prefix):
            environ['PATH_INFO'] = path_info[len(self.prefix)-1:] or '/'
            # Also adjust SCRIPT_NAME
            environ['SCRIPT_NAME'] = environ.get('SCRIPT_NAME', '') + self.prefix[:-1]
        
        return self.app(environ, start_response)

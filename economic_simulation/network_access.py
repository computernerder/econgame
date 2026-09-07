"""Shared LAN sign-in without exposing the server password to game pages."""
from collections import OrderedDict, deque
import secrets
import time
from urllib.parse import parse_qs

from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse


class NetworkAccess:
    def __init__(self, origin, access_key, session_token):
        self.origin = origin
        self.host = origin.split('://', 1)[1]
        self.access_key = access_key
        self.session_token = session_token
        self.secure = origin.startswith('https://')
        self.failures = OrderedDict()

    def same_origin(self, request):
        return request.headers.get('origin') == self.origin

    def authenticated(self, request):
        return secrets.compare_digest(request.cookies.get('game_session', '').encode(), self.session_token.encode())

    async def form(self, request):
        if request.headers.get('content-type', '').split(';')[0] != 'application/x-www-form-urlencoded':
            return {}
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 4096:
                return {}
        try:
            return parse_qs(body.decode('utf-8'), max_num_fields=4)
        except (UnicodeError, ValueError):
            return {}

    async def check(self, request, env):
        """Return an early response, or None to enter an authenticated game route."""
        if request.headers.get('host', '').lower() != self.host:
            return JSONResponse({'detail': 'Use the configured game address.'}, status_code=403)
        path = request.url.path
        if path == '/healthz' and request.method in ('GET', 'HEAD'):
            return JSONResponse({'status': 'ok'})
        if path == '/static/login.css' and request.method in ('GET', 'HEAD'):
            return None
        if path == '/login':
            if request.method == 'GET':
                if self.authenticated(request):
                    return RedirectResponse('/', status_code=303)
                return HTMLResponse(env.get_template('login.html').render(error=''))
            if request.method != 'POST' or not self.same_origin(request):
                return JSONResponse({'detail': 'Sign in from the game address.'}, status_code=403)
            client = request.client.host if request.client else 'unknown'
            now = time.monotonic()
            attempts = self.failures.setdefault(client, deque())
            self.failures.move_to_end(client)
            while len(self.failures) > 512:
                self.failures.popitem(last=False)
            while attempts and attempts[0] <= now - 60:
                attempts.popleft()
            if len(attempts) >= 10:
                return HTMLResponse(env.get_template('login.html').render(error='Too many attempts. Try again in a minute.'),
                                    status_code=429, headers={'Retry-After': '60'})
            form = await self.form(request)
            supplied = form.get('access_key', [''])[0]
            if not secrets.compare_digest(supplied.encode(), self.access_key.encode()):
                attempts.append(now)
                return HTMLResponse(env.get_template('login.html').render(error='That access key was not recognized.'), status_code=401)
            self.failures.pop(client, None)
            response = RedirectResponse('/', status_code=303)
            response.set_cookie('game_session', self.session_token, httponly=True, samesite='strict',
                                secure=self.secure, max_age=43200)
            return response
        if path == '/logout':
            if request.method != 'POST' or not self.same_origin(request) or not self.authenticated(request):
                return JSONResponse({'detail': 'Sign out from the game window.'}, status_code=403)
            form = await self.form(request)
            if not secrets.compare_digest(form.get('csrf', [''])[0].encode(), self.session_token.encode()):
                return JSONResponse({'detail': 'Refresh the game before signing out.'}, status_code=403)
            response = RedirectResponse('/login', status_code=303)
            response.delete_cookie('game_session', httponly=True, samesite='strict', secure=self.secure)
            return response
        if not self.authenticated(request):
            if request.method in ('GET', 'HEAD') and not path.startswith('/api/'):
                return RedirectResponse('/login', status_code=303)
            return JSONResponse({'detail': 'Sign in to Empire Manager.', 'login_url': '/login'}, status_code=401)
        if request.method not in ('GET', 'HEAD'):
            if not self.same_origin(request) or not secrets.compare_digest(request.headers.get('x-game-token', '').encode(), self.session_token.encode()):
                return JSONResponse({'detail': 'This action did not come from the game window.'}, status_code=403)
        return None

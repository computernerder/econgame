"""Headless, single-writer server for Docker and LAN deployment."""
from contextlib import asynccontextmanager
from dataclasses import dataclass
import argparse
import os
from pathlib import Path
import re
import secrets
from urllib.parse import urlsplit


def public_origin(value):
    try:
        parsed = urlsplit(value.strip())
        port = parsed.port
    except ValueError as exc:
        raise ValueError('EMPIRE_PUBLIC_URL must be the full http(s) game address.') from exc
    if (parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or parsed.path not in ('', '/') or parsed.query or parsed.fragment
            or not re.fullmatch(r'[a-zA-Z0-9.\-:\[\]]+', parsed.netloc)):
        raise ValueError('EMPIRE_PUBLIC_URL must be an http(s) origin without a path, credentials or query.')
    host = parsed.hostname.lower()
    if ':' in host:
        host = '[' + host + ']'
    if port and port != (443 if parsed.scheme == 'https' else 80):
        host += ':' + str(port)
    return parsed.scheme + '://' + host


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    origin: str
    port: int = 8000

    @classmethod
    def from_env(cls):
        origin = public_origin(os.environ.get('EMPIRE_PUBLIC_URL', ''))
        port = int(os.environ.get('EMPIRE_PORT', '8000'))
        if not 1 <= port <= 65535:
            raise ValueError('EMPIRE_PORT must be between 1 and 65535.')
        return cls(Path(os.environ.get('EMPIRE_DATA_DIR', '/data')).resolve(), origin, port)


def access_key(data_dir):
    explicit = os.environ.get('EMPIRE_ACCESS_KEY')
    key_file = os.environ.get('EMPIRE_ACCESS_KEY_FILE')
    if explicit is not None and key_file:
        raise ValueError('Set only EMPIRE_ACCESS_KEY or EMPIRE_ACCESS_KEY_FILE.')
    if explicit is not None:
        key = explicit
    elif key_file:
        key = Path(key_file).read_text(encoding='utf-8').strip()
    else:
        path = data_dir / 'access-key'
        if not path.exists():
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w', encoding='utf-8') as output:
                output.write(secrets.token_urlsafe(32) + '\n')
        if path.is_symlink():
            raise ValueError('The generated access-key file must be inside the data directory.')
        key = path.read_text(encoding='utf-8').strip()
    if not 16 <= len(key) <= 512:
        raise ValueError('Use an access key of 16 to 512 characters.')
    return key


def active_save(save_dir):
    pointer = save_dir / 'last-campaign.txt'
    name = pointer.read_text(encoding='utf-8').strip() if pointer.exists() else 'campaign.sqlite3'
    if Path(name).name != name or '/' in name or '\\' in name or not name.endswith('.sqlite3'):
        name = 'campaign.sqlite3'
    path = save_dir / name
    if path.is_symlink():
        raise ValueError('Campaign files must be inside the save directory.')
    if not path.exists():
        path = save_dir / 'campaign.sqlite3'
    if path.is_symlink():
        raise ValueError('Campaign files must be inside the save directory.')
    return path


def create_server(settings):
    from .application import Game
    from .desktop import SaveLock
    from .network_access import NetworkAccess
    from .web import create_app

    settings.data_dir.mkdir(parents=True, exist_ok=True)
    library_lock = SaveLock(settings.data_dir / '.server.lock')
    campaign_lock = None
    game = None
    try:
        key = access_key(settings.data_dir)
        save_dir = settings.data_dir / 'saves'
        save_dir.mkdir(exist_ok=True)
        path = active_save(save_dir)
        campaign_lock = SaveLock(path.with_suffix('.lock'))
        game = Game(path, save_lock=campaign_lock)
        token = secrets.token_urlsafe(32)

        @asynccontextmanager
        async def lifespan(app):
            try:
                yield
            finally:
                import anyio
                def shutdown():
                    game.stop()
                    if game.worker and game.worker.is_alive():
                        game.worker.join()
                    game.close()
                    library_lock.close()
                await anyio.to_thread.run_sync(shutdown)

        app = create_app(game, token, settings.origin.split('://', 1)[1],
                         network_access=NetworkAccess(settings.origin, key, token), lifespan=lifespan)
        app.state.game = game
        return app
    except BaseException:
        if game:
            game.close()
        if campaign_lock:
            campaign_lock.close()
        library_lock.close()
        raise


def main():
    parser = argparse.ArgumentParser(description='Empire Manager network server')
    parser.add_argument('--healthcheck', action='store_true')
    args = parser.parse_args()
    settings = Settings.from_env()
    if args.healthcheck:
        from urllib.request import Request, urlopen
        request = Request(f'http://127.0.0.1:{settings.port}/healthz', headers={'Host': settings.origin.split('://', 1)[1]})
        with urlopen(request, timeout=3) as response:
            if response.status != 200:
                raise SystemExit(1)
        return
    import uvicorn
    app = create_server(settings)
    print('Empire Manager server: ' + settings.origin, flush=True)
    print('Persistent campaigns: ' + str(settings.data_dir / 'saves'), flush=True)
    if not os.environ.get('EMPIRE_ACCESS_KEY') and not os.environ.get('EMPIRE_ACCESS_KEY_FILE'):
        print('Sign-in key is stored in ' + str(settings.data_dir / 'access-key'), flush=True)
    uvicorn.run(app, host='0.0.0.0', port=settings.port, workers=1, access_log=False,
                proxy_headers=False, server_header=False, timeout_graceful_shutdown=45)


if __name__ == '__main__':
    main()

"""Build identity captured from the running image, never from campaign saves."""
import os
import re

from . import __version__


def build_info():
    number = os.environ.get('EMPIRE_BUILD_NUMBER', 'local')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.\-]{0,39}', number):
        number = 'local'
    revision = os.environ.get('EMPIRE_GIT_SHA', '')
    if not re.fullmatch(r'[a-f0-9]{40}', revision):
        revision = ''
    short = revision[:7]
    return {'number': number, 'revision': revision, 'short_revision': short,
            'version': __version__, 'label': f'Build {number}',
            'detail': f'v{__version__}' + (f' · {short}' if short else ''),
            'header': number + (f'-{short}' if short else '')}

"""The actual browser helper must also work where HTTP disables randomUUID."""
from pathlib import Path
import shutil
import subprocess

import pytest


def test_http_lan_command_ids_are_unique_valid_uuids():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is optional; needed for the browser command-ID regression.')
    source = Path(__file__).resolve().parents[1] / 'economic_simulation/static/game.js'
    script = r'''
const fs = require('fs');
const vm = require('vm');
const assert = require('node:assert/strict');
const {webcrypto} = require('node:crypto');
const source = fs.readFileSync(process.argv[1], 'utf8').split('const token =')[0];
let calls = 0;
const http = {crypto: {getRandomValues(bytes) { calls++; return webcrypto.getRandomValues(bytes); }}};
vm.createContext(http);
vm.runInContext(source, http);
const ids = Array.from({length: 1000}, () => vm.runInContext('commandId()', http));
assert.equal(calls, 1000);
assert.equal(new Set(ids).size, 1000);
assert.ok(ids.every(id => /^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/.test(id)));
const https = {crypto: {randomUUID: () => 'native-uuid'}};
vm.createContext(https);
vm.runInContext(source, https);
assert.equal(vm.runInContext('commandId()', https), 'native-uuid');
'''
    subprocess.run([node, '-e', script, str(source)], check=True, capture_output=True, text=True)

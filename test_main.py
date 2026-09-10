import copy
import os
import unittest
from unittest.mock import patch
import httpx
from fastapi.testclient import TestClient
from main import app

PAYLOAD = {'event': 'messages.upsert', 'instance': 'home-assistance', 'data': {
    'key': {'id': 'abc', 'remoteJid': '919876543210@s.whatsapp.net', 'fromMe': False},
    'message': {'conversation': 'Hi Sachin'}}}

class EchoTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'EVOLUTION_API_URL': 'https://evolution.example',
            'EVOLUTION_API_KEY': 'test', 'WEBHOOK_SECRET': 's'*32}, clear=True)
        self.env.start()
        self.client = TestClient(app)
        self.client.__enter__()
        self.calls = []
        self.status = 201
        async def send(url, **kwargs):
            self.calls.append((url, kwargs))
            return httpx.Response(self.status, request=httpx.Request('POST', url))
        self.mock = patch.object(app.state.client, 'post', side_effect=send)
        self.mock.start()

    def tearDown(self):
        self.mock.stop()
        self.client.__exit__(None, None, None)
        self.env.stop()

    def post(self, payload):
        return self.client.post('/webhooks/evolution', json=payload,
                                headers={'x-webhook-secret': 's'*32})

    def test_echo_and_duplicate(self):
        self.assertEqual(self.post(PAYLOAD).json()['echoed'], 1)
        self.assertEqual(self.post(PAYLOAD).json()['echoed'], 0)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.calls[0][1]['json'], {'number': '919876543210', 'text': 'Hi Sachin'})

    def test_own_group_wrong_instance_and_media(self):
        for variant in ('own', 'group', 'instance', 'media'):
            p = copy.deepcopy(PAYLOAD)
            if variant == 'own': p['data']['key']['fromMe'] = True
            if variant == 'group': p['data']['key']['remoteJid'] = '123@g.us'
            if variant == 'instance': p['instance'] = 'other'
            if variant == 'media': p['data']['message'] = {'imageMessage': {}}
            self.assertEqual(self.post(p).json()['echoed'], 0)
        self.assertEqual(self.calls, [])

    def test_secret_required(self):
        self.assertEqual(self.client.post('/webhooks/evolution', json=PAYLOAD).status_code, 401)
        self.assertEqual(self.calls, [])

    def test_failed_send_can_be_retried(self):
        self.status = 500
        self.assertEqual(self.post(PAYLOAD).status_code, 502)
        self.status = 201
        self.assertEqual(self.post(PAYLOAD).json()['echoed'], 1)

    def test_extended_text_batch(self):
        p = copy.deepcopy(PAYLOAD)
        p['data']['message'] = {'extendedTextMessage': {'text': 'नमस्कार'}}
        p['data'] = [p['data']]
        self.assertEqual(self.post(p).json()['echoed'], 1)
        self.assertEqual(self.calls[0][1]['json']['text'], 'नमस्कार')

if __name__ == '__main__':
    unittest.main()

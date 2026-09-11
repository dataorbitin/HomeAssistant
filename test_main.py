import os
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app


class WebhookTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            'EVOLUTION_API_URL': 'https://evolution.example',
            'EVOLUTION_API_KEY': 'test', 'WEBHOOK_SECRET': 's' * 32,
        }, clear=True)
        self.env.start()
        self.client = TestClient(app)
        self.client.__enter__()
        self.output = patch('builtins.print')
        self.output.start()

    def tearDown(self):
        self.output.stop()
        self.client.__exit__(None, None, None)
        self.env.stop()

    def test_authenticated_payloads_do_not_send_echo(self):
        with patch.object(app.state.client, 'post') as send:
            for payload in ({'message': 'Hello'}, ['Hello'], None):
                response = self.client.post('/webhook/evolution', json=payload,
                    content='null' if payload is None else None,
                    headers={'x-webhook-secret': 's' * 32})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {'status': 'ok'})
            send.assert_not_called()

    def test_query_token(self):
        response = self.client.post('/webhook/evolution',
            params={'token': 's' * 32}, json={})
        self.assertEqual(response.status_code, 200)

    def test_secret_required(self):
        response = self.client.post('/webhook/evolution', json={})
        self.assertEqual(response.status_code, 401)

    def test_invalid_json(self):
        response = self.client.post('/webhook/evolution', content='{',
            headers={'x-webhook-secret': 's' * 32})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['detail'], 'Invalid JSON: JSONDecodeError')


if __name__ == '__main__':
    unittest.main()

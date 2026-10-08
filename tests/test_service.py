import unittest
from unittest.mock import patch

import service


class ModelPayloadTests(unittest.TestCase):
    def payload(self, name=None):
        data = {'text': '测试正文', 'version': 'v4.28.2'}
        if name is not None:
            data['model_name'] = name
        return {'tmpl': '<div class="brand-name">Amadeus</div>', 'tmpldata': data}

    def test_metadata_passed_without_changing_text(self):
        with patch.object(service, '_compile_image', return_value=(b'image', 'image/png')) as compile_image:
            service._render(self.payload('gpt-sol'))
            self.assertEqual(compile_image.call_args.args[:2], ('测试正文', 'v4.28.2'))
            self.assertEqual(compile_image.call_args.args[-1], 'gpt-sol')
            self.assertTrue(compile_image.call_args.kwargs['legacy_reply_prefix'])

    def test_missing_or_invalid_metadata_is_compatible(self):
        for name in (None, {'secret': 'not-a-model'}, 123):
            with self.subTest(name=name), patch.object(service, '_compile_image', return_value=(b'image', 'image/png')) as compile_image:
                service._render(self.payload(name))
                self.assertEqual(compile_image.call_args.args[-1], '')

    def test_non_codex_fallback_does_not_reinterpret_code_as_quotes(self):
        payload = self.payload('model')
        payload['tmpl'] = '<div>another plugin</div>'
        with patch.object(service, '_proxy_unsupported', side_effect=service.RenderError('unavailable')), patch.object(service, '_compile_image', return_value=(b'image', 'image/png')) as compile_image:
            service._render(payload)
            self.assertFalse(compile_image.call_args.kwargs['legacy_reply_prefix'])

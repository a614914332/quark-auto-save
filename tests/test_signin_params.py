import unittest
import types
import sys
from unittest import mock

sys.modules.setdefault(
    "requests",
    types.SimpleNamespace(
        request=lambda *args, **kwargs: None,
        Response=lambda: types.SimpleNamespace(status_code=None, _content=b""),
    ),
)
sys.modules.setdefault("natsort", types.SimpleNamespace(natsorted=lambda items: items))
sys.modules.setdefault("treelib", types.SimpleNamespace(Tree=object))

from quark_auto_save import Quark
import quark_auto_save


class SigninParamParsingTests(unittest.TestCase):
    def test_parse_semicolon_cookie_params(self):
        cookie = "__uid=1; kps=abc123; sign=xyz456; vcode=vvv789"
        self.assertEqual(
            Quark(cookie).mparam,
            {
                "kps": "abc123",
                "kp": "abc123",
                "sign": "xyz456",
                "vcode": "vvv789",
            },
        )

    def test_parse_ampersand_mobile_params(self):
        cookie = "__uid=1; mobile_params=kps=abc&sign=xyz&vcode=vvv"
        self.assertEqual(
            Quark(cookie).mparam,
            {"kps": "abc", "kp": "abc", "sign": "xyz", "vcode": "vvv"},
        )

    def test_decode_double_encoded_and_urlsafe_values(self):
        cookie = (
            "__uid=1; "
            "kps=a%252Bb%253D%253D; "
            "sign=abc-_123%252F%252B%253D; "
            "vcode=v-_%252B42"
        )
        self.assertEqual(
            Quark(cookie).mparam,
            {
                "kps": "a+b==",
                "kp": "a+b==",
                "sign": "abc-_123/+=",
                "vcode": "v-_+42",
            },
        )

    def test_missing_any_param_returns_empty_dict(self):
        cookie = "__uid=1; kps=abc123; sign=xyz456"
        self.assertEqual(Quark(cookie).mparam, {})

    def test_parse_growth_params_from_url(self):
        cookie = (
            "__uid=1; "
            "https://drive-m.quark.cn/1/clouddrive/capacity/growth/info"
            "?kps=abc123&sign=xyz456&vcode=1234567890&fr=iphone&ve=10.8.1.2995"
        )
        self.assertEqual(
            Quark(cookie).mparam,
            {
                "kps": "abc123",
                "kp": "abc123",
                "sign": "xyz456",
                "vcode": "1234567890",
                "fr": "iphone",
                "ve": "10.8.1.2995",
            },
        )

    def test_build_growth_query_applies_defaults_and_refreshes_vcode(self):
        account = Quark("__uid=1; kps=abc123; sign=xyz456; vcode=1234567890")
        query = account._build_growth_query()
        self.assertEqual(query["kps"], "abc123")
        self.assertEqual(query["kp"], "abc123")
        self.assertEqual(query["sign"], "xyz456")
        self.assertEqual(query["fr"], "iphone")
        self.assertEqual(query["sign_cyclic"], "true")
        self.assertEqual(query["fetch_record"], "true")
        self.assertTrue(query["__t"].isdigit())
        self.assertEqual(query["vcode"], "1234567890")

    def test_build_growth_headers_matches_mobile_request_shape(self):
        headers = Quark("__uid=1; kps=abc123; sign=xyz456; vcode=1234567890")._build_growth_headers()
        self.assertEqual(headers["origin"], "https://b.quark.cn")
        self.assertEqual(headers["referer"], "https://b.quark.cn/")
        self.assertEqual(headers["sec-fetch-site"], "same-site")
        self.assertIn("iPhone", headers["user-agent"])

    def test_growth_info_without_mobile_params_uses_pc_cookie_fallback(self):
        response = types.SimpleNamespace(json=lambda: {"data": {"ok": True}})

        with mock.patch.object(quark_auto_save.requests, "request", return_value=response) as request:
            account = Quark("__uid=1; other=value")
            self.assertEqual(account.get_growth_info(), {"ok": True})

        _, url = request.call_args.args
        kwargs = request.call_args.kwargs
        self.assertEqual(
            url,
            "https://drive-m.quark.cn/1/clouddrive/capacity/growth/info",
        )
        self.assertEqual(kwargs["params"], {"pr": "ucpro", "fr": "pc", "uc_param_str": ""})
        self.assertEqual(kwargs["headers"]["cookie"], "__uid=1; other=value")


if __name__ == "__main__":
    unittest.main()

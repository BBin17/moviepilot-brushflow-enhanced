"""通用站点签到的安全判定测试。"""

from types import SimpleNamespace
from unittest.mock import patch

from app.plugins.brushflow.signin import signin_site


def _site(**overrides):
    return {
        "id": 1,
        "name": "测试站",
        "url": "https://pt.example.test/",
        "cookie": "c_secure_uid=1",
        "ua": "Mozilla/5.0",
        **overrides,
    }


def test_generic_attendance_success():
    response = SimpleNamespace(status_code=200, text="签到成功，获得 10 魔力值")
    with patch("app.plugins.brushflow.signin.RequestUtils") as request_utils:
        request_utils.return_value.get_res.return_value = response
        success, message = signin_site(_site())

    assert success is True
    assert message == "今日已签到"
    request_utils.return_value.get_res.assert_called_once_with(
        url="https://pt.example.test/attendance.php"
    )


def test_login_form_is_not_treated_as_success():
    response = SimpleNamespace(
        status_code=200,
        text='<form action="login.php"><input name="username"></form>',
    )
    with patch("app.plugins.brushflow.signin.RequestUtils") as request_utils:
        request_utils.return_value.get_res.return_value = response
        success, message = signin_site(_site())

    assert success is False
    assert message == "签到失败，Cookie 已失效"


def test_cloudflare_response_is_not_submitted():
    response = SimpleNamespace(status_code=403, text="Just a moment... Cloudflare")
    with patch("app.plugins.brushflow.signin.RequestUtils") as request_utils:
        request_utils.return_value.get_res.return_value = response
        success, message = signin_site(_site())

    assert success is False
    assert message == "签到失败，站点需要浏览器验证"

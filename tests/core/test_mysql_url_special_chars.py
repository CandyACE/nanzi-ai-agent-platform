"""Issue #68: MySQL 密码含 @ 等特殊字符时，连接 URL 不得被错误拆分 host。"""

from sqlalchemy.engine.url import URL


def _build_url(driver: str, user: str, password: str, host: str, port: int, db: str) -> URL:
    """与 Settings.build_mysql_url 相同的构造方式。"""
    return URL.create(
        drivername=driver,
        username=user,
        password=password,
        host=host,
        port=port,
        database=db,
    )


def test_mysql_url_encodes_at_in_password():
    url = _build_url(
        "mysql+aiomysql",
        "root",
        "pass1298@secret",
        "192.168.90.202",
        3306,
        "aiagent",
    )
    assert url.host == "192.168.90.202"
    assert url.password == "pass1298@secret"
    assert url.username == "root"
    rendered = url.render_as_string(hide_password=False)
    assert "192.168.90.202" in rendered
    assert "pass1298%40secret" in rendered
    # 复现 Issue #68：未编码时会被解析成 host=1298@192.168.90.202
    assert "1298@192.168.90.202" not in rendered


def test_mysql_sync_url_encodes_special_chars():
    url = _build_url(
        "mysql+pymysql",
        "root",
        "p@ss:w/ord#1",
        "192.168.90.202",
        3306,
        "aiagent",
    )
    rendered = url.render_as_string(hide_password=False)
    assert rendered.startswith("mysql+pymysql://")
    assert "@192.168.90.202" in rendered
    assert "p%40ss" in rendered
    assert "p@ss:w/ord#1" not in rendered

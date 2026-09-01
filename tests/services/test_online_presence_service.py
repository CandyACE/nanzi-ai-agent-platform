"""在线用户 Presence 服务测试。"""

import pytest

from app.services.online_presence_service import OnlinePresenceService


pytestmark = pytest.mark.no_infrastructure


class _FakePipeline:
    def __init__(self, redis):
        self.redis = redis
        self.commands = []

    def zadd(self, key, mapping):
        self.commands.append(("zadd", key, mapping))

    def hset(self, key, mapping):
        self.commands.append(("hset", key, mapping))

    def expire(self, key, seconds):
        self.commands.append(("expire", key, seconds))

    def hgetall(self, key):
        self.commands.append(("hgetall", key))

    async def execute(self):
        results = []
        for command in self.commands:
            if command[0] == "zadd":
                _, key, mapping = command
                self.redis.zsets.setdefault(key, {}).update(mapping)
                results.append(1)
            elif command[0] == "hset":
                _, key, mapping = command
                self.redis.hashes.setdefault(key, {}).update(mapping)
                results.append(1)
            elif command[0] == "expire":
                results.append(True)
            else:
                _, key = command
                results.append(self.redis.hashes.get(key, {}))
        return results


class _FakeRedis:
    def __init__(self):
        self.strings = {}
        self.zsets = {}
        self.hashes = {}
        self.removed_members = []

    async def set(self, key, value, *, ex, nx):
        assert ex > 0
        assert nx is True
        if key in self.strings:
            return None
        self.strings[key] = value
        return True

    def pipeline(self):
        return _FakePipeline(self)

    async def zremrangebyscore(self, key, minimum, maximum):
        members = self.zsets.get(key, {})
        expired = [member for member, score in members.items() if score <= maximum]
        for member in expired:
            del members[member]
        self.removed_members.extend(expired)
        return len(expired)

    async def zrange(self, key, start, end):
        members = self.zsets.get(key, {})
        ordered = sorted(members.items(), key=lambda item: (item[1], item[0]))
        return [member for member, _ in ordered]

    async def zrem(self, key, *members):
        for member in members:
            self.zsets.get(key, {}).pop(member, None)


@pytest.mark.asyncio
async def test_touch_online_user_records_presence_and_throttles_writes():
    redis = _FakeRedis()

    first = await OnlinePresenceService.touch(
        {"user_id": "1", "user_name": "admin", "real_name": "管理员", "role": "admin"},
        redis_client=redis,
        now=1000,
    )
    second = await OnlinePresenceService.touch(
        {"user_id": "1", "user_name": "admin", "real_name": "管理员", "role": "admin"},
        redis_client=redis,
        now=1010,
    )

    assert first is True
    assert second is False
    assert redis.zsets["presence:users"] == {"1": 1300}
    assert redis.hashes["presence:user:1"]["last_active"] == "1000"


@pytest.mark.asyncio
async def test_list_active_users_removes_expired_presence_and_returns_current_users():
    redis = _FakeRedis()
    redis.zsets["presence:users"] = {"1": 1300, "2": 900}
    redis.hashes["presence:user:1"] = {
        "user_id": "1",
        "user_name": "admin",
        "real_name": "管理员",
        "role": "admin",
        "last_active": "1000",
    }

    users = await OnlinePresenceService.list_active_users(redis_client=redis, now=1000)

    assert users == [redis.hashes["presence:user:1"]]
    assert redis.zsets["presence:users"] == {"1": 1300}
    assert redis.removed_members == ["2"]

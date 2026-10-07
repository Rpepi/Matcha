import pytest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from app import presence
from app.presence import user_connected, user_disconnected, reset_presence


def make_redis(*, incr=1, decr=0, keys=()):
    redis = AsyncMock()
    redis.incr = AsyncMock(return_value=incr)
    redis.decr = AsyncMock(return_value=decr)
    redis.delete = AsyncMock()

    async def scan_iter(match=None):
        for key in keys:
            yield key

    redis.scan_iter = MagicMock(side_effect=scan_iter)
    return redis


@pytest.fixture
def db():
    """Patch the pool used by app.presence; yields the connection its blocks receive."""
    conn = AsyncMock()
    cursor = MagicMock()
    cursor.rowcount = 0
    conn.execute = AsyncMock(return_value=cursor)
    conn.commit = AsyncMock()

    @asynccontextmanager
    async def connection():
        yield conn

    pool = MagicMock()
    pool.connection = connection
    with patch.object(presence.pool_module, "pool", pool):
        conn.cursor_result = cursor
        yield conn


class TestUserConnected:
    async def test_first_stream_marks_the_user_online(self, db):
        redis = make_redis(incr=1)

        await user_connected(redis, 7)

        redis.incr.assert_awaited_once_with("presence:connections:7")
        query, params = db.execute.await_args.args
        assert "is_online = true" in query
        assert params == (7,)
        db.commit.assert_awaited_once()

    @pytest.mark.parametrize("count", [2, 3, 10])
    async def test_a_second_tab_changes_nothing_in_the_database(self, db, count):
        await user_connected(make_redis(incr=count), 7)

        db.execute.assert_not_called()
        db.commit.assert_not_called()

    async def test_counts_per_user(self, db):
        redis = make_redis(incr=2)
        await user_connected(redis, 7)
        await user_connected(redis, 8)
        assert [c.args[0] for c in redis.incr.await_args_list] == ["presence:connections:7", "presence:connections:8"]


class TestUserDisconnected:
    async def test_last_stream_marks_the_user_offline_and_stamps_last_seen(self, db):
        redis = make_redis(decr=0)

        await user_disconnected(redis, 7)

        redis.decr.assert_awaited_once_with("presence:connections:7")
        query, params = db.execute.await_args.args
        assert "is_online = false" in query and "last_seen = NOW()" in query
        assert params == (7,)
        db.commit.assert_awaited_once()

    async def test_the_counter_is_deleted_once_it_reaches_zero(self, db):
        redis = make_redis(decr=0)
        await user_disconnected(redis, 7)
        redis.delete.assert_awaited_once_with("presence:connections:7")

    @pytest.mark.parametrize("count", [1, 2, 5])
    async def test_other_tabs_still_open_keeps_the_user_online(self, db, count):
        redis = make_redis(decr=count)

        await user_disconnected(redis, 7)

        db.execute.assert_not_called()
        redis.delete.assert_not_called()

    async def test_a_negative_count_is_repaired_not_kept(self, db):
        # E.g. a counter lost to a Redis restart, then a stream closing.
        redis = make_redis(decr=-1)

        await user_disconnected(redis, 7)

        redis.delete.assert_awaited_once_with("presence:connections:7")
        assert "is_online = false" in db.execute.await_args.args[0]


class TestResetPresence:
    async def test_deletes_every_counter_and_marks_the_flagged_users_offline(self, db):
        redis = make_redis(keys=["presence:connections:1", "presence:connections:9"])

        await reset_presence(redis)

        redis.scan_iter.assert_called_once_with(match="presence:connections:*")
        assert [c.args[0] for c in redis.delete.await_args_list] == ["presence:connections:1", "presence:connections:9"]
        query = db.execute.await_args.args[0]
        assert "is_online = false" in query and "last_seen = NOW()" in query and "WHERE is_online" in query
        db.commit.assert_awaited_once()

    async def test_works_with_nothing_to_reset(self, db):
        await reset_presence(make_redis(keys=[]))
        db.commit.assert_awaited_once()

    async def test_only_touches_users_flagged_online(self, db):
        # A blanket UPDATE would stamp every account's last_seen at each restart.
        await reset_presence(make_redis())
        assert "WHERE is_online" in db.execute.await_args.args[0]

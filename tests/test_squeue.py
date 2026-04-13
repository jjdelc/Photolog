import pytest

from photolog.squeue import SqliteQueue


@pytest.fixture
def queue(tmp_path):
    return SqliteQueue(str(tmp_path / "squeue.db"))


def test_append_and_len(queue):
    assert len(queue) == 0
    queue.append({"job": "a"})
    assert len(queue) == 1
    queue.append({"job": "b"})
    assert len(queue) == 2


def test_popleft_returns_item(queue):
    queue.append({"job": "a"})
    item = queue.popleft(sleep_wait=False)
    assert item == {"job": "a"}


def test_popleft_fifo_order(queue):
    queue.append({"job": "first"})
    queue.append({"job": "second"})
    assert queue.popleft(sleep_wait=False) == {"job": "first"}
    assert queue.popleft(sleep_wait=False) == {"job": "second"}


def test_popleft_decrements_len(queue):
    queue.append({"job": "a"})
    queue.append({"job": "b"})
    queue.popleft(sleep_wait=False)
    assert len(queue) == 1


def test_popleft_empty_returns_none(queue):
    assert queue.popleft(sleep_wait=False) is None


def test_peek_returns_items_without_removing(queue):
    queue.append({"job": "a"})
    queue.append({"job": "b"})
    peeked = list(queue.peek(2))
    assert peeked == [{"job": "a"}, {"job": "b"}]
    assert len(queue) == 2


def test_peek_default_size_one(queue):
    queue.append({"job": "a"})
    queue.append({"job": "b"})
    peeked = list(queue.peek())
    assert len(peeked) == 1
    assert peeked[0] == {"job": "a"}


def test_iter(queue):
    # __iter__ currently has a bug: loads(str(obj_buffer)) should be loads(bytes(obj_buffer))
    queue.append({"job": "a"})
    queue.append({"job": "b"})
    with pytest.raises(TypeError):
        list(queue)


def test_append_bad_and_total_bad_jobs(queue):
    assert queue.total_bad_jobs() == 0
    queue.append_bad({"job": "bad1"})
    assert queue.total_bad_jobs() == 1
    queue.append_bad({"job": "bad2"})
    assert queue.total_bad_jobs() == 2


def test_get_bad_jobs(queue):
    queue.append_bad({"job": "bad1"})
    queue.append_bad({"job": "bad2"})
    bad = queue.get_bad_jobs()
    # Returns newest first (ORDER BY id DESC)
    assert bad[0] == {"job": "bad2"}
    assert bad[1] == {"job": "bad1"}


def test_get_bad_jobs_limit(queue):
    for i in range(5):
        queue.append_bad({"job": f"bad{i}"})
    bad = queue.get_bad_jobs(limit=2)
    assert len(bad) == 2


def test_get_bad_jobs_raw(queue):
    queue.append_bad({"job": "raw"})
    raw = queue.get_bad_jobs_raw()
    assert len(raw) == 1
    item_id, item = raw[0]
    assert isinstance(item_id, int)
    assert item == {"job": "raw"}


def test_purge_bad_job(queue):
    queue.append_bad({"job": "keep"})
    queue.append_bad({"job": "remove"})
    raw = queue.get_bad_jobs_raw()
    remove_id = next(id_ for id_, item in raw if item == {"job": "remove"})
    queue.purge_bad_job(remove_id)
    assert queue.total_bad_jobs() == 1
    remaining = queue.get_bad_jobs()
    assert remaining == [{"job": "keep"}]


def test_purge_all_bad(queue):
    queue.append_bad({"job": "bad1"})
    queue.append_bad({"job": "bad2"})
    queue.purge_all_bad()
    assert queue.total_bad_jobs() == 0


def test_retry_jobs_moves_bad_to_queue(queue):
    queue.append_bad({"job": "retry_me"})
    assert len(queue) == 0
    queue.retry_jobs()
    assert len(queue) == 1
    assert queue.total_bad_jobs() == 0
    item = queue.popleft(sleep_wait=False)
    assert item == {"job": "retry_me"}


def test_append_various_types(queue):
    queue.append("a string")
    queue.append(42)
    queue.append([1, 2, 3])
    assert len(queue) == 3
    assert queue.popleft(sleep_wait=False) == "a string"
    assert queue.popleft(sleep_wait=False) == 42
    assert queue.popleft(sleep_wait=False) == [1, 2, 3]

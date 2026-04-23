# tests/test_hashmap.py

import pytest
from core.hash_map import HashMap


# ==================================================================
# 1. Basic put / get
# ==================================================================

class TestPutGet:

    def test_put_and_get_single_key(self):
        hmap = HashMap()
        hmap.put("k1", 42)
        assert hmap.get("k1") == 42

    def test_get_missing_key_returns_none(self):
        hmap = HashMap()
        assert hmap.get("ghost") is None

    def test_put_updates_existing_key(self):
        hmap = HashMap()
        hmap.put("k1", "first")
        hmap.put("k1", "second")
        assert hmap.get("k1") == "second"

    def test_put_update_does_not_increase_size(self):
        hmap = HashMap()
        hmap.put("k1", 1)
        hmap.put("k1", 2)
        assert hmap._size == 1

    def test_put_multiple_keys(self):
        hmap = HashMap()
        for i in range(10):
            hmap.put(f"key{i}", i * 10)
        for i in range(10):
            assert hmap.get(f"key{i}") == i * 10

    def test_put_none_value(self):
        """None is a valid value — must not be confused with 'not found'."""
        hmap = HashMap()
        hmap.put("k1", None)
        # has() should confirm the key exists even though the value is None
        assert hmap.has("k1") is True

    def test_put_various_value_types(self):
        hmap = HashMap()
        hmap.put("int",   123)
        hmap.put("str",   "hello")
        hmap.put("list",  [1, 2, 3])
        hmap.put("dict",  {"a": 1})
        assert hmap.get("int")  == 123
        assert hmap.get("str")  == "hello"
        assert hmap.get("list") == [1, 2, 3]
        assert hmap.get("dict") == {"a": 1}


# ==================================================================
# 2. has()
# ==================================================================

class TestHas:

    def test_has_existing_key(self):
        hmap = HashMap()
        hmap.put("x", 1)
        assert hmap.has("x") is True

    def test_has_missing_key(self):
        hmap = HashMap()
        assert hmap.has("x") is False

    def test_has_after_delete_returns_false(self):
        hmap = HashMap()
        hmap.put("x", 1)
        hmap.delete("x")
        assert hmap.has("x") is False

    def test_has_on_empty_map(self):
        hmap = HashMap()
        assert hmap.has("anything") is False


# ==================================================================
# 3. delete()
# ==================================================================

class TestDelete:

    def test_delete_existing_key_returns_true(self):
        hmap = HashMap()
        hmap.put("k1", 99)
        assert hmap.delete("k1") is True

    def test_delete_missing_key_returns_false(self):
        hmap = HashMap()
        assert hmap.delete("ghost") is False

    def test_delete_decrements_size(self):
        hmap = HashMap()
        hmap.put("k1", 1)
        hmap.put("k2", 2)
        hmap.delete("k1")
        assert hmap._size == 1

    def test_delete_makes_key_unretrievable(self):
        hmap = HashMap()
        hmap.put("k1", 1)
        hmap.delete("k1")
        assert hmap.get("k1") is None

    def test_delete_same_key_twice(self):
        hmap = HashMap()
        hmap.put("k1", 1)
        assert hmap.delete("k1") is True
        assert hmap.delete("k1") is False   # already gone

    def test_delete_all_keys_size_zero(self):
        hmap = HashMap()
        for i in range(5):
            hmap.put(f"k{i}", i)
        for i in range(5):
            hmap.delete(f"k{i}")
        assert hmap._size == 0

    def test_reinsert_after_delete(self):
        """Key deleted and re-inserted must be retrievable with new value."""
        hmap = HashMap()
        hmap.put("k1", "original")
        hmap.delete("k1")
        hmap.put("k1", "new")
        assert hmap.get("k1") == "new"
        assert hmap._size == 1


# ==================================================================
# 4. Tombstone correctness
# ==================================================================

class TestTombstone:

    def test_key_after_tombstone_still_findable(self):
        """
        The classic tombstone test:
        insert a, b, c in same probe chain → delete b (tombstone) →
        c must still be found.
        """
        hmap = HashMap(capacity=8)
        hmap.put("a", 1)
        hmap.put("b", 2)
        hmap.put("c", 3)
        hmap.delete("b")
        assert hmap.get("a") == 1
        assert hmap.get("b") is None
        assert hmap.get("c") == 3

    def test_insert_reuses_tombstone_slot(self):
        """
        After deleting a key its tombstone slot should be reused
        on the next insert of a different key in the same chain.
        The size must reflect only live entries.
        """
        hmap = HashMap(capacity=8)
        hmap.put("a", 1)
        hmap.put("b", 2)
        hmap.delete("a")
        hmap.put("d", 4)   # should reuse the tombstone
        assert hmap.get("d") == 4
        assert hmap._size == 2   # "b" and "d"

    def test_multiple_tombstones_chain_intact(self):
        """Delete several keys in sequence — remaining keys must survive."""
        hmap = HashMap(capacity=16)
        keys = [f"key{i}" for i in range(8)]
        for i, k in enumerate(keys):
            hmap.put(k, i)
        # delete alternating keys
        for k in keys[::2]:
            hmap.delete(k)
        # remaining keys must still be retrievable
        for i, k in enumerate(keys[1::2]):
            assert hmap.get(k) == keys.index(k)

    def test_has_false_on_tombstone(self):
        hmap = HashMap(capacity=8)
        hmap.put("k1", 1)
        hmap.delete("k1")
        assert hmap.has("k1") is False


# ==================================================================
# 5. Resize / rehash
# ==================================================================

class TestResize:

    def test_resize_triggers_at_70_percent_load(self):
        """
        _resize_if_needed is called BEFORE each insert, so the resize
        fires when the CURRENT load >= 0.7 at the start of a put call.
        capacity=10: after 7 inserts load=0.7, the 8th put triggers resize.
        """
        hmap = HashMap(capacity=10)
        for i in range(7):
            hmap.put(f"k{i}", i)
        # load is exactly 0.7 — resize hasn't fired yet (check is strict <)
        assert hmap._capacity == 10
        # 8th insert: load=0.7 fails the < 0.7 guard → resize fires
        hmap.put("k7", 7)
        assert hmap._capacity > 10

    def test_all_keys_survive_resize(self):
        hmap = HashMap(capacity=8)
        for i in range(100):
            hmap.put(f"key{i}", i * 10)
        for i in range(100):
            assert hmap.get(f"key{i}") == i * 10, f"key{i} lost after resize"

    def test_size_correct_after_resize(self):
        hmap = HashMap(capacity=8)
        for i in range(50):
            hmap.put(f"k{i}", i)
        assert hmap._size == 50

    def test_capacity_doubles(self):
        """
        capacity=8: after 6 inserts load=0.75, the 7th put's pre-check
        sees 6/8=0.75 >= 0.7 and doubles capacity to 16.
        """
        hmap = HashMap(capacity=8)
        for i in range(6):
            hmap.put(f"k{i}", i)
        assert hmap._capacity == 8    # not yet triggered
        hmap.put("k6", 6)             # 7th insert triggers resize
        assert hmap._capacity == 16

    def test_tombstones_not_copied_on_resize(self):
        """Tombstones must be dropped during rehash — only live entries copied."""
        hmap = HashMap(capacity=8)
        for i in range(4):
            hmap.put(f"k{i}", i)
        hmap.delete("k0")
        hmap.delete("k1")
        # trigger resize
        for i in range(4, 10):
            hmap.put(f"k{i}", i)
        # deleted keys must still be gone
        assert hmap.get("k0") is None
        assert hmap.get("k1") is None
        # live keys must survive
        for i in range(2, 10):
            assert hmap.get(f"k{i}") == i

    def test_operations_work_after_multiple_resizes(self):
        hmap = HashMap(capacity=4)
        for i in range(200):
            hmap.put(f"key{i}", i)
        for i in range(0, 200, 2):
            hmap.delete(f"key{i}")
        for i in range(1, 200, 2):
            assert hmap.get(f"key{i}") == i
        for i in range(0, 200, 2):
            assert hmap.get(f"key{i}") is None


# ==================================================================
# 6. Size tracking
# ==================================================================

class TestSizeTracking:

    def test_empty_map_size_zero(self):
        hmap = HashMap()
        assert hmap._size == 0

    def test_size_increments_on_insert(self):
        hmap = HashMap()
        for i in range(5):
            hmap.put(f"k{i}", i)
            assert hmap._size == i + 1

    def test_size_unchanged_on_update(self):
        hmap = HashMap()
        hmap.put("k1", 1)
        hmap.put("k1", 2)
        hmap.put("k1", 3)
        assert hmap._size == 1

    def test_size_decrements_on_delete(self):
        hmap = HashMap()
        hmap.put("k1", 1)
        hmap.put("k2", 2)
        hmap.delete("k1")
        assert hmap._size == 1

    def test_size_unchanged_on_delete_missing(self):
        hmap = HashMap()
        hmap.put("k1", 1)
        hmap.delete("ghost")
        assert hmap._size == 1


# ==================================================================
# 7. Edge cases
# ==================================================================

class TestEdgeCases:

    def test_empty_string_key(self):
        hmap = HashMap()
        hmap.put("", "empty key value")
        assert hmap.get("") == "empty key value"
        assert hmap.has("") is True

    def test_single_character_keys(self):
        hmap = HashMap()
        for ch in "abcdefghij":
            hmap.put(ch, ord(ch))
        for ch in "abcdefghij":
            assert hmap.get(ch) == ord(ch)

    def test_long_key(self):
        hmap = HashMap()
        long_key = "x" * 1000
        hmap.put(long_key, "long")
        assert hmap.get(long_key) == "long"

    def test_repr_shows_live_entries(self):
        hmap = HashMap()
        hmap.put("a", 1)
        hmap.put("b", 2)
        hmap.delete("a")
        r = repr(hmap)
        assert "b" in r
        assert "a" not in r

    def test_large_volume_insert_delete_reinsert(self):
        """Stress: insert 300 keys, delete half, reinsert deleted ones."""
        hmap = HashMap()
        for i in range(300):
            hmap.put(f"k{i}", i)
        for i in range(0, 300, 2):
            hmap.delete(f"k{i}")
        for i in range(0, 300, 2):
            hmap.put(f"k{i}", i * 100)
        for i in range(0, 300, 2):
            assert hmap.get(f"k{i}") == i * 100
        for i in range(1, 300, 2):
            assert hmap.get(f"k{i}") == i

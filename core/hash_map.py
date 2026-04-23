# core/hash_map.py

class HashMap:

    _TOMBSTONE = object()

    def __init__(self, capacity: int = 64):
        self._capacity = capacity
        self._buckets = [None] * self._capacity
        self._size = 0            # live entries only
        self._tombstones = 0      # deleted-but-not-yet-reclaimed slots

    def _hash(self, key: str) -> int:
        return hash(key) % self._capacity

    def _probe(self, key: str):
        index = self._hash(key)
        first_tombstone = None

        for _ in range(self._capacity):
            slot = self._buckets[index]

            if slot is None:
                if first_tombstone is not None:
                    return first_tombstone, False
                return index, False

            if slot is self._TOMBSTONE:
                if first_tombstone is None:
                    first_tombstone = index

            elif slot[0] == key:
                return index, True

            index = (index + 1) % self._capacity

        if first_tombstone is not None:
            return first_tombstone, False
        raise OverflowError("HashMap is full")

    def put(self, key: str, value) -> None:
        self._resize_if_needed()
        index, found = self._probe(key)

        if not found:
            self._size += 1
            # Overwriting a tombstone slot: decrement tombstone count so
            # _load_factor() does not double-count this slot.
            if self._buckets[index] is self._TOMBSTONE:
                self._tombstones -= 1

        self._buckets[index] = (key, value)

    def get(self, key: str):
        index, found = self._probe(key)
        if found:
            return self._buckets[index][1]
        return None

    def delete(self, key: str) -> bool:
        index, found = self._probe(key)
        if not found:
            return False
        self._buckets[index] = self._TOMBSTONE
        self._size -= 1
        self._tombstones += 1
        return True

    def has(self, key: str) -> bool:
        _, found = self._probe(key)
        return found

    def _load_factor(self) -> float:
        # Count live + tombstones so probe-chain length is bounded.
        # Counting only live entries allowed the effective occupancy to
        # reach 100% (all slots are tombstones or live) without triggering
        # a resize, making probe chains degrade to O(n).
        return (self._size + self._tombstones) / self._capacity

    def _resize_if_needed(self):
        if self._load_factor() < 0.7:
            return
        old_buckets = self._buckets
        self._capacity *= 2
        self._buckets = [None] * self._capacity
        self._size = 0
        self._tombstones = 0      # tombstones are purged during rehash

        for slot in old_buckets:
            if slot is not None and slot is not self._TOMBSTONE:
                self.put(slot[0], slot[1])

    def __repr__(self):
        items = [
            f"{slot[0]!r}: {slot[1]!r}"
            for slot in self._buckets
            if slot is not None and slot is not self._TOMBSTONE
        ]
        return "{" + ", ".join(items) + "}"

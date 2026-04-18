# core/hash_map.py


class HashMap:

    _TOMBSTONE = object()  # unique sentinel for deleted slots

    def __init__(self, capacity: int = 64):
        self._capacity = capacity
        self._buckets = [None] * self._capacity  # the raw array
        self._size = 0  # number of live entries

    # ── hashing ──────────────────────────────────────────────

    def _hash(self, key: str) -> int:
        """
        Turn a string key into an array index.
        Uses Python's built-in hash() but constrains it to our array size.
        """
        return hash(key) % self._capacity

    def _probe(self, key: str):
        """
        Linear probing: starting from the hash index, walk forward
        until we find the key, a None slot, or wrap around.

        Returns (index, found):
            - If key exists       → (index_of_key, True)
            - If key not found    → (first_available_slot, False)
        """
        index = self._hash(key)
        first_tombstone = None  # remember first tombstone we passed

        for _ in range(self._capacity):
            slot = self._buckets[index]

            if slot is None:
                # empty slot — key definitely not beyond this point
                if first_tombstone is not None:
                    return first_tombstone, False  # reuse tombstone slot for insert
                return index, False

            if slot is self._TOMBSTONE:
                # deleted slot — key might still be further ahead
                if first_tombstone is None:
                    first_tombstone = index  # remember it for potential insert

            elif slot[0] == key:
                # found it
                return index, True

            index = (index + 1) % self._capacity  # wrap around

        # full loop done — table is full or key not found
        if first_tombstone is not None:
            return first_tombstone, False
        raise OverflowError("HashMap is full")

    # ── core operations ───────────────────────────────────────

    def put(self, key: str, value) -> None:
        """Insert or update a key-value pair. O(1) average."""
        self._resize_if_needed()
        index, found = self._probe(key)

        if not found:
            self._size += 1  # new entry

        self._buckets[index] = (key, value)

    def get(self, key: str):
        """Return value for key, or None if not found. O(1) average."""
        index, found = self._probe(key)
        if found:
            return self._buckets[index][1]
        return None

    def delete(self, key: str) -> bool:
        """
        Remove a key. Places a tombstone so probing chains stay intact.
        Returns True if deleted, False if key didn't exist.
        O(1) average.
        """
        index, found = self._probe(key)
        if not found:
            return False

        self._buckets[index] = self._TOMBSTONE
        self._size -= 1
        return True

    def has(self, key: str) -> bool:
        """Return True if key exists. O(1) average."""
        _, found = self._probe(key)
        return found

    # ── load factor & resizing ────────────────────────────────

    def _load_factor(self) -> float:
        return self._size / self._capacity

    def _resize_if_needed(self):
        """
        If the table is more than 70% full, double its capacity.
        Rehash all existing live entries into the new array.
        """
        if self._load_factor() < 0.7:
            return

        old_buckets = self._buckets
        self._capacity *= 2
        self._buckets = [None] * self._capacity
        self._size = 0  # will be re-counted during rehash

        for slot in old_buckets:
            if slot is not None and slot is not self._TOMBSTONE:
                self.put(slot[0], slot[1])  # re-insert into new array

    # ── display ───────────────────────────────────────────────

    def __repr__(self):
        items = [
            f"{slot[0]!r}: {slot[1]!r}"
            for slot in self._buckets
            if slot is not None and slot is not self._TOMBSTONE
        ]
        return "{" + ", ".join(items) + "}"
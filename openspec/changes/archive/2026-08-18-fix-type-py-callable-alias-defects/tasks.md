## 1. Fix type.py aliases

- [x] 1.1 Update `Mapper` in `type.py` to `Callable[[T], R | None | Awaitable[R | None]]`
- [x] 1.2 Update `Consumer` in `type.py` to `Callable[[T], None | Awaitable[None]]`
- [x] 1.3 Delete the unused `Filterer` alias from `type.py`

## 2. Update call sites

- [x] 2.1 Change `for_each()`'s `consumer` parameter in `stream.py` from `Callable[[T], Any]` to `Consumer[T]`
- [x] 2.2 Change `for_each_ordered()`'s `consumer` parameter in `stream.py` from `Callable[[T], Any]` to `Consumer[T]`
- [x] 2.3 Remove the now-unused `Any` import from `stream.py` if nothing else references it

## 3. Verify

- [x] 3.1 Run `uv run ty check src` and confirm no new type errors
- [x] 3.2 Run `uv run pytest` and confirm the full suite still passes
- [x] 3.3 Run `uv run ruff check .` and `uv run ruff format --check .`

## 4. Documentation

- [x] 4.1 Update `roadmap.md`: move this item from **Now** to **Done** with a summary of the fix

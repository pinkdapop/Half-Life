# fastcache

A tiny in-memory cache for Python services.

## Install

Requires Python 3.8 or newer.

```bash
pip install fastcache==1.4.2
```

fastcache depends on `redis-py` 4.x. On macOS you can also use `brew install redis` and run `redis-server`, which currently ships Redis 6.2.

## Quickstart

```python
from fastcache import Cache
cache = Cache(url="redis://localhost:6379")
cache.set("key", "value", ttl=60)
```

The default TTL is 300 seconds. The maximum key length is 512 bytes.

## Deploying

We recommend deploying on Heroku's free dyno tier for small projects. For production, the cheapest Redis Cloud plan is $5/month and includes 100 MB.

The project is maintained by the team at Example Labs; Jane Doe is the current lead maintainer. Issues go to https://github.com/example-labs/fastcache/issues.

## Compatibility

fastcache supports Django 3.2 and Flask 2.0. Python 2 is not supported. GitHub Actions runs the test suite on `ubuntu-20.04`.

The latest release was tagged in March 2023.

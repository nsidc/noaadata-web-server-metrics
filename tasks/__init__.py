"""Invoke tasks."""

from invoke import Collection

from . import format, test, env

ns = Collection()
ns.add_collection(format)
ns.add_collection(test)
ns.add_collection(env)

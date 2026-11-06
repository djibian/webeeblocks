"""Strict R2025a Webots Supervisor SFBool readback, never authority.

The native Python binding may expose the enabled value as integer 1 rather than
the Python singleton True. Truthy floats/strings/other integers must fail closed.
"""


def enabled(value):
    return value is True or (type(value) is int and value == 1)

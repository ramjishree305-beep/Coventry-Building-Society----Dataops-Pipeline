import os


class MissingSecretError(Exception):
    pass


def get_secret(name):
    value = os.getenv(name)
    if not value:
        raise MissingSecretError(
            f"Secret '{name}' is not set. Add it to your .env file "
            f"(see .env.example) or export it in your shell.")
    return value

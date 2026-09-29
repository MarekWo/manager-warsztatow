from django.conf import settings


def build_info() -> dict[str, str]:
    """The running version and the short commit the image was built from ("" outside an image)."""
    return {"version": settings.APP_VERSION, "build": settings.APP_BUILD[:7]}


def version_string() -> str:
    info = build_info()
    return f"{info['version']} ({info['build']})" if info["build"] else info["version"]

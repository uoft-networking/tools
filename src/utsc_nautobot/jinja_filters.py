from django_jinja import library


@library.filter
def analyze_obj(obj):
    return obj
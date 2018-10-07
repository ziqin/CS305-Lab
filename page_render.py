import os
import urllib.parse

import web


def render_dir(requested_path: str) -> str:
    html_doc = \
'''
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Index of {0}</title></head>
<body>
<h1>Index of {0}</h1><hr>
<ul><li><a href="{1}">../</a></li>{2}</ul><hr>
</body>
</html>
'''
    if not requested_path.endswith('/'):
        requested_path += '/'
    path_linker = '' if requested_path.endswith('/') else '/'

    def path2link(file: str):
        quoted_path = urllib.parse.quote(requested_path + path_linker + file)
        return '<li><a href="{}">{}</a></li>'.format(quoted_path, file)
    lis = ''.join(map(path2link, os.listdir('.' + requested_path)))
    return html_doc.format(requested_path, requested_path + '../', lis)


def render_err(status: int, message: str = None):
    html_doc = \
'''
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>{0} {1}</title></head>
<body><h1>{0} {1}</h1><hr><p>{2}</p></body>
</html>
'''
    if not message:
        message = ''
    return html_doc.format(status, web.HttpResponse.STATUS[status], message)

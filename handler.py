import mimetypes
import os

import page_render
import web


class HandlerBase:
    def __init__(self, methods: tuple=('GET',), is_dedicated: bool=False):
        self.methods = methods
        self.is_dedicated = is_dedicated

    def filtering(self, request) -> bool:
        return request.method in self.methods

    def handle(self, request):
        raise NotImplementedError


class DirBrowseHandler(HandlerBase):
    def __init__(self):
        super().__init__(methods=('GET', 'HEAD'), is_dedicated=True)

    def filtering(self, request) -> bool:
        return super().filtering(request) and os.path.isdir('.' + request.path)

    def handle(self, request):
        doc = page_render.render_dir(request.path)
        mime_type = 'text/html; charset=utf-8'
        if request.method == 'GET':
            resp = web.HttpResponse(status=200, mimetype=mime_type)
            resp.add_body(doc)
        else:  # request.method == 'HEAD':
            resp = web.HttpResponse(status=200, mimetype=mime_type, length=len(doc.encode()))
        return resp


class FileTransHandler(HandlerBase):
    def __init__(self):
        super().__init__(methods=('GET', 'HEAD'), is_dedicated=True)

    def filtering(self, request) -> bool:
        return super().filtering(request) and os.path.isfile('.' + request.path)

    def handle(self, request):
        mime_type = mimetypes.guess_type(request.path, strict=False)[0]
        if not mime_type:
            mime_type = 'application/octet-stream'
        if request.method == 'GET':
            resp = web.HttpResponse(status=200, mimetype=mime_type)
            with open('.' + request.path, 'rb') as f:
                resp.add_body(f.read())
        else:  # request.method = 'HEAD'
            resp = web.HttpResponse(status=200, mimetype=mime_type, length=os.path.getsize('.' + request.path))
        return resp


def handle_err(status: int, message: str=None):
    resp = web.HttpResponse(status=status, mimetype='text/html; charset=utf-8')
    resp.add_body(page_render.render_err(status, message))
    return resp

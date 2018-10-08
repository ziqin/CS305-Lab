import logging
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
        mime_type = 'text/html; charset=utf-8'
        if request.method == 'GET':
            doc = page_render.render_dir(request.path)
            resp = web.HttpResponse(status=200, mimetype=mime_type)
            resp.headers['Content-Length'] = len(doc)
            resp.body = doc
        else:  # request.method == 'HEAD':
            resp = web.HttpResponse(status=200, mimetype=mime_type)
        return resp


class FileTransHandler(HandlerBase):
    def __init__(self):
        super().__init__(methods=('GET', 'HEAD'), is_dedicated=True)

    def filtering(self, request) -> bool:
        return super().filtering(request) and os.path.isfile('.' + request.path)

    def handle(self, request):
        mime = mimetypes.guess_type(request.path)[0] or 'application/octet-stream'
        if request.method == 'GET':
            resp = web.HttpResponse(status=200, mimetype=mime)
            with open('.' + request.path, 'rb') as f:
                file_content = f.read()
            resp.headers['Content-Length'] = len(file_content)
            resp.body = file_content
        else:  # request.method = 'HEAD'
            resp = web.HttpResponse(status=200, mimetype=mime)
            resp.headers['Content-Length'] = os.path.getsize('.' + request.path)

        return resp


class FileRangeTransHandler(HandlerBase):
    def __init__(self):
        super().__init__(methods=('GET',), is_dedicated=True)

    def filtering(self, request) -> bool:
        return super().filtering(request) and \
               'Range' in request.headers and \
               request.headers['Range'].startswith('bytes=') and \
               os.path.isfile('.' + request.path)

    def handle(self, request):
        def parse_range(r):
            range_start, range_end = r.split('-')
            assert range_start != ''
            return int(range_start), (int(range_end) if range_end else None)
        try:
            ranges = [parse_range(r) for r in request.headers['Range'].lstrip('bytes=').split(', ')]
        except (ValueError, AssertionError) as e:
            raise web.ParsingError from e

        if len(ranges) > 1:
            logging.error('multipart/byteranges requests handling not implemented, returning complete resource')
            return FileTransHandler().handle(request)
        relative_path = '.' + request.path
        file_size = os.path.getsize(relative_path)
        begin, end = ranges[0]
        end = end or file_size - 1
        if not begin <= end < file_size:
            raise web.RangeNotSatisfiableError
        content_length = end - begin + 1
        with open(relative_path, 'rb') as f:
            f.seek(begin)
            file_content = f.read(content_length)
        mime = mimetypes.guess_type(request.path)[0] or 'application/octet-stream'
        resp = web.HttpResponse(status=206, mimetype=mime)
        resp.headers['Content-Range'] = 'bytes {}-{}/{}'.format(begin, end, file_size)
        resp.body = file_content
        return resp


def handle_err(status: int, message: str=None):
    resp = web.HttpResponse(status=status, mimetype='text/html; charset=utf-8')
    resp.body = page_render.render_err(status, message)
    resp.headers['Content-Length'] = len(resp.body)
    return resp

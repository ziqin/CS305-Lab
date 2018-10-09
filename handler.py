import logging
import mimetypes
import os
import urllib.parse

import page_render
import web


def handle_err(status: int, message: str=None):
    resp = web.HttpResponse(status=status, mimetype='text/html; charset=utf-8')
    resp.body = page_render.render_err(status, message)
    resp.headers['Content-Length'] = len(resp.body)
    resp.add_cookie('last-visit', '/', max_age=-1)
    return resp


class HandlerBase:
    methods = 'GET',

    @classmethod
    def filtering(cls, request) -> bool:
        if cls is HandlerBase:
            raise NotImplementedError
        return request.method in cls.methods

    @classmethod
    def process(cls, request, response):
        raise NotImplementedError


class DirBrowseHandler(HandlerBase):
    methods = 'GET', 'HEAD'

    @classmethod
    def filtering(cls, request) -> bool:
        return super().filtering(request) and os.path.isdir('.' + request.path)

    @classmethod
    def process(cls, request, response):
        response.status = 200
        response.mime = 'text/html; charset=utf-8'
        response.add_cookie(name='last-visit', value=urllib.parse.quote(request.path), max_age=7776000)  # 90 days
        if request.method == 'GET':
            doc = page_render.render_dir(request.path)
            response.body = doc
            response.headers['Content-Length'] = len(response.body)


class FileTransHandler(HandlerBase):
    methods = 'GET', 'HEAD'

    @classmethod
    def filtering(cls, request) -> bool:
        return super().filtering(request) and os.path.isfile('.' + request.path)

    @classmethod
    def process(cls, request, response):
        response.status = 200
        response.mime = mimetypes.guess_type(request.path)[0]
        if request.method == 'GET':
            with open('.' + request.path, 'rb') as f:
                file_content = f.read()
            response.headers['Content-Length'] = len(file_content)
            response.body = file_content
        else:  # request.method = 'HEAD'
            response.headers['Content-Length'] = os.path.getsize('.' + request.path)


class FileRangeTransHandler(HandlerBase):
    methods = 'GET',

    @classmethod
    def filtering(cls, request) -> bool:
        return super().filtering(request) and \
               'Range' in request.headers and \
               request.headers['Range'].startswith('bytes=') and \
               os.path.isfile('.' + request.path)

    @classmethod
    def process(cls, request, response):
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
            FileTransHandler.process(request, request)
            return
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

        response.status = 206
        response.mime = mimetypes.guess_type(request.path)[0]
        response.headers['Content-Range'] = 'bytes {}-{}/{}'.format(begin, end, file_size)
        response.body = file_content


class LastVisitHandler(HandlerBase):
    methods = 'GET', 'HEAD'

    @classmethod
    def filtering(cls, request):
        return super().filtering(request) and request.path == '/' and \
            'last-visit' in request.cookies and 'Referer' not in request.headers

    @classmethod
    def process(cls, request, response):
        last_visit = request.cookies['last-visit'].value
        response.status = 302
        response.mime = 'text/html; charset=utf-8'
        response.headers['Location'] = last_visit
        response.body = page_render.render_redirect(response.status, last_visit)
        logging.info('redirect to %s', last_visit)

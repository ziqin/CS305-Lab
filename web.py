import asyncio
import errno
import logging
import os
import sys
import time
import urllib.parse

import handler


class HttpServer:
    def __init__(self, host: str, port: int = 80):
        self.host = host
        self.port = port
        self.handlers = [handler.DirBrowseHandler(), handler.FileTransHandler()]

    def run(self):
        loop = asyncio.get_event_loop()
        coroutine = asyncio.start_server(self.connected_callback, self.host, self.port, loop=loop)
        server = loop.run_until_complete(coroutine)
        logging.info('Listening http://%s:%d', self.host, self.port)
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            logging.info('Quit.')
        finally:
            server.close()
            loop.run_until_complete(server.wait_closed())
            loop.close()

    async def connected_callback(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        response = ''
        try:
            header_data = await reader.readuntil(separator=b'\r\n\r\n')
            request = HttpRequest(header_data)
            if request.method not in ('GET', 'HEAD'):
                raise HttpServer.MethodNotAllowedError(request.method)
            if not os.path.exists('.' + request.path):
                raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), request.path)
            for hdl in self.handlers:
                if hdl.filtering(request) and hdl.is_dedicated:
                    response = hdl.handle(request)
                    break
            logging.info('Sending response: %s', request.path)
        except HttpRequest.ParsingError:
            logging.warning('Bad request')
            response = handler.handle_err(400)
        except PermissionError as e:
            logging.warning('Permission denied: %s', e.filename)
            response = handler.handle_err(403)
        except FileNotFoundError as e:
           logging.warning('File not exist: %s', e.filename)
           response = handler.handle_err(404)
        except HttpServer.MethodNotAllowedError as e:
            logging.warning('Method not allowed: %s', e.method_name)
            response = handler.handle_err(405)
        except asyncio.IncompleteReadError:
            pass
        except RuntimeError:
            logging.exception("Oops!")
            response = handler.handle_err(500)
        finally:
            writer.write(response.encode())
            await writer.drain()
            writer.close()
            if sys.version_info >= (3, 7):
                await writer.wait_closed()

    class MethodNotAllowedError(ValueError):
        def __init__(self, method_name: str):
            self.method_name = method_name

        def __str__(self):
            return 'HTTP method {} is not allowed'.format(self.method_name)


class HttpRequest:
    def __init__(self, data):
        try:
            header_lines = data.decode().split('\r\n')
            self.method, path, self.protocol = header_lines[0].split(' ')
            self.path = urllib.parse.unquote(path)
            self.headers = {}
            for field in header_lines[1:]:
                if field:
                    field_name, field_value = field.split(': ')
                    self.headers[field_name] = field_value
        except ValueError as e:
            raise HttpRequest.ParsingError('failed to parse the HTTP request') from e

    class ParsingError(RuntimeError):
        pass


class HttpResponse:
    PROTOCOL = 'HTTP/1.0'

    STATUS = {
        200: 'OK',
        301: 'Moved Permanently',
        400: 'Bad Request',
        404: 'Not Found',
        405: 'Method Not Allowed',
        500: 'Internal Server Error'
    }

    def __init__(self, status: int, mimetype: str, length: int = None):
        self.status = status
        self.mimetype = mimetype
        self.length = length
        self.body = None

    def add_body(self, body):
        body_type = type(body)
        if body_type is bytes:
            self.body = body
        elif body_type is str:
            self.body = body.encode()
        else:
            raise TypeError('response body should be bytes or string')
        self.length = len(self.body)

    def encode(self) -> bytes:
        response_head = list()
        response_head.append('{} {} {}\r\n'.format(HttpResponse.PROTOCOL, self.status, HttpResponse.STATUS[self.status]))
        fields = {
            'Connection': 'close',
            'Server': 'WebFileBrowser/1.0',
            'Date': time.strftime('%a, %d %b %Y %H:%M:%S GMT', time.gmtime()),
            'Content-Type': self.mimetype,
            'Content-Length': self.length
        }
        response_head.extend(('{}: {}\r\n'.format(name, value) for name, value in fields.items()))
        response_head_bytes = ''.join(response_head).encode()
        return b'\r\n'.join([response_head_bytes, self.body if self.body else b''])

#!/usr/bin/env python3

"""Web File Browser"""

__author__ = 'Jeeken (Wang Ziqin)'
__version__ = '1.0'


import asyncio
import mimetypes
import os
import sys
import time
import urllib.parse


HOST = '127.0.0.1'
PORT = 8080


class ParseError(ValueError):
    pass


class MethodNotAllowedError(ValueError):
    pass


class HttpRequestHeader:
    def __init__(self, data):
        try:
            header_lines = data.decode().split('\r\n')
            self.method, self.path, self.protocol = header_lines[0].split(' ')
            self.headers = {}
            for field in header_lines[1:]:
                if field:
                    field_name, field_value = field.split(': ')
                    self.headers[field_name] = field_value
        except:
            raise ParseError('failed to parse HTTP header')


class HttpResponse:
    STATUS_CODE = {
        200: 'OK',
        400: 'BAD REQUEST',
        404: 'NOT FOUND',
        405: 'METHOD NOT ALLOWED',
        500: 'INTERNAL SERVER ERROR'
    }

    def __init__(self, status: int, body: bytes, mimetype: str, is_persistent=False):
        self.protocol = 'HTTP/1.1' if is_persistent else 'HTTP/1.0'
        self.status = status
        self.persistent = is_persistent
        self.mimetype = mimetype
        self.body = body

    def encode(self) -> bytes:
        headers = {
            'Connection': 'keep-alive' if self.persistent else 'close',
            'Server': 'WebFileBrowser/1.0',
            'Date': time.strftime('%a, %d %b %Y %H:%M:%S GMT', time.gmtime()),
            'Content-Type': self.mimetype,
            'Content-Length': len(self.body)
        }
        response = list()
        response.append('{} {} {}'.format(self.protocol, self.status, HttpResponse.STATUS_CODE[self.status]))
        response.extend(('{}: {}'.format(name, value) for name, value in headers.items()))
        return b'\r\n\r\n'.join(['\r\n'.join(response).encode(), self.body])

    @staticmethod
    def response_error(status: int):
        error_doc = '''
        <!DOCTYPE html>
        <html>
            <head><title>{0} {1}</title></head>
            <body><h1>{0} {1}</h1><hr></body>
        </html>
        '''.format(status, HttpResponse.STATUS_CODE[status])
        return HttpResponse(status, error_doc.encode(), 'text/html; charset=utf-8')

    @staticmethod
    def render_dir(dir_path: str):
        files = '\n'.join(['<li><a href="{}">{}</a></li>'.format('./'+urllib.parse.quote(f), f)
            for f in os.listdir(dir_path)])
        doc = '''
        <!DOCTYPE html>
        <html>
            <head><title>Index of {0}</title></head>
            <body>
                <h1>Index of {0}</h1>
                <hr>
                <ul>
                    <li><a href="../">../</a></li>
                    {1}
                </ul>
                <hr>
            </body>
        </html>
        '''.format(dir_path, files)
        return HttpResponse(200, doc.encode(), 'text/html; charset=utf-8')


async def connected_callback(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    try:
        header_data = await reader.readuntil(separator=b'\r\n\r\n')
        request_header = HttpRequestHeader(header_data)
        if request_header.method != 'GET':
            raise MethodNotAllowedError('Only GET method is supported')
        path = '.' + urllib.parse.unquote(request_header.path)

        if os.path.isdir(path):
            response = HttpResponse.render_dir(path)
        else:
            mimetype, _ = mimetypes.guess_type(request_header.path)
            with open(path, 'rb') as f:
                file_content = f.read()
            response = HttpResponse(200, file_content, mimetype if mimetype else 'application/octet-stream')
        writer.write(response.encode())
        print('Sent response: {}'.format(path))

    except FileNotFoundError:
        print('File not exist', file=sys.stderr)
        writer.write(HttpResponse.response_error(404).encode())
    except MethodNotAllowedError:
        print('Method not allowed', file=sys.stderr)
        writer.write(HttpResponse.response_error(405).encode())
    except ParseError:
        print('Bad request', file=sys.stderr)
        writer.write(HttpResponse.response_error(400).encode())
    except:
        print('Oops!', file=sys.stderr)
        writer.write(HttpResponse.response_error(500).encode())
    finally:
        await writer.drain()
        writer.close()
        await writer.wait_closed()


def web():
    loop = asyncio.get_event_loop()
    coroutine = asyncio.start_server(connected_callback, HOST, PORT, loop=loop)
    server = loop.run_until_complete(coroutine)
    print('Listening http://{}:{}'.format(HOST, PORT))
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        print("\nCtrl+C pressed, quit.")
    finally:
        server.close()
        loop.run_until_complete(server.wait_closed())
        loop.close()


if __name__ == '__main__':
    web()

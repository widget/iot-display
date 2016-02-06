
import re
import socket
import gc

class Connect(object):

    def __init__(self, host, port=80, debug=False):
        self.host = host
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.address = socket.getaddrinfo(host, port)[0][4]
        self.debug = debug
        self.last_fetch_time = (0, 0, 0, 0, 0, 0)

    @staticmethod
    def simple_strptime(date_str):
        """
        Decode a date of a fixed form
        :param date_str: Of the form  "Sun, 31 Jan 2016 14:16:24 GMT"
        :return: tuple (2016,1,31,14,16,24)
        """
        MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
        date = re.compile(r'(\d+) (\w+) (\d+) (\d+):(\d+):(\d+)', )
        res = date.search(date_str)
        month = MONTHS.index(res.group(2))
        return res.group(3), month, res.group(1), res.group(4), res.group(5), res.group(6)

    def fetch(self, path, path_type='octet-stream', max_length=16384):
        """
        HTTP request, like normal things.  Sets the date in last_fetch_time.  Will attempt
        to keep-alive.
        :param path: Path on the website to pull
        :param path_type: Content-Type (substring match)
        :param max_length: Maximum Content-Length to accept
        :return: The content (no headers)
        """

        req = 'GET {path} HTTP/1.0\nHost: {host}\n'.format(host=self.host, path=path)
        req += 'Connection: keep-alive\n'
        # TODO Authorization (sic)? Would only manage Basic unless we do an OAuth trick
        # Using HTTP/1.0 with keep-alive as 1.1 can't refuse chunking (unlikely though it is)
        req += 'User-Agent: Widget-IoTDisplay/1.0\nAccept-Encoding: identity\n\n'

        req = req.encode()

        try:
            self.socket.send(req)
        except OSError:
            self.socket = socket.socket()
            self.socket.connect(self.address)
            self.socket.send(req)

        try:
            header_line = self.socket.readline().decode()
        except OSError:
            raise RuntimeError("Couldn't connect to server")

        # First line better be "HTTP/1.0 200 OK"
        if "200 OK" not in header_line:
            raise RuntimeError("Can't handle server response: " + header_line)

        length = 0
        content_type = ""
        self.last_fetch_time = (0, 0, 0, 0, 0, 0)
        keep_alive = False
        in_headers = True
        while in_headers:
            # Parse each line in turn, we'll check the current date and
            # how much data is coming, and its type
            header_line = self.socket.readline().decode()
            if self.debug:
                print(header_line,end='') # EOL in string already

            arg = header_line.split(':')[-1].strip()
            if "date" in header_line.lower():
                # Grab time and keep it but we check the whole line with a regex
                self.last_fetch_time = Connect.simple_strptime(header_line)
            elif "content-length" in header_line.lower():
                #  Extract the length
                length = int(arg)
            elif "content-type" in header_line.lower():
                content_type = arg
            elif header_line == '\r\n':
                # No more headers
                in_headers = False
            elif "keep-alive" in header_line.lower():
                keep_alive = True

        # Cleanup before the (potentially mahoosive fetch)
        del header_line
        del in_headers
        # Force gc after our mess above
        gc.collect()

        content = None
        if length > max_length:
            self.socket.close()
            raise RuntimeError("Requested entity too large (%d)" % length)
        if path_type not in content_type:
            raise ValueError("Can't verify content type")
        if length == 0:
            raise ValueError("Not sure how big the payload is")

        content = self.socket.recv(length)

        if not keep_alive:
            if self.debug:
                print("No keep-alive, closing socket")
            self.socket.close()
        return content

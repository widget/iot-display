import re
import socket
import gc


class Connect(object):

    # Using HTTP/1.0 with keep-alive as 1.1 can't refuse chunking (unlikely though it is)
    REQ = """{method} {path} HTTP/1.0\r
Host: {host}\r
Connection: keep-alive\r
User-Agent: Widget-IoTDisplay/1.0\r
"""

    def __init__(self, host, port=80, debug=False):
        self.keep_alive = False
        self.host = host
        self.socket = socket.socket()
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
        MONTHS = [
            "Jan",
            "Feb",
            "Mar",
            "Apr",
            "May",
            "Jun",
            "Jul",
            "Aug",
            "Sep",
            "Oct",
            "Nov",
            "Dec",
        ]
        date = re.compile(
            r"(\d+) (\w+) (\d+) (\d+):(\d+):(\d+)",
        )
        res = date.search(date_str)
        month = MONTHS.index(res.group(2))
        return (
            int(res.group(3)),
            month + 1,
            int(res.group(1)),
            int(res.group(4)),
            int(res.group(5)),
            int(res.group(6)),
        )

    def post(self, path, **kwargs):

        content_dict = []
        for key, value in kwargs.items():
            content_dict.append("%s=%s" % (key, value))

        content = "&".join(content_dict)

        req = Connect.REQ.format(host=self.host, path=path, method="POST")
        req += (
            "Content-Type: application/x-www-form-urlencoded\r\nContent-Length: %d\r\n\r\n"
            % len(content)
        )

        if self.debug:
            print(req)
            print(content)

        req = req.encode()

        try:
            self.socket.send(req)
        except OSError:
            self.socket = socket.socket()
            self.socket.connect(self.address)
            self.socket.send(req)

        self.socket.send(content.encode())
        content_type, header_line, in_headers, length = self.parse_headers()

        self._close_keep_alive()

    def get_quick(self, path, path_type="octet-stream", max_length=16384):
        """
        HTTP request, like normal things.  Sets the date in last_fetch_time.  Will attempt
        to keep-alive.
        :param path: Path on the website to pull
        :param path_type: Content-Type (substring match)
        :param max_length: Maximum Content-Length to accept
        :return: The content (no headers)
        """

        length = self._do_get(max_length, path, path_type)
        # Force gc before we do some big allocs
        gc.collect()

        # Keep getting until we've got what we were promised
        content = b""
        while len(content) < length:
            content += self.socket.recv(length - len(content))

        self._close_keep_alive()
        return content

    def get_object(self, path, path_type="octet-stream", max_length=16384):
        """
        HTTP request for big things.  Sets the date in last_fetch_time.  Will attempt
        to keep-alive.  Returns the socket (file like object) for things to sip
        data from.  Needs cleaning when done
        :param path: Path on the website to pull
        :param path_type: Content-Type (substring match)
        :param max_length: Maximum Content-Length to accept
        :return: The content (no headers)
        """

        length = self._do_get(max_length, path, path_type)
        # Force gc before we do some big allocs
        gc.collect()

        return length, self.socket

    def get_object_done(self):
        self._close_keep_alive()

    def _do_get(self, max_length, path, path_type):
        req = Connect.REQ.format(host=self.host, path=path, method="GET")
        req += "Accept-Encoding: identity\r\n\r\n"
        req = req.encode()
        try:
            self.socket.send(req)
        except OSError:
            if self.debug:
                print("Socket not already open, opening and sending request")
            self.socket = socket.socket()
            self.socket.connect(self.address)
            self.socket.send(req)
        content_type, header_line, in_headers, length = self.parse_headers()
        # Cleanup before the (potentially mahoosive fetch)
        del header_line
        del in_headers
        content = None
        if length > max_length:
            self.socket.close()
            raise RuntimeError("Requested entity too large (%d)" % length)
        if path_type not in content_type:
            raise ValueError("Can't verify content type")
        if length == 0:
            raise ValueError("Not sure how big the payload is")

        return length

    def _close_keep_alive(self):
        if not self.keep_alive:
            if self.debug:
                print("No keep-alive, closing socket")
            self.socket.close()
            self.socket = socket.socket()

    def parse_headers(self):
        try:
            header_line = self.socket.readline().decode()
        except OSError:
            raise RuntimeError("Couldn't connect to server")

        if self.debug:
            print(header_line, end="")  # EOL in string already\

        # First line better be "HTTP/1.0 200 OK"
        if "200 OK" not in header_line:
            raise RuntimeError("Can't handle server response: " + header_line)
        length = 0
        content_type = ""
        self.last_fetch_time = (0, 0, 0, 0, 0, 0)
        in_headers = True
        while in_headers:
            # Parse each line in turn, we'll check the current date and
            # how much data is coming, and its type
            header_line = self.socket.readline().decode()

            arg = header_line.split(":")[-1].strip()
            if "date" in header_line.lower():
                # Grab time and keep it but we check the whole line with a regex
                self.last_fetch_time = Connect.simple_strptime(header_line)
            elif "content-length" in header_line.lower():
                #  Extract the length
                length = int(arg)
            elif "content-type" in header_line.lower():
                content_type = arg
            elif header_line == "\r\n":
                # No more headers
                in_headers = False
            elif "keep-alive" in header_line.lower():
                self.keep_alive = True

            if self.debug and in_headers:
                print(header_line, end="")  # EOL in string already

        return content_type, header_line, in_headers, length

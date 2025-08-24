from datetime import datetime
from logging.config import dictConfig

from flask import Flask, abort, request
from lxml import etree
from tzlocal import get_localzone
from werkzeug.middleware.proxy_fix import ProxyFix

dictConfig(
    {
        "version": 1,
        "formatters": {
            "default": {
                "format": "%(asctime)s %(levelname)s %(message)s",
            }
        },
        "handlers": {
            "wsgi": {
                "class": "logging.StreamHandler",
                "stream": "ext://flask.logging.wsgi_errors_stream",
                "formatter": "default",
            }
        },
        "root": {"level": "INFO", "handlers": ["wsgi"]},
    }
)

# Create the application, then warn it that it's behind a proxy
app = Flask("iot comms", static_folder="/static")
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_host=1)
tz = get_localzone()

SERVER_METADATA = "/static/server.xml"
MAX_ENTRIES = 1000


@app.route("/upload.php", methods=["POST"])
def hello_world():
    battery = request.form.get("battery")
    reset = request.form.get("reset")
    screen = request.form.get("screen")
    if not battery:
        app.logger.info("No battery key in POST")
        abort(400)

    if not reset:
        app.logger.info("No reset key in POST")
        abort(400)

    if not screen:
        app.logger.info("No screen key in POST")
        abort(400)

    # Get the base XML
    try:
        parser = etree.XMLParser(remove_blank_text=True)
        metadata = etree.parse(SERVER_METADATA, parser)
        app.logger.debug("Loaded existing XML")
    except OSError:
        app.logger.exception("Can't open XML file")
        metadata = etree.ElementTree(etree.Element("display"))

    # Get the client node
    client_node = metadata.find("./client")
    if client_node is None:
        client_node = etree.SubElement(metadata.getroot(), "client")

    # Delete node if there's too many
    num_children = len(client_node)
    app.logger.info("Currently %d entries" % num_children)
    if num_children > MAX_ENTRIES:
        to_delete = num_children - MAX_ENTRIES
        app.logger.info("Deleting oldest %d", to_delete)
        for _ in range(to_delete):
            client_node.remove(client_node.getchildren()[0])

    # Set timezone on the time
    now = tz.localize(datetime.now())

    # Store current values
    latest = etree.SubElement(client_node, "log")
    latest.attrib["battery"] = battery
    latest.attrib["reset"] = reset
    latest.attrib["screen"] = screen
    latest.attrib["ip"] = request.remote_addr
    latest.attrib["time"] = now.strftime("%Y-%m-%dT%H:%M:%S")

    metadata.write(SERVER_METADATA, xml_declaration=True, pretty_print=True)
    return ""


@app.route("/data.bin")
def data_bin():
    app.logger.debug("Binary image requested")
    return app.send_static_file("data.bin")


@app.route("/data.png")
def data_png():
    app.logger.debug("Preview requested")
    return app.send_static_file("data.png")


@app.route("/status.html")
def send_status():
    app.logger.debug("Status page")
    return app.send_static_file("status.html")


@app.route("/metadata.json")
def send_metadata():
    app.logger.debug("Metadata")
    return app.send_static_file("metadata.json")

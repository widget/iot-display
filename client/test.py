
import time
from epd import EPD
from connect import Connect
import gc


def update_loop(url, interval=0, port=80):
    """
    Download image, update display, sleep, loop.
    Gives up on any error
    :param url:
    :param interval:
    :param port:
    :return:
    """
    e = EPD()
    e.enable()
    sep = url.find('/')
    host = url[:sep]
    path = url[sep:]
    del sep
    while True:# TODO WDT reqd
        print("Mem free: %d" % gc.mem_free())

        c = Connect(host, port, debug=True)
        content = c.fetch(path)
        print("Uploading...", end='')
        e.upload_whole_image(content)
        print("done.")
        e.display_update()
        del content
        del c

        if interval > 0:
            print("Sleeping for %ds" % interval)
            time.sleep(interval)
        else:
            input("Press enter to update (Ctrl-C to stop).")

        gc.collect()

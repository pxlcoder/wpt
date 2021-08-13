#!/usr/bin/python
import json
import logging
import urllib
import threading
from queue import Empty

from mod_pywebsocket import stream, msgutil
from wptserve import stash


logger = logging.getLogger()


address, authkey = stash.load_env_config()
stash = stash.Stash("msg_channel", address=address, authkey=authkey)


def web_socket_do_extra_handshake(request):
    return


def web_socket_transfer_data(request):
    uuid, direction = parse_request(request)
    print("Got web_socket_transfer_data %s %s" % (uuid, direction))

    with stash.lock:
        value = stash.take(uuid)
        if value is None:
            queue = stash.get_queue()
            if direction == "read":
                has_reader = True
                writer_count = 0
            else:
                has_reader = False
                writer_count = 1
        else:
            queue, has_reader, writer_count = value
            if direction == "read":
                if has_reader:
                    raise ValueError("Tried to start multiple readers for the same queue")
            else:
                writer_count += 1

        stash.put(uuid, (queue, has_reader, writer_count))

    if direction == "read":
        run_read(request, uuid, queue)
    elif direction == "write":
        run_write(request, uuid, queue)

    close_channel(uuid, direction)


def web_socket_passive_closing_handshake(request):
    uuid, direction = parse_request(request)
    print("Got web_socket_passive_closing_handshake %s %s" % (uuid, direction))
    close_channel(uuid, direction)
    return request.ws_close_code, request.ws_close_reason


def parse_request(request):
    query = request.unparsed_uri.split('?')[1]
    GET = dict(urllib.parse.parse_qsl(query))
    uuid = GET["uuid"]
    direction = GET["direction"]
    return uuid, direction


def wait_for_close(request, uuid, queue):
    closed = False
    while not closed:
        try:
            print("wait_for_close started on read thread for %s" % uuid)
            line = request.ws_stream.receive_message()
            if line is None:
                break
            try:
                cmd, data = json.loads(line)
            except ValueError:
                cmd = None
            if cmd == "close":
                closed = True
                print("Got client initiated close for %s" % uuid)
            else:
                logger.warning("Unexpected message on read socket  %s", line)
        except Exception:
            if not (request.server_terminated or request.client_terminated):
                print("Got exception in wait_for_close %s:\n %s" % (uuid, traceback.format_exc()))
            closed = True

    if not request.server_terminated:
        queue.put(("close", None))


def run_read(request, uuid, queue):
    close_thread = threading.Thread(target=wait_for_close, args=(request, uuid, queue), daemon=True)
    close_thread.start()

    while True:
        try:
            data = queue.get(True, 1)
        except Empty:
            if request.server_terminated or request.client_terminated:
                break
        else:
            print(f"Got data {data}")
            cmd, body = data
            if cmd == "close":
                break

            if cmd == "message":
                msgutil.send_message(request, json.dumps(body))
            else:
                logger.warning("Unknown queue command %s", cmd)


def run_write(request, uuid, queue):
    while True:
        line = request.ws_stream.receive_message()
        if line is None:
            break
        cmd, body = json.loads(line)
        if cmd == "pause":
            queue.put(("close", None))
        elif cmd == "message":
            print(f"Putting data {line}")
            queue.put((cmd, body))
        elif cmd == "delete":
            close_channel(uuid, None)


def close_channel(uuid, direction):
    # Decrease the refcount of the queue
    # Direction of None indicates that we force delete the queue from the stash
    print("Got close_socket %s %s" % (uuid, direction))
    with stash.lock:
        data = stash.take(uuid)
        if data is None or direction is None:
            return
        queue, has_reader, writer_count = data
        if direction == "read":
            has_reader = False
        else:
            writer_count -= 1

        if has_reader and writer_count > 0 or not queue.empty():
            print("Updating refcount %s %s %s" % (uuid, has_reader, writer_count))
            stash.put(uuid, (queue, has_reader, writer_count))
        else:
            print("Deleting message queue for %s" % uuid)

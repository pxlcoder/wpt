# Store a queue of messages in the stash
def main(request, response):
    uuid = request.GET[b'uuid']
    stash = request.server.stash

    with stash.lock:
        queue = stash.take(uuid) or []

        if request.method == u'POST':
            queue.append(request.body)
            ret = b'ok'

        # Pull from the |uuid| queue, the posted data.
        else:
            if len(queue) == 0:
                ret = b'none'
            else:
                ret = queue.pop(0)

        stash.put(uuid, queue)
    return ret

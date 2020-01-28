# Threaded Requests
A light weight module that uses a pool with a maximum size and a queue (waiting to use the pool) to make concurrent HTTP requests.  This was originally part of a scraping project that got tangled up in captcha hell, but the base code was useful enough to split out on its own.

## How does it work?
It instantiates both a `urllib3.PoolManager` and a `concurrent.futures.ThreadPoolExecutor` with the same pool size/number of workers.  Each request from the `PoolManager` is sent off in its own thread by the `ThreadPoolExecutor`.  When the response is returned, the thread is completed and the results collected. 

## What are the `ThreadedRequestHandler` classes for?
These classes tell the `RequestQueue` what to retrieve (the `url` parameter).  These are also where you define how the response from each `PoolManager.request` is handled, as well as adding any callbacks for when the thread is closed.  The two abstract method, `parse` and `callback`, are used as follows:
#### `parse`
- Accepts an `urllib3.response.HTTPResponse` as the first argument.
- This method is passed to the thread and applied before the thread completes. So the parsing happens within the thread.
To have it do nothing use:
```
def parse(self, res):
    return res
```

#### `callback`
- Accepts a `concurrent.futures.Future` as the first argument.
- This method runs after the thread closes.  
- It does *not* intrinsically modify the content of the `Future` object (through you can make it do so.)
To have it do nothing use:
```
def callback(self, future):
    pass
```

## Examples
### Pagination
Scrape 1000 pages, but be nice to the server by only running 10 parallel threads.

```
from time import sleep
from requestqueue import RequestQueue 

rq = RequestQueue(10)
url = 'https://some.url.com/?p={}'
for p in range(1, 101):
    rq.add_request_from_url(url.format(p))
while rq.pending:
    print(rq.pending, 'requests pending')
    sleep(1)
results = rq.retrieve_completed
```

### Subclassing
Preparse JSON returns, submit a url from within to the queue

```
import json

class JSONHandler(ThreadedRequestHandler):
    def __init__(self, url, method='GET', queue=None):
        """
        A very basic handler class that parse the response from the
        url as JSON uses the thread callback to add a new request to
        the queue if a new URL is found.
        """
        super().__init__(url, method)
        self.queue=queue

    def parse(self, res):
        return json.loads(res.data)

    def callback(self, thread):
        new_url = thread.result().get('URL')
        if new_url:
            handler = self.__class__(new_url)
            self.queue.add_request(handler)

rq = RequestQueue(10)
url = 'https://somejson.url.com/?p={}'
for p in range(1, 10):
    rq.add_request_from_url(url.format(p), JSONHandler)
while rq.pending:
    print(rq.pending, 'requests pending')
    sleep(1)
results = rq.retrieve_completed
```
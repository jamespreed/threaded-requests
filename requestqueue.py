import urllib3
import certifi
import abc
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed


class ThreadedRequestHandler(metaclass=abc.ABCMeta):
    """
    Base class for all request classes
    """
    def __init__(self, url, method):
        """
        Instantiates a handler to for the results of `url`.  
        """
        self._url = url
        self.method = method

    def __repr__(self):
        n = self.__class__.__name__
        return f'<{n} at 0x{id(self):x}>'

    def __call__(self, pool_request, **kwargs):
        return self.parse(pool_request(self.method, self.url, **kwargs))

    @property
    def url(self):
        return self._url

    @abc.abstractmethod
    def parse(self, res):
        pass

    @abc.abstractmethod
    def callback(self, thread):
        pass


class SimpleThreadedRequestHandler(ThreadedRequestHandler):
    def __init__(self, url, method='GET'):
        """
        A very basic handler class that decodes the response from the
        url and uses the thread callback to store the results in the
        `result` attribute when the thread finishes.
        """
        super().__init__(url, method)
        self.result = None

    def parse(self, res):
        # res is an urllib3 http object.  the `data` attribute holds
        # the raw return.  
        # return as unicode instead of bytes
        return res.data.decode('utf-8')

    def callback(self, thread):
        # copy thread result back to the handler object
        self.result = thread.result()


class RequestQueue:
    """
    Class for queuing up http requests to be processed.
    """

    def __init__(self, pool_size=5):
        self._pool_size = pool_size
        self.thread_pool = ThreadPoolExecutor(pool_size)
        self.http_pool = urllib3.PoolManager(
            maxsize=self.pool_size,
            cert_reqs='CERT_REQUIRED',
            ca_certs=certifi.where()
        )
        self.headers = {
            'User-Agent': 'Python/RequestQueue',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        self.futures = {}

    def __repr__(self):
        s = self.status
        f = s.get('FREE')
        c = s.get('FINISHED', 0)
        z = self.pool_size
        i = id(self)
        return f'<RequestQueue {c} results {f}/{z} threads free at 0x{i:x}>'

    @property
    def pool_size(self):
        return self._pool_size

    def add_request_from_url(self, 
                             url, 
                             handler=SimpleThreadedRequestHandler,
                             **kwargs):
        """
        Convenience method for adding a request to the queue.

        :url: [str] url to retrieve 
        :request: [ThreadedRequestHandler] the type of handler object to 
            instantiate
        :kwargs: additional key-word arguments to pass to the 
            ThreadedRequestHandler
        """
        h = handler(url, **kwargs)
        self.add_request(h)
        return h

    def add_request(self, handler):
        """
        Add a request to the queue based on the `handler` object url.
        """
        f = self.thread_pool.submit(
            handler, 
            self.http_pool.request, 
            headers=self.headers
        )
        f.add_done_callback(handler.callback)
        self.futures[f] = handler

    def retrieve_completed(self):
        completed = [f for f in self.futures if f.done()]
        return [(f.result(), self.futures.pop(f)) for f in completed]

    @property
    def status(self):
        d = dict(Counter(f._state for f in self.futures))
        d['FREE'] = self.pool_size - d.get('RUNNING', 0)
        return d

    @property
    def pending(self):
        return self.status.get('PENDING', 0)

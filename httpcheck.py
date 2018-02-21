#!/bin/bash
import re
import os
import ssl
import sys
import httplib
from urlparse import urlparse


WHITE_LIST = {
}

SKIP_LIST = (
)

BLACK_LIST = {
}


class request():
    def __init__(self, hostname, port="https"):
        self.host = hostname
        self.port = port
        self.connect()

    def connect(self):
        if self.port == "https":
            if sys.version_info >= (2, 7, 9):
                self.conn = httplib.HTTPSConnection(self.host, \
                            context=ssl._create_unverified_context())
            else:
                self.conn = httplib.HTTPSConnection(self.host)
        else:
            self.conn = httplib.HTTPConnection(self.host)

    def get(self, url, ttl=10):
        self.conn.request("GET", url)
        res = self.conn.getresponse()

        # whitelist
        if url in WHITE_LIST:
            if WHITE_LIST[url] == res.status:
                print("skip: url %s is in whitelist" % url)
                return url, ""
        # blacklist
        if url in BLACK_LIST:
            if BLACK_LIST[url] == res.status:
                print("ERROR: known problem url %s is broken" % url)
                return url, ""

        if res.status in [301, 302]:
            if ttl < 1:
                raise Exception("Loop in direction %s%s" % (self.host, url))
            data = res.read()
            link = re.findall("Location:\s*(.*)\r", str(res.msg))[0]
            print("--> %s" % link)
            o = urlparse(link)
            # if o.netloc != self.host:
            #    raise Exception("Wrong hostname %s is not in %s" % (link, self.host))
            if o.scheme != self.port or o.netloc != self.host:
                external_link(link)
                return link, None
            return self.get(o.path, ttl-1)
        if not res.status == 200:
            raise Exception("Http status %s %s %s" % (res.status, url, res.reason))
        data = res.read()
        res.close()
        return url, data


def external_link(link):
    if link in SKIP_LIST:
        print("skip: url %s is in skiplist" % link)
        return
    o = urlparse(link)
    r = request(o.netloc, o.scheme)
    r.get(o.path)



class Runner:
    def __init__(self, url):
        self.visited = set()
        self.queue = set(url)
        self.list = set(self.queue)
        self.external = set()
        self.sources = set()
        self.parents = {}
        self.host = [o.netloc for o in [urlparse(it) for it in url]]

    def loop(self):
        # main loop
        while(self.queue):
            self.next()
            print("%d/%d" % (len(self.queue), len(self.list)))

        # check external links
        for it in sorted(self.external):
            print(it)
            try:
                external_link(it)
            except Exception as e:
                print("Unexpected error: %s" % e.value)
                raise Exception("Error: broken link %s on page %s" % (it, self.parents[it]))

        # check sources
        miss_sources = set()
        for it in sorted(self.sources):
            print(it)
            try:
                external_link(it)
            except:
                miss_sources.add(it)
        print("\n============================")
        print("Broken link %d in sources:" % len(miss_sources))
        print("============================")
        for it in sorted(miss_sources):
            print(it)

    def check(self, url):
        o = urlparse(url)
        self.req = request(o.netloc, o.scheme)
        url, content = self.req.get(o.path)
        oo = urlparse(url)
        if url.startswith("http") and oo.netloc not in self.host:
            self.external.add(url)
            return []
        if url.endswith("pdf"):
            print("Binary file: %s" % url)
            return
        url = "%s://%s%s" % (o.scheme, o.netloc, url)
        return self.parse_content(content, url)

    def parent(self, parent, link):
        if link not in self.parents:
            self.parents[link] = [parent,]
        else:
            if link not in self.parents[link]:
                self.parents[link].append(parent)

    def next(self):
        url = self.queue.pop()
        o = urlparse(url)
        if o.netloc not in self.host:
            self.external.add(url)
            return
        l = self.check(url)
        self.visited.add(url)
        if not l: return

        n = l.difference(self.list)
        self.list = self.list.union(n)
        self.queue = self.queue.union(n)

    def parse_content(self, content, url):
        def absolute_url(link, url):
            link = link.split("#")[0]
            if not link: return
            if link.startswith("http"):
                return link
            elif link.startswith("/"):
                o = urlparse(url)
                path = link.replace("//", "/")
                return "%s://%s%s" % (o.scheme, o.netloc, link)
            else:
                o = urlparse(url)
                path = os.path.dirname(o.path)
                path = path.replace("//", "/")
                return "%s://%s%s/%s" % (o.scheme, o.netloc, path, link)

        re_links = '<a href="?\'?([^"\'>]*)'
        re_sources = '[^<]+(href|src|data)="?\'?([^"\'>]*)'
        s = set()
        for it in re.findall(re_links, content):
            if it.startswith("mailto:"): continue
            link = absolute_url(it, url)
            if not link: continue
            s.add(link)
            self.parent(url, it)

        for tag, it in re.findall(re_sources, content):
            link = absolute_url(it, url)
            # skip if link is empty
            if not link: continue
            # skip url in queue
            if link in s: continue
            # skip if value is email
            if link.startswith("mailto:"): continue
            # save tag link, img, script,..
            self.sources.add(link)

        return s



def main():
    if len(sys.argv) < 2:
        print("RUN: python %s url, url2, ..." % sys.argv[0])
        sys.exit(255)
    r = Runner(sys.argv[1:])
    r.loop()

def test():
    r = Runner("http://studenik.varhoo.cz/")
    r.next()
    
if __name__=="__main__":
    # test()
    main()

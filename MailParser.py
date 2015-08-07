
import sys, time, datetime, traceback, mailbox, os
import email.utils
from email.header import decode_header
sys.stdout = sys.stderr

HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
</head>
<body>
<h2>%(subject)s</h2>
%(body)s
</body>
</html>
"""

HTML_HEAD = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
</head>
<body>
"""

HTML_FOOT = """
</body>
</html>
"""

POST_TEMPLATE = """
<a href=%(msgUrl)s>%(key)s</a> %(dateStr)s<br>
<a href="%(htmlUrl)s">%(subject)s</a>
%(author)s<br>\n"""

def getDate(date):
    if not date:
        return date
    date_tuple=email.utils.parsedate_tz(date)
    if date_tuple:
        date=datetime.datetime.fromtimestamp(email.utils.mktime_tz(date_tuple))
    ds = date.strftime("%A %Y/%m/%d %H:%M:%S %z")
    return ds

def getAuthor(str):
    i = str.find("<")
    if i >= 0:
        j = str.find(">")
        str = str[:i]+str[j+1:]
    return str.strip()

def htmlSafe(s):
    s = str(s)
    s = s.replace("<", "")
    s = s.replace(">", "")
    return s

class MailParser:
    def __init__(self, mboxPath):
        t0 = time.time()
        self.mboxPath = mboxPath
        self.mbox = mailbox.mbox(mboxPath)
        self.contentTypes = {}
        self.subjects = {}
        self.authors = {}
        self.recipients = {}
        #self.msgById = {}
        self.postsByKey = {}
        self.keyById = {}
        t1 = time.time()
        dir = "files"
        if not os.path.exists(dir):
            os.mkdir(dir)
        print "Parser created in %.3fsecs" % (t1-t0)

    def scan(self, maxNum=0):
        t0 = time.time()
        n = 0
        for key in self.mbox.keys():
            if maxNum and n > maxNum:
                return
            n += 1
            try:
                self.process(key)
            except:
                print "Failed on", key
                traceback.print_exc()
        t1 = time.time()
        print "scanned in %.3fsecs" % (t1-t0)

    def process(self, key):
        #print key
        msg = self.mbox[key]
        post = {'key': key, 'refs': [], 'children': []}
        self.postsByKey[key] = post
        msgPath = "files/%d.txt" % key
        file(msgPath, "w").write(msg.as_string())
        try:
            mcType = msg['Content-Type']
        except:
            print "No Content Type"
            return
        msgId = msg['Message-Id']
        self.keyById[msgId] = key
        post['msgId'] = msgId
        #self.msgById[msgId] = msg
        self.postsByKey[msgId] = post
        try:
            refs = msg['References']
            if refs:
                #print "refs:", refs
                refs = refs.split()
                for ref in refs:
                    try:
                        rkey = self.keyById[ref]
                        post['refs'].append(rkey)
                        rpost = self.postsByKey[rkey]
                        rpost['children'].append(key)
                    except KeyError:
                        print "No key for ref", ref
        except:
            traceback.print_exc()
            print "*** problem with refs"
        subject = msg['Subject']
        subject = decode_header(subject)[0][0]
        self.subjects[key] = subject
        author = msg['From']
        self.authors[key] = author
        recipient = msg['To']
        self.recipients[recipient] = 1
        date = msg['Date']
        date = getDate(date)
        post['date'] = date
        post['author'] = author
        post['subject'] = subject
        i = 0
        if msg.is_multipart():
            parts = msg.get_payload()
        else:
            #parts = [msg.get_payload()]
            parts = [msg]
        """
        print "type(parts):", type(parts)
        if type(parts) == type("str"):
            print "*** str parts:", parts
            return
        """
        #print parts
        for part in parts:
            i += 1
            #print part.get_payload()
            try:
                cType = part['Content-Type']
            except:
                print "type(part):", type(part)
                print part
            if cType.find("text/html") >= 0:
                path = "files/%s.html" % key
                print "writing", path
                vals = {'body': part.get_payload(decode=True),
                        'subject': subject}
                htmlStr = HTML_TEMPLATE % vals
                file(path, "w").write(htmlStr)

    def writeIndex(self):
        t0 = time.time()
        f = file("index.html", "w")
        f.write(HTML_HEAD)
        f.write("<h1>Index of CSM posts</h1>\n")
        for key in self.roots:
            post = self.postsByKey[key]
            self.writePost(f, post)
        f.write(HTML_FOOT)
        t1 = time.time()
        print "wrote index in %.3fsecs" % (t1-t0)

    def writePost(self, f, post, indent=""):
        key = post['key']
        print indent+"writePost", key
        author = post['author']
        subject = post['subject']
        dateStr = post['date']
        print key, author
        print subject
        vals = {'author': getAuthor(author),
                'dateStr': dateStr,
                'msgUrl': "files/%s.txt" % key,
                'htmlUrl': "files/%s.html" % key,
                'subject': subject, 'key': key}
        str = POST_TEMPLATE % vals
        f.write(str)
        if post["refs"]:
            f.write("Refs: %s<br>\n" % (htmlSafe(post["refs"]),))
        if post["children"]:
            f.write("Children: %s<br>\n" % (htmlSafe(post['children']),))
        if 'group' in post:
            group = post['group']
            print "group:", group
            f.write("<ul>\n")
            for gkey in group:
                post = self.postsByKey[gkey]
                self.writePost(f, post, "  ")
            f.write("</ul>\n")

    def getGraph(self, post, graph=None):
        key = post['key']
        #print "getGraph", key
        if graph == None:
            graph = dict()
        else:
            graph[key] = post['children']
        for childKey in post['children']:
            try:
                child = self.postsByKey[childKey]
            except KeyError:
                print "*** no post for key", childKey
                continue
            self.getGraph(child, graph)
        return graph
        
    def group(self):
        self.roots = []
        posts = self.postsByKey
        for key in posts:
            post = posts[key]
            if not post['refs']:
                self.roots.append(key)
        print "roots:\n", self.roots, "\n"
        for key in self.roots:
            post = self.postsByKey[key]
            if post['children']:
                post['group'] = self.getGraph(post)

    def dump(self):
        #print key, msg.keys()
        print self.contentTypes
        print "Recipients:"
        print self.recipients

if __name__ == '__main__':
    mp = MailParser("CSM.mbox")
    #mp.scan(100)
    mp.scan()
    #mp.process(29)
    mp.group()
    mp.writeIndex()
    mp.dump()




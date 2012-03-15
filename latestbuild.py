from collections import defaultdict
import json
import logging
import os
import time
from webob import Request, Response, html_escape

from pulsebuildmonitor import start_pulse_monitor, createDaemon

class LatestBuildMonitor(object):

    def __init__(self, port=8034, logger=None):
        self.builds = defaultdict(lambda: defaultdict(dict))
        self.port = port
        self.logger = logger

    def __call__(self, environ, start_response):
        req = Request(environ)
        if req.url.find('README') > -1:
          readme = os.path.join(os.path.dirname(__file__), 'README.html')
          resp = Response(content_type='text/html')
          resp.body = open(readme, 'r').read()
        else:
          resp = Response(content_type='application/json')
          resp.status_int = 200
          resp.body = json.dumps(self.builds)
        return resp(environ, start_response)

    def buildCallback(self, builddata):
        #print '========================================================='
        #print 'buildCallback'
        #print json.dumps(builddata, indent=2)
        #print '========================================================='
        self.builds[builddata['tree']][builddata['platform']].update({builddata['buildtype']:  builddata['buildurl']})
        if not builddata['buildurl']:
          if self.logger:
            self.logger.error('no buildurl:\n%s' % json.dumps(builddata, indent=2))

    def testCallback(self, builddata):
        if False:
            print '========================================================='
            print 'testCallback'
            print json.dumps(builddata, indent=2)
            print '========================================================='

    def pulseCallback(self, data):
        key = data['_meta']['routing_key']

    def start(self):
        monitor = start_pulse_monitor(buildCallback=self.buildCallback,
                                      testCallback=self.testCallback,
                                      pulseCallback=self.pulseCallback,
                                      trees=None)

        from wsgiref.simple_server import make_server, WSGIRequestHandler

        class QuietHandler(WSGIRequestHandler):
          """Custom WSGIRequestHandler class that doesn't do any logging.
          """
          def log_request(*args, **kw):
            pass
          def log_error(*args, **kw):
            pass
          def log_message(*args, **kw):
            pass

        httpd = make_server('127.0.0.1', self.port, self, handler_class=QuietHandler)
        if self.logger:
          self.logger.info('Serving on http://127.0.0.1:%s' % self.port)
        else:
          print 'Serving on http://127.0.0.1:%s' % self.port
        httpd.serve_forever()


def main():
    import optparse
    parser = optparse.OptionParser()
    parser.add_option('-p', '--port', default='8034',
                    dest='port', type='int',
                    help='Port to serve on')
    parser.add_option('--pidfile', dest='pidfile',
                    help='path to file for logging pid')
    parser.add_option('--logfile', dest='logfile',
                    help='path to file for logging output')
    parser.add_option('--daemon', dest='daemon', action='store_true',
                    help='run as daemon')
    options, args = parser.parse_args()

    if options.daemon:
        createDaemon(options.pidfile, options.logfile)

    logger = None
    if options.logfile:
        logger = logging.getLogger('LatestBuild')
        logger.setLevel(logging.DEBUG)
        handler = logging.FileHandler(options.logfile)
        logger.addHandler(handler)

    if options.pidfile is not None:
        fp = open(options.pidfile, "w")
        fp.write("%d\n" % os.getpid())
        fp.close()

    monitor = LatestBuildMonitor(logger=logger)
    monitor.start()


if __name__ == '__main__':
    main()


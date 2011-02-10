import logging
import os
import socket
import sys

try:
    import json
except:
    import simplejson as json

from optparse import OptionParser
from pulsebuildmonitor import PulseBuildMonitor
from threading import Thread
from webob import Request, Response, html_escape
from webob import exc

#from daemon import createDaemon

class LatestBuildMonitor(PulseBuildMonitor, Thread):
  def __init__(self, logger=None, port=8014, **kwargs):
    self.logger = logger
    self.port = port
    self.builds = {}
    PulseBuildMonitor.__init__(self, logger=self.logger, **kwargs)
    Thread.__init__(self)

  def __call__(self, environ, start_response):
    resp = Response(content_type='application/json')
    resp.status_int = 200
    resp.body = json.dumps(self.get_latest_build())

    return resp(environ, start_response)

  def onBuildComplete(self, builddata):
    if builddata['tree'] not in self.builds:
      self.builds[builddata['tree']] = {}
    if builddata['platform'] not in self.builds[builddata['tree']]:
      self.builds[builddata['tree']][builddata['platform']] = {}
    self.builds[builddata['tree']][builddata['platform']].update({builddata['buildtype']:  builddata['buildurl']})

  def onPulseMessage(self, data):
    key = data['_meta']['routing_key']
    print key

  def get_latest_build(self):
    return self.builds

  def run(self):
    from wsgiref.simple_server import make_server
    httpd = make_server('127.0.0.1', self.port, self)
    if self.logger:
      self.logger.info('Serving on http://127.0.0.1:%s' % options.port)
    elif not options.daemon:
      print 'Serving on http://127.0.0.1:%s' % options.port
    try:
      httpd.serve_forever()
    except KeyboardInterrupt:
      print '^C'

if __name__ == '__main__':
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

  monitor = LatestBuildMonitor(logger=logger,
                               port=options.port,
                               label='woo@mozilla.com|latest_build_monitor_' + socket.gethostname())
  monitor.start()
  monitor.listen()
  


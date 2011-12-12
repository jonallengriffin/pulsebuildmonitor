# ***** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# The Original Code is Pulse Build Monitor.
#    
# The Initial Developer of the Original Code is
# Mozilla foundation
# Portions created by the Initial Developer are Copyright (C) 2011
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#   Jonathan Griffin <jgriffin@mozilla.com>
#
# Alternatively, the contents of this file may be used under the terms of
# either the GNU General Public License Version 2 or later (the "GPL"), or
# the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisions above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.
#
# ***** END LICENSE BLOCK *****

import cPickle
import datetime
import httplib
import os
import re
import time
import traceback
try:
  import json
except:
  import simplejson as json
from dateutil.parser import parse
from mozillapulse import consumers
from Queue import Queue, Empty
from threading import Thread, RLock
from urlparse import urlparse

class BuildManifest(object):

  def __init__(self, logger, queue):
    self.logger = logger
    self.queue = queue

  def buildTuple(self, builddata):
    """A tuple representing a build in the build manifest.
    """

    if 'logurl' in builddata:
      return (builddata['tree'],
              builddata['os'],
              builddata['platform'],
              builddata['buildtype'],
              builddata['builddate'],
              builddata['test'],
              builddata['logurl'],
              builddata['timestamp'],
              builddata['buildername'],
              builddata['mobile'],
              builddata['talos'])

    else:
      return (builddata['tree'],
              builddata['platform'],
              builddata['buildlogurl'],
              builddata['buildtype'],
              builddata['builddate'],
              builddata['timestamp'],
              builddata['builder'],
              builddata['buildnumber'],
              builddata['mobile'],
              builddata['buildername'],
              )

  def _convert_unicode_values(self, obj):
    for key in obj:
      if isinstance(obj[key], unicode):
        obj[key] = str(obj[key])
    return obj

  def addBuild(self, builddata):
    """Add the build to the build manifest.
    """

    if self.logger:
      self.logger.info('adding %s' % repr(self.buildTuple(builddata)))
    if not isinstance(builddata, dict):
      raise Exception('wrong data type passed to addBuild: %s' % type(builddata))
    self.queue.put(self._convert_unicode_values(builddata))


class TestLogThread(Thread):

  def __init__(self, manifest, lock, log_avail_callback,
               buildlog_avail_callback=None,
               logger=None, buildmanifest=None, queue=None):
    super(TestLogThread, self).__init__()
    self.builddata = None
    self.buildmanifest = buildmanifest
    self.lock = lock
    self.log_avail_callback = log_avail_callback
    self.buildlog_avail_callback = buildlog_avail_callback
    self.logger = logger
    self.queue = queue
    self.daemon = True

  def getUrlInfo(self, url):
    """Return a (code, content_length) tuple from making an
       HTTP HEAD request for the given url.
    """

    try:
      content_length = -1
      p = urlparse(url)

      conn = httplib.HTTPConnection(p[1])
      conn.request('HEAD', p[2])
      res = conn.getresponse()
      code = res.status

      if code == 200:
        for header in res.getheaders():
          if header[0] == 'content-length':
            content_length = int(header[1])

      return (code, content_length)

    except AttributeError:
      # this can happen when we didn't get a valid url from pulse
      return (-1, -1)

    except Exception, inst:
      if self.logger:
        self.logger.exception(inst)
        self.logger.error(url)
      return (-1, -1)

  def run(self):
    self.logger.info('test log thread started')
    # loop forever
    while True:

      try:

        try:
          builddata = self.queue.get_nowait()
        except Empty:
          self.logger.info('no builds, going to sleep')
          time.sleep(30)
          self.logger.info('end sleep')
          continue
        self.logger.info('inspecting %s' % repr(builddata))

        urlfield = 'logurl' if 'logurl' in builddata else 'buildlogurl'
        if urlfield in builddata:
          code, content_length = self.getUrlInfo(str(builddata[urlfield]))
        else:
          continue

        if code == 200:
          if urlfield == 'logurl':
            self.log_avail_callback(builddata)
          elif urlfield == 'buildlogurl' and self.buildlog_avail_callback is not None:
            self.buildlog_avail_callback(builddata)

        else:
          # some HTTP error code; ignore unless we've hit the max time
          timestamp = datetime.datetime.strptime(builddata['timestamp'], '%Y%m%d%H%M%S')
          if datetime.datetime.now() - timestamp < datetime.timedelta(seconds=600):
            # XXX: log error
            self.queue.put(builddata)

      except Exception, inst:
        if self.logger:
          self.logger.exception(inst)

      time.sleep(10)

class BadPulseMessageError(Exception):

  def __init__(self, pulseMessage, error):
    self.pulseMessage = pulseMessage
    self.error = error
  def __str__(self):
    return '%s -- %s' % (json.dumps(self.pulseMessage), self.error)


class PulseBuildMonitor(object):
  talosTests = [
    '-tpan',
    '-tdhtml_nochrome',
    '-tsspider_nochrome',
    '-tsvg_nochrome',
    '-tp4m',
    '-ts',
    '-twinopen',
    '-tzoom',
  ]

  def __init__(self, label=None, tree='mozilla-central',
               manifest='builds.manifest', notify_on_logs=False,
               durable=False, platforms=None, tests=None,
               logger=None, mobile=None, includeTalos=False):
    self.label = label
    self.tree = tree
    self.platforms = platforms
    self.tests = tests
    self.durable = durable
    self.notify_on_logs = notify_on_logs
    self.manifest = os.path.abspath(manifest)
    self.logger = logger
    self.mobile = mobile

    self.lock = RLock()
    self.queue = Queue()

    if self.notify_on_logs:
      # delete any old manifest file
      if os.access(self.manifest, os.F_OK):
        os.remove(self.manifest)

      # track what files are pending in a manifest
      self.buildmanifest = BuildManifest(self.logger,
                                         self.queue)

      # create a new thread to handle watching for logs
      self.logthread = TestLogThread(self.manifest,
                                     self.lock,
                                     self.onTestLogAvailable,
                                     buildlog_avail_callback=self.onBuildLogAvailable,
                                     logger=self.logger,
                                     buildmanifest=self.buildmanifest,
                                     queue=self.queue)
      self.logthread.start()

    # setup the pulse consumer
    if not self.label:
      raise Exception('label not defined')
    self.pulse = consumers.BuildConsumer(applabel=self.label)
    self.pulse.configure(topic='#.finished',
                         callback=self.pulseMessageReceived,
                         durable=self.durable)

    if isinstance(self.tree, list):
      trees = '|'.join(self.tree)
    else:
      trees = self.tree
    self.unittestRe = re.compile(r'build\.((%s)[-|_](.*?)(-debug|-o-debug|-pgo|_pgo|_test)?[-|_](test|unittest|pgo)-(.*?))\.(\d+)\.' % trees)
    self.buildRe = re.compile(r'build\.(%s)[-|_](.*?)\.(\d+)\.' % trees)

  def purgePulseQueue(self):
    """Purge any messages from the queue.  This has no effect if you're not
       using a durable queue.
    """

    self.pulse.purge_existing_messages()

  def buildid2date(self, string):
    """Takes a buildid string and returns a python datetime and 
       seconds since epoch
    """

    date = parse(string)
    return (date, int(time.mktime(date.timetuple())))

  def listen(self):
    """Start listening for pulse messages.  This call never returns.
    """
    self.pulse.listen()

  def onBuildComplete(self, builddata):
    """Called whenever a buildbot build is finished.

       builddata is a dict with the following keys:
        tree:      mozilla-central, etc.
        branch:    the hg branch the build was made from
        builddate: the buildbot builddate in seconds since epoch format
        buildid:   the buildbot buildid
        timestamp: the datetime the pulse message was received, in
                   'YYYYMMDDHHMMSS' format
        platform:  generic platform, e.g., linux, linux64, win32, macosx64
        buildurl:  full url to the build on http://stage.mozilla.org
        buildtype: one of: debug, opt, pgo
        testsurl:  full url to the test bundle
        key:       the pulse routing_key that was sent with this message
    """
    pass

  def onBuildLogAvailable(self, builddata):
    """Called whenever a buildlog is available; same parameters as above,
       plus:
         buildlogurl: full url to the build log
    """
    pass

  def onTestComplete(self, builddata):
    """Called whenver a buildbot test is finished.  Note that
       the test's logfile is not guaranteed to be availble yet; use
       onTestLogAvailable() to receive notifications when new test logs
       are available to download.

       builddata is a dict with the following keys:
        tree:        mozilla-central, etc.
        branch:      the hg branch the build was made from
        os:          specific OS, e.g., win7, xp, fedora64, snowleopard
        platform:    generic platform, e.g., linux, linux64, win32, macosx64
        buildtype:   one of: debug, opt, pgo
        builddate:   the buildbot builddate in seconds since epoch format
        test:        the name of the test, e.g., reftest, mochitest-other
        timestamp:   the datetime the pulse message was received, in 
                     'YYYYMMDDHHMMSS' format
        testsurl:    full url to the test bundle
        logurl:      full url to the logfile on http://stage.mozilla.org
    """
    pass

  def onTestLogAvailable(self, builddata):
    """Called whenever a test log becomes available on the FTP site.  See
       onTestComplete for explanation of the builddata parameter.
    """
    pass

  def onPulseMessage(self, data):
    """Called for every pulse message that we receive; 'data' is the
       unprocessed payload from pulse.
    """
    pass

  def pulseMessageReceived(self, data, message):
    """Called whenever our pulse consumer receives a message.
    """

    # we determine if this message is of interest to us by examining
    # the routing_key
    key = data['_meta']['routing_key']

    try:
      self.onPulseMessage(data)

      # see if this message is for our tree; if not, discard it
      tree = None
      if isinstance(self.tree, list):
        for atree in self.tree:
          if atree in key:
            tree = atree
            break
      else:
        if self.tree in key:
          tree = self.tree
      if tree is None:
        message.ack()
        return

      # create a dict that holds build properties
      builddata = { 
                    'key': key,
                    'buildid': None,
                    'platform': None,
                    'builddate': None,
                    'buildurl': None,
                    'branch': None,
                    'testsurl': None,
                    'buildername': None,
                    'tree': tree,
                    'timestamp': datetime.datetime.now().strftime('%Y%m%d%H%M%S')
                  }

      if 'mob' in key:
        builddata['mobile'] = True
      else:
        builddata['mobile'] = False

      stage_platform = None
      try:
        # scan the payload properties for items of interest
        for property in data['payload']['build']['properties']:

          # look for buildid
          if property[0] == 'buildid':
            builddata['buildid'] = property[1]
            date,builddata['builddate'] = self.buildid2date(property[1])

          # look for platform
          elif property[0] == 'platform':
            builddata['platform'] = property[1]
            if '-debug' in builddata['platform']:
              builddata['platform'] = builddata['platform'][0:builddata['platform'].find('-debug')]

          # look for build url
          elif property[0] in ['packageUrl', 'build_url', 'fileURL']:
            builddata['buildurl'] = property[1]
            # ignore xulrunner builds
            if 'xulrunner' in builddata['buildurl']:
              message.ack()
              return

          # look for tests url
          elif property[0] == 'testsUrl':
            builddata['testsurl'] = property[1]

          # look for hg branch
          elif property[0] == 'branch':
            builddata['branch'] = property[1]

          # look for buildername
          elif property[0] == 'buildername':
            builddata['buildername'] = property[1]

          # look for stage_platform
          elif property[0] == 'stage_platform':
            stage_platform = property[1]
            if '-pgo' in stage_platform:
              # we don't want any '-pgo' suffix here
              stage_platform = stage_platform[0:stage_platform.find('-pgo')]

      except Exception, inst:
        raise BadPulseMessageError(data, traceback.format_exc(2))

      # see if this message is from mobile
      if (self.mobile is not None and self.mobile != builddata['mobile']):
        message.ack()
        return

      # see if this message is for one of our platforms
      if (self.platforms is not None and builddata['platform'] not in self.platforms and \
                                         stage_platform not in self.platforms):
        message.ack()
        return

      # see if this message is for a unittest
      match = self.unittestRe.match(key)
      if match:
        builddata['os'] = match.groups()[2]
        builddata['talos'] = 'talos' in builddata['buildername'] #bool(len(filter(lambda x: x in key, self.talosTests)))
        if stage_platform and (builddata['talos'] or 'android' in builddata['os']):
          builddata['platform'] = stage_platform
        # store some more metadata in the builddata dict
        debug_or_pgo = match.groups()[3]
        if debug_or_pgo:
          if 'debug' in debug_or_pgo:
            builddata['buildtype'] = 'debug'
          elif 'pgo' in debug_or_pgo:
            builddata['buildtype'] = 'pgo'
        else:
          builddata['buildtype'] = 'opt'
        # normally this could be 'test' or 'unittest', but sometimes it's 'pgo'! :(
        extra = match.groups()[4]
        if 'pgo' in extra:
            builddata['buildtype'] = 'pgo'
        builddata['test'] = match.groups()[5]
        builddata['buildnumber'] = match.groups()[6]
        builddata['logurl'] = None
        if builddata['buildurl']:
          builddata['logurl'] = '%s/%s-build%s.txt.gz' % \
              (os.path.dirname(builddata['buildurl']),
               match.groups()[0], builddata['buildnumber'])

        # see if this message is for one of our test types
        if self.tests is not None and builddata['test'] not in self.tests:
          message.ack()
          return

        # call the onTestComplete handler
        self.onTestComplete(builddata)
        if self.notify_on_logs:
          self.buildmanifest.addBuild(builddata)

      else:
        # see if this message is for a build
        match = self.buildRe.match(key)
        if match:
          # call the onBuildComplete handler
          if 'debug' in key:
            builddata['buildtype'] = 'debug'
          elif 'pgo' in key:
            builddata['buildtype'] = 'pgo'
          else:
            builddata['buildtype'] = 'opt'
          builddata['buildnumber'] = match.group(3)
          builddata['builder'] = match.group(2)
          builddata['buildlogurl'] = None
          if builddata['buildurl']:
            builddata['buildlogurl'] = '%s/%s-%s-build%s.txt.gz' % \
                (os.path.dirname(builddata['buildurl']),
                 builddata['tree'],
                 match.group(2), builddata['buildnumber'])
          self.onBuildComplete(builddata)

          if self.notify_on_logs:
            self.buildmanifest.addBuild(builddata)

        else:
          print 'unexpected message received: %s' % key

      # acknowledge the message, to remove it from the queue
      message.ack()

    except BadPulseMessageError, inst:
      message.ack()
      if self.logger:
        self.logger.exception(inst)
      traceback.print_exc()

    except Exception, inst:
      if self.logger:
        message.ack()
        self.logger.exception(inst)
        traceback.print_exc()
      else:
        raise


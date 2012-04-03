# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.


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


class BadPulseMessageError(Exception):

  def __init__(self, key):
    self.key = key
  def __str__(self):
    return self.key


class PulseBuildMonitor(object):

  unittestsRe = re.compile(r'(unittest|talos).(.*?)\.(.*?)\.(.*?)\.(.*?)\.(.*?)\.(.*?)\.(.*)')
  buildsRe = re.compile(r'build.(.*?)\.(.*?)\.(.*?)\.(.*)')

  def __init__(self, label=None, trees='mozilla-central',
               durable=False, platforms=None, tests=None,
               buildtypes=None, products=None, buildtags=None,
               logger=None, talos=False, builds=False,
               unittests=False):
    self.label = label
    self.trees = trees
    self.platforms = platforms
    self.tests = tests
    self.products = products
    self.buildtypes = buildtypes
    self.durable = durable
    self.logger = logger
    self.talos = talos
    self.builds = builds
    self.buildtags = buildtags
    self.unittests = unittests

    assert(self.talos or self.builds or self.unittests)

    # setup the pulse consumer
    if not self.label:
      raise Exception('label not defined')
    self.pulse = consumers.NormalizedBuildConsumer(applabel=self.label)
    topics = []
    if self.talos:
        topics.append("talos.#")
    if self.builds:
        topics.append("build.#")
    if self.unittests:
        topics.append("unittest.#")
    self.pulse.configure(topic=topics,
                         callback=self.pulse_message_received,
                         durable=self.durable)

    if isinstance(self.trees, basestring):
      self.trees = [self.trees]

  def purge_pulse_queue(self):
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

  def on_build_complete(self, builddata):
    """Called whenever a buildbot build is finished. See README.txt
       for an explanation of builddata.
    """
    pass

  onBuildComplete = on_build_complete
  onBuildLogAvailable = on_build_complete

  def on_test_complete(self, builddata):
    """Called whenever a test log becomes available on the FTP site.  See
       README.txt for explanation of builddata.
    """
    pass

  onTestLogAvailable = on_test_complete
  onTestComplete = on_test_complete

  def on_pulse_message(self, data):
    """Called for every pulse message that we receive; 'data' is the
       unprocessed payload from pulse.
    """
    pass

  onPulseMessage = on_pulse_message

  def pulse_message_received(self, data, message):
    """Called whenever our pulse consumer receives a message.
    """

    # acknowledge the message, to remove it from the queue
    message.ack()

    # we determine if this message is of interest to us by examining
    # the routing_key
    key = data['_meta']['routing_key']

    try:
      self.on_pulse_message(data)

      if key.startswith('unittest') or key.startswith('talos'):
        if self.unittests or self.talos:
          m = self.unittestsRe.match(key)
          if not m:
            raise BadPulseMessageError(key)
          talos = 'talos' in m.group(1)
          tree = m.group(2)
          platform = m.group(3)
          os = m.group(4)
          buildtype = m.group(5)
          test = m.group(6)
          product = m.group(7)
          builder = m.group(8)

          if (talos and not self.talos) or (not talos and not self.unittests):
            return

          if self.trees and tree not in self.trees:
            return
          if self.platforms and platform not in self.platforms:
            return
          if self.buildtypes and buildtype not in self.buildtypes:
            return
          if self.tests and test not in self.tests:
            return
          if self.products and product not in self.products:
            return

          self.on_test_complete(data['payload'])

      elif key.startswith('build'):
        if self.builds:
          m = self.buildsRe.match(key)
          if not m:
            raise BadPulseMessageError(key)
          tree = m.group(1)
          platform = m.group(2)
          buildtype = m.group(3)
          extra = m.group(4)

          if self.trees and tree not in self.trees:
            return
          if self.platforms and platform not in self.platforms:
            return
          if self.buildtypes and buildtype not in self.buildtypes:
            return
          if self.products and data['payload']['product'] not in self.products:
            return
          if self.buildtags:
            if isinstance(self.buildtags[0], basestring):
              # a list of tags which must all be present
              tags = [x for x in self.buildtags if x in data['payload']['tags']]
              if len(tags) != len(self.buildtags):
                return
            elif isinstance(self.buildtags[0], list):
              # a nested list of tags, any one of which must all be present
              tagsMatch = False
              for taglist in self.buildtags:
                tags = [x for x in taglist if x in data['payload']['tags']]
                if len(tags) == len(self.buildtags):
                  tagsMatch = True
                  break
              if not tagsMatch:
                return
            else:
              raise Exception('buildtags must be a list of strings or a list of lists')

          self.on_build_complete(data['payload'])

      else:
        raise BadPulseMessageError(key)

    except Exception, inst:
      if self.logger:
        self.logger.exception(inst)
        traceback.print_exc()
      else:
        raise


# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.


import logging
import random
import socket
import string
import threading

from pulsebuildmonitor import PulseBuildMonitor


class FactoryBuildMonitor(PulseBuildMonitor):

    def __init__(self, buildCallback=None, testCallback=None,
                 pulseCallback=None, tests=None, products=None,
                 platforms=None, trees=None, label=None, mobile=False,
                 logger=None, buildtypes=None, talos=False,
                 buildTags=None, buildtags=None):
        self.platforms = platforms
        self.trees = trees
        self.mobile = mobile
        self.label = label
        self.buildtypes = buildtypes
        self.buildtags = buildtags
        self.buildCallback = buildCallback
        self.testCallback = testCallback
        self.pulseCallback = pulseCallback
        self.monitorThread = None
        self.tests = tests
        self.talos = talos
        self.products = products

        if not self.label:
            # generate a random label
            self.label = '%s_%s' % (
                ''.join(random.choice(string.letters) for i in xrange(12)),
                socket.gethostname())

        if isinstance(logger, basestring):
            # if 'logger' is a string, create a logging handler for it
            self.logger = logging.getLogger(logger)
            self.logger.setLevel(logging.DEBUG)
            handler = logging.FileHandler(logger)
            self.logger.addHandler(handler)
        else:
            # otherwise assume it is already a logging instance, or None
            self.logger = logger

        PulseBuildMonitor.__init__(self,
                                   trees=self.trees,
                                   label=self.label,
                                   logger=self.logger,
                                   buildtypes=self.buildtypes,
                                   platforms=self.platforms,
                                   talos=self.talos,
                                   tests=self.tests,
                                   buildtags=self.buildtags,
                                   products=self.products,
                                   builds=buildCallback is not None,
                                   unittests=testCallback is not None)

    def join(self):
        assert(self.monitorThread)
        self.monitorThread.join()

    def start(self):
        self.monitorThread = threading.Thread(target=self.listen)
        self.monitorThread.daemon = True
        self.monitorThread.start()

    def start_callback_thread(self, callback, *args):
        callback(*args)

    def on_pulse_message(self, data):
        if self.pulseCallback:
            callbackThread = threading.Thread(target=self.start_callback_thread, args=(self.pulseCallback, data))
            callbackThread.daemon = True
            callbackThread.start()

    def on_build_complete(self, builddata):
        callbackThread = threading.Thread(target=self.start_callback_thread, args=(self.buildCallback, builddata))
        callbackThread.daemon = True
        callbackThread.start()

    def on_test_complete(self, builddata):
        callbackThread = threading.Thread(target=self.start_callback_thread, args=(self.testCallback, builddata))
        callbackThread.daemon = True
        callbackThread.start()

def start_pulse_monitor(buildCallback=None, testCallback=None, pulseCallback=None, **kwargs):

    monitor = FactoryBuildMonitor(buildCallback=buildCallback,
                                  testCallback=testCallback,
                                  pulseCallback=pulseCallback,
                                  **kwargs)
    monitor.start()
    return monitor


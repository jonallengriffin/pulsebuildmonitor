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
# The Initial Developer of the Original Code is Mozilla Foundation.
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

import logging
import random
import socket
import string
import threading

from pulsebuildmonitor import PulseBuildMonitor


class FactoryBuildMonitor(PulseBuildMonitor):

    def __init__(self, buildCallback=None, testCallback=None,
                 pulseCallback=None,
                 platform=None, tree=None, label=None, mobile=False,
                 logger=None, buildtype=None, includeTalos=False):
        self.platform = platform
        self.tree = tree if tree else ['mozilla-central']
        self.mobile = mobile
        self.label = label
        self.buildtype = buildtype
        self.buildCallback = buildCallback
        self.testCallback = testCallback
        self.pulseCallback = pulseCallback
        self.monitorThread = None
        self.includeTalos = includeTalos

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
                                   tree=self.tree,
                                   notify_on_logs=self.testCallback is not None,
                                   label=self.label,
                                   mobile=self.mobile,
                                   logger=self.logger,
                                   includeTalos = self.includeTalos)

    def join(self):
        assert(self.monitorThread)
        self.monitorThread.join()

    def start(self):
        self.monitorThread = threading.Thread(target=self.listen)
        self.monitorThread.daemon = True
        self.monitorThread.start()

    def start_callback_thread(self, callback, *args):
        callback(*args)

    def onPulseMessage(self, data):
        if self.pulseCallback:
            callbackThread = threading.Thread(target=self.start_callback_thread, args=(self.pulseCallback, data))
            callbackThread.daemon = True
            callbackThread.start()

    def onBuildComplete(self, builddata):
        if (self.buildCallback and 
                (not self.platform or
                    ('platform' in builddata and builddata['platform'] in self.platform)) and
                (not self.buildtype or
                    ('buildtype' in builddata and builddata['buildtype'] == self.buildtype))):
            callbackThread = threading.Thread(target=self.start_callback_thread, args=(self.buildCallback, builddata))
            callbackThread.daemon = True
            callbackThread.start()

    def onTestLogAvailable(self, builddata):

        if (self.testCallback and
                (not self.platform or
                    ('platform' in builddata and builddata['platform'] in self.platform)) and
                (not self.buildtype or
                    ('buildtype' in builddata and builddata['buildtype'] in self.buildtype))):
            print 'calling callback'
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


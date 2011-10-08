Pulse Build Monitor
===================

Pulse is mozilla's internal event system, see http://pulse.mozilla.org.
The pulse build monitor is a tool that consumes pulse events from
buildbot, and notifies callbacks when messages of interest are received.


Installation
============

Pulse build monitor requires the mozillapulse package to be installed.

  hg clone http://hg.mozilla.org/users/clegnitto_mozilla.com/mozillapulse/
  cd mozillapulse
  python setup.py install

After that, you can download and install the pulse build monitor package.

  hg clone http://hg.mozilla.org/automation/pulsebuildmonitor/
  cd pulsebuildmonitor
  python setup.py install


Usage
=====

To use the monitor, you just call a single convenience function:

  from pulsebuildmonitor import start_pulse_monitor

  monitor = start_pulse_monitor(buildCallback=None,
                                testCallback=None,
                                pulseCallback=None,
                                label=None,
                                tree=['mozilla-central'],
                                platform=None,
                                mobile=False,
                                buildtype=None,
                                logger=None,
                                includeTalos=False)

This function returns right away; all of the activity it initiated is
executed on separate threads.


Parameters
==========

  buildCallback - a function to call when a buildbot message is received
    that indicates a build is finished.  This callback is called with
    a dict with the following properties:
      * buildurl: the full url of the build
      * testsurl: the full url of tests.zip corresponding to the build
      * tree:      mozilla-central, etc.
      * branch:    the hg branch the build was made from
      * builddate: the buildbot builddate in seconds since epoch format
      * buildid:   the buildbot buildid
      * timestamp: the datetime the pulse message was received, in
                   'YYYYMMDDHHMMSS' format
      * platform:  generic platform, e.g., linux, linux64, win32, macosx64
      * buildtype: one of: debug, opt
      * key:       the pulse routing_key that was sent with this message

  testCallback - a function to call when a buildbot messages is received
    that indicates a unit test has been finished.  This callback is called
    with a dict with the following properties:
      * tree:        mozilla-central, etc.
      * branch:      the hg branch the build was made from
      * os:          specific OS, e.g., win7, xp, fedora64, snowleopard
      * platform:    generic platform, e.g., linux, linux64, win32, macosx64
      * buildtype:   one of: debug, opt
      * builddate:   the buildbot builddate in seconds since epoch format
      * test:        the name of the test, e.g., reftest, mochitest-other
      * timestamp:   the datetime the pulse message was received, in 
                     'YYYYMMDDHHMMSS' format
      * logurl:      full url to the logfile on http://stage.mozilla.org
      * mobile:      true if the message relates to a mobile test
      * talos:       true if the message related to a talos test

  pulseCallback - a function to call when any buildbot message is received.
    The messages sent to this callback are not filtered by the platform,
    mobile, and buildtype parameters.  The function is called with one
    parameter, a large dict that contains the pulse message.  The structure
    of this dict varies depending on message type.  This can be useful
    if you want to provide your own message filtering.

  label - a unique string to identify this pulse consumer.  If None is
    passed, a random string will be generated.

  tree - a list of trees to use to filter messages passed to 
    buildCallback and testCallback.  If not specified, defaults
    to ['mozilla-central'].

  platform - one of: linux, linux64, win32, win64, macosx, macosx64,
    android, or None.  If specified, will be used to filter messages
    passed to buildCallback and testCallback.

  mobile - if True, only pass messages relting to mobile builds to
    buildCallback and testCallback.  If False, exclude all mobile
    messages.

  includeTalos - if True, pass messages relating to both talos and
    unittests to testCallback.  If False (the default), exclude all
    talos messages.

  buildtype - either 'opt' or 'debug'.  If specified, used to filter
    messages passed to buildCallback and testCallback.

  logger - either a string or a logging.logger instance.  If a string,
    a logging.logger instance will be created using the given string
    as a filename.


Threading considerations
========================

As mentioned above, start_pulse_monitor will return immediately; all
the activity it initiates is handled on separate threads.  If your main
thread has nothing to do while waiting for pulse messages, it may call
the join() method on the monitor object returned by start_pulse_monitor:

  monitor = start_pulse_monitor(args...)
  monitor.join()

The call to join will never return, unless the program is terminated.
Even when this is done, the pulse message callbacks are always invoked
using separate threads.

Because each call to a callback is made on a separate thread, if they
access any shared resources, they should make use of locks (such as
threading.RLock) or other synchronization mechanisms to prevent
deadlocks or other problems.

Any exceptions which occur when executing the callbacks will be logged
(if you specified the logger parameter), and will be print to stdout.
However, since they are run on separate threads, they will not stop
execution of the monitor thread itself.  Thus, these exceptions will
not cause your program to terminate; you'll need to consult the log
(or watch stdout) to determine if your callbacks are raising exceptions
or not.

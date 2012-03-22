Pulse Build Monitor
===================

Pulse is mozilla's internal event system, see http://pulse.mozilla.org.
The pulse build monitor is a tool that consumes pulse events from
buildbot, and notifies callbacks when messages of interest are received.


Installation
============

Download and install the pulse build monitor package.

  hg clone http://hg.mozilla.org/automation/pulsebuildmonitor/
  cd pulsebuildmonitor
  python setup.py install

Or, more simply:

  easy_install pulsebuildmonitor


Usage
=====

To use the monitor, you just call a single convenience function:

  from pulsebuildmonitor import start_pulse_monitor

  monitor = start_pulse_monitor(buildCallback=None,
                                testCallback=None,
                                pulseCallback=None,
                                label=None,
                                trees=['mozilla-central'],
                                platforms=None,
                                products=None,
                                buildtypes=None,
                                tests=None,
                                buildtags=None
                                logger=None,
                                talos=False)

This function returns right away; all of the activity it initiates is
executed on separate threads.


Parameters
==========

  buildCallback - a function to call when a buildbot message is received
    that indicates a build is finished.  This callback is called with
    a dict with the following properties:
      * buildtype:   one of: debug, opt, pgo
      * product:     the product, may be firefox, mobile, xulrunner, None
                     or some other value
      * revision:    the hg commit that the build was built from
      * builddate:   the buildbot builddate in seconds since epoch format
      * buildername: the buildbot buildername in long format, e.g.,
                     "Android Tegra 250 try opt test mochitest-1"
      * timestamp:   the datetime the pulse message was received, in 
                     'YYYYMMDDHHMMSS' format
      * tree:        mozilla-central, etc.  Only the repo name is included
                     here, not the relative path, so this value might
                     be mozilla-beta, but not releases/mozilla-beta.
      * platform:    generic platform, e.g., linux, linux64, win32, macosx64
      * buildurl:    the full url to the build used to run the test
      * testsurl:    the full url to the test package for this build
      * key:         the pulse key for the original pulse message
      * release:     for release builds, the name of the release
      * tags:        a list of zero or more tags for this build; see
                     https://github.com/mozilla/pulsetranslator/blob/master/pulsetranslator/messageparams.py
                     for a list of possible values.

  testCallback - a function to call when a buildbot messages is received
    that indicates a unit test has been finished.  This callback is called
    with a dict with the following properties:
      * buildtype:   one of: debug, opt, pgo
      * product:     the product, may be firefox, mobile, xulrunner, None
                     or some other value
      * revision:    the hg commit that the build was built from
      * builddate:   the buildbot builddate in seconds since epoch format
      * buildername: the buildbot buildername in long format, e.g.,
                     "Android Tegra 250 try opt test mochitest-1"
      * timestamp:   the datetime the pulse message was received, in 
                     'YYYYMMDDHHMMSS' format
      * talos:       true if the message is related to a talos test
      * tree:        mozilla-central, etc.  Only the repo name is included
                     here, not the relative path, so this value might
                     be mozilla-beta, but not releases/mozilla-beta.
      * buildnumber: the buildbot build number
      * os:          specific OS, e.g., win7, xp, fedora64, snowleopard
      * platform:    generic platform, e.g., linux, linux64, win32, macosx64
      * buildurl:    the full url to the build used to run the test
      * logurl:      full url to the logfile on http://stage.mozilla.org
      * key:         the pulse key for the original pulse message
      * release:     for release builds, the name of the release
      * test:        the name of the test, e.g., reftest, mochitest-other

  pulseCallback - a function to call when any buildbot message is received.
    The messages sent to this callback are not filtered.  The function
    is called with one parameter, a large dict that contains the pulse
    message.  The structure of this dict varies depending on message type.
    This can be useful if you want to provide your own message filtering.

  label - a unique string to identify this pulse consumer.  If None is
    passed, a random string will be generated.

  trees - a list of trees to use to filter messages passed to 
    buildCallback and testCallback.  If not specified, defaults
    to ['mozilla-central'].

  platforms - a list of one of more of: linux, linuxqt, linux-rpm, linux64,
    linux64-rpm, win32, win64, macosx, macosx64, android, android-xul.
    If specified, will be used to filter messages passed to
    buildCallback and testCallback.

  products = a list of one or more prodcuts to filter messages with;
    possible products include firefox, mobile, xulrunner, and None
    for buildbot messages that don't contain product information.

  talos - if True, pass messages relating to both talos and
    unittests to testCallback.  If False (the default), exclude all
    talos messages.

  tests - a list of test names (e.g., 'reftest') that is used to filter
    talos and unittest messages passed to testCallback.  The test names
    are defined by buildbot and are subject to change without notice.

  buildtype - a list of one or more of: debug, opt, pgo. If specified,
    used to filter messages passed to buildCallback and testCallback.

  buildtags - a list of build tags which are used to filter builds
    passed to buildCallback.  The list can either be a list of strings,
    in which case all strings must match build tags in order for the
    message to be passed to buildCallback, or it can be a list of lists of
    strings, in which all strings in any of the inner lists much match
    build tags in order for the message to pass the filter.  Build tags
    are arbitrary tags that can help distginuish between different builds;
    possible values are defined at 
    https://github.com/mozilla/pulsetranslator/blob/master/pulsetranslator/messageparams.py#L53

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


Upgrading from earlier versions
===============================

There are some minor API changes to pulsebuildmonitor 0.6.  When creating
a pulsebuildmonitor, some of the parameters have changed:

* 'buildtype' is now 'buildtypes', and is a list
* 'tree' is now 'trees', and is a list (previously it was a list or a string)
* 'mobile' has been removed (you can filter on the mobile product using products=['mobile'])
* 'includeTalos' is now just 'talos'
* there are some new arguments, see the 'Usage' section above

Additionally, pulsebuildmonitor now requires mozillapulse >= 0.6.  You can
install the latest using 'easy_install mozillapulse', or grab a copy from
http://hg.mozilla.org/automation/mozillapulse/

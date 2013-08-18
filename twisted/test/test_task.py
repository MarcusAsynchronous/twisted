# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.python.compat import set

from twisted.trial import unittest

from twisted.internet import interfaces, task, reactor, defer, error

# Be compatible with any jerks who used our private stuff
Clock = task.Clock

from twisted.python import failure


class TestableLoopingCall(task.LoopingCall):
    def __init__(self, clock, *a, **kw):
        super(TestableLoopingCall, self).__init__(*a, **kw)
        self.clock = clock



class TestException(Exception):
    pass



class ClockTestCase(unittest.TestCase):
    """
    Test the non-wallclock based clock implementation.
    """
    def testSeconds(self):
        """
        Test that the L{seconds} method of the fake clock returns fake time.
        """
        c = task.Clock()
        self.assertEqual(c.seconds(), 0)


    def testCallLater(self):
        """
        Test that calls can be scheduled for later with the fake clock and
        hands back an L{IDelayedCall}.
        """
        c = task.Clock()
        call = c.callLater(1, lambda a, b: None, 1, b=2)
        self.failUnless(interfaces.IDelayedCall.providedBy(call))
        self.assertEqual(call.getTime(), 1)
        self.failUnless(call.active())


    def testCallLaterCancelled(self):
        """
        Test that calls can be cancelled.
        """
        c = task.Clock()
        call = c.callLater(1, lambda a, b: None, 1, b=2)
        call.cancel()
        self.failIf(call.active())


    def test_callLaterOrdering(self):
        """
        Test that the DelayedCall returned is not one previously
        created.
        """
        c = task.Clock()
        call1 = c.callLater(10, lambda a, b: None, 1, b=2)
        call2 = c.callLater(1, lambda a, b: None, 3, b=4)
        self.failIf(call1 is call2)


    def testAdvance(self):
        """
        Test that advancing the clock will fire some calls.
        """
        events = []
        c = task.Clock()
        call = c.callLater(2, lambda: events.append(None))
        c.advance(1)
        self.assertEqual(events, [])
        c.advance(1)
        self.assertEqual(events, [None])
        self.failIf(call.active())


    def testAdvanceCancel(self):
        """
        Test attemping to cancel the call in a callback.

        AlreadyCalled should be raised, not for example a ValueError from
        removing the call from Clock.calls. This requires call.called to be
        set before the callback is called.
        """
        c = task.Clock()
        def cb():
            self.assertRaises(error.AlreadyCalled, call.cancel)
        call = c.callLater(1, cb)
        c.advance(1)


    def testCallLaterDelayed(self):
        """
        Test that calls can be delayed.
        """
        events = []
        c = task.Clock()
        call = c.callLater(1, lambda a, b: events.append((a, b)), 1, b=2)
        call.delay(1)
        self.assertEqual(call.getTime(), 2)
        c.advance(1.5)
        self.assertEqual(events, [])
        c.advance(1.0)
        self.assertEqual(events, [(1, 2)])


    def testCallLaterResetLater(self):
        """
        Test that calls can have their time reset to a later time.
        """
        events = []
        c = task.Clock()
        call = c.callLater(2, lambda a, b: events.append((a, b)), 1, b=2)
        c.advance(1)
        call.reset(3)
        self.assertEqual(call.getTime(), 4)
        c.advance(2)
        self.assertEqual(events, [])
        c.advance(1)
        self.assertEqual(events, [(1, 2)])


    def testCallLaterResetSooner(self):
        """
        Test that calls can have their time reset to an earlier time.
        """
        events = []
        c = task.Clock()
        call = c.callLater(4, lambda a, b: events.append((a, b)), 1, b=2)
        call.reset(3)
        self.assertEqual(call.getTime(), 3)
        c.advance(3)
        self.assertEqual(events, [(1, 2)])


    def test_getDelayedCalls(self):
        """
        Test that we can get a list of all delayed calls
        """
        c = task.Clock()
        call = c.callLater(1, lambda x: None)
        call2 = c.callLater(2, lambda x: None)

        calls = c.getDelayedCalls()

        self.assertEqual(set([call, call2]), set(calls))


    def test_getDelayedCallsEmpty(self):
        """
        Test that we get an empty list from getDelayedCalls on a newly
        constructed Clock.
        """
        c = task.Clock()
        self.assertEqual(c.getDelayedCalls(), [])


    def test_providesIReactorTime(self):
        c = task.Clock()
        self.failUnless(interfaces.IReactorTime.providedBy(c),
                        "Clock does not provide IReactorTime")


    def test_callLaterKeepsCallsOrdered(self):
        """
        The order of calls scheduled by L{task.Clock.callLater} is honored when
        adding a new call via calling L{task.Clock.callLater} again.

        For example, if L{task.Clock.callLater} is invoked with a callable "A"
        and a time t0, and then the L{IDelayedCall} which results from that is
        C{reset} to a later time t2 which is greater than t0, and I{then}
        L{task.Clock.callLater} is invoked again with a callable "B", and time
        t1 which is less than t2 but greater than t0, "B" will be invoked before
        "A".
        """
        result = []
        expected = [('b', 2.0), ('a', 3.0)]
        clock = task.Clock()
        logtime = lambda n: result.append((n, clock.seconds()))

        call_a = clock.callLater(1.0, logtime, "a")
        call_a.reset(3.0)
        clock.callLater(2.0, logtime, "b")

        clock.pump([1]*3)
        self.assertEqual(result, expected)


    def test_callLaterResetKeepsCallsOrdered(self):
        """
        The order of calls scheduled by L{task.Clock.callLater} is honored when
        re-scheduling an existing call via L{IDelayedCall.reset} on the result
        of a previous call to C{callLater}.

        For example, if L{task.Clock.callLater} is invoked with a callable "A"
        and a time t0, and then L{task.Clock.callLater} is invoked again with a
        callable "B", and time t1 greater than t0, and finally the
        L{IDelayedCall} for "A" is C{reset} to a later time, t2, which is
        greater than t1, "B" will be invoked before "A".
        """
        result = []
        expected = [('b', 2.0), ('a', 3.0)]
        clock = task.Clock()
        logtime = lambda n: result.append((n, clock.seconds()))

        call_a = clock.callLater(1.0, logtime, "a")
        clock.callLater(2.0, logtime, "b")
        call_a.reset(3.0)

        clock.pump([1]*3)
        self.assertEqual(result, expected)


    def test_callLaterResetInsideCallKeepsCallsOrdered(self):
        """
        The order of calls scheduled by L{task.Clock.callLater} is honored when
        re-scheduling an existing call via L{IDelayedCall.reset} on the result
        of a previous call to C{callLater}, even when that call to C{reset}
        occurs within the callable scheduled by C{callLater} itself.
        """
        result = []
        expected = [('c', 3.0), ('b', 4.0)]
        clock = task.Clock()
        logtime = lambda n: result.append((n, clock.seconds()))

        call_b = clock.callLater(2.0, logtime, "b")
        def a():
            call_b.reset(3.0)

        clock.callLater(1.0, a)
        clock.callLater(3.0, logtime, "c")

        clock.pump([0.5] * 10)
        self.assertEqual(result, expected)



class LoopTestCase(unittest.TestCase):
    """
    Tests for L{task.LoopingCall} based on a fake L{IReactorTime}
    implementation.
    """
    def test_defaultClock(self):
        """
        L{LoopingCall}'s default clock should be the reactor.
        """
        call = task.LoopingCall(lambda: None)
        self.assertEqual(call.clock, reactor)


    def test_callbackTimeSkips(self):
        """
        When more time than the defined interval passes during the execution
        of a callback, L{LoopingCall} should schedule the next call for the
        next interval which is still in the future.
        """
        times = []
        callDuration = None
        clock = task.Clock()
        def aCallback():
            times.append(clock.seconds())
            clock.advance(callDuration)
        call = task.LoopingCall(aCallback)
        call.clock = clock

        # Start a LoopingCall with a 0.5 second increment, and immediately call
        # the callable.
        callDuration = 2
        call.start(0.5)

        # Verify that the callable was called, and since it was immediate, with
        # no skips.
        self.assertEqual(times, [0])

        # The callback should have advanced the clock by the callDuration.
        self.assertEqual(clock.seconds(), callDuration)

        # An iteration should have occurred at 2, but since 2 is the present
        # and not the future, it is skipped.

        clock.advance(0)
        self.assertEqual(times, [0])

        # 2.5 is in the future, and is not skipped.
        callDuration = 1
        clock.advance(0.5)
        self.assertEqual(times, [0, 2.5])
        self.assertEqual(clock.seconds(), 3.5)

        # Another iteration should have occurred, but it is again the
        # present and not the future, so it is skipped as well.
        clock.advance(0)
        self.assertEqual(times, [0, 2.5])

        # 4 is in the future, and is not skipped.
        callDuration = 0
        clock.advance(0.5)
        self.assertEqual(times, [0, 2.5, 4])
        self.assertEqual(clock.seconds(), 4)


    def test_reactorTimeSkips(self):
        """
        When more time than the defined interval passes between when
        L{LoopingCall} schedules itself to run again and when it actually
        runs again, it should schedule the next call for the next interval
        which is still in the future.
        """
        times = []
        clock = task.Clock()
        def aCallback():
            times.append(clock.seconds())

        # Start a LoopingCall that tracks the time passed, with a 0.5 second
        # increment.
        call = task.LoopingCall(aCallback)
        call.clock = clock
        call.start(0.5)

        # Initially, no time should have passed!
        self.assertEqual(times, [0])

        # Advance the clock by 2 seconds (2 seconds should have passed)
        clock.advance(2)
        self.assertEqual(times, [0, 2])

        # Advance the clock by 1 second (3 total should have passed)
        clock.advance(1)
        self.assertEqual(times, [0, 2, 3])

        # Advance the clock by 0 seconds (this should have no effect!)
        clock.advance(0)
        self.assertEqual(times, [0, 2, 3])


    def test_reactorTimeCountSkips(self):
        """
        When L{LoopingCall} schedules itself to run again, if more than the
        specified interval has passed, it should schedule the next call for the
        next interval which is still in the future. If it was created
        using L{LoopingCall.withCount}, a positional argument will be
        inserted at the beginning of the argument list, indicating the number
        of calls that should have been made.
        """
        times = []
        clock = task.Clock()
        def aCallback(numCalls):
            times.append((clock.seconds(), numCalls))

        # Start a LoopingCall that tracks the time passed, and the number of
        # skips, with a 0.5 second increment.
        call = task.LoopingCall.withCount(aCallback)
        call.clock = clock
        INTERVAL = 0.5
        REALISTIC_DELAY = 0.01
        call.start(INTERVAL)

        # Initially, no seconds should have passed, and one calls should have
        # been made.
        self.assertEqual(times, [(0, 1)])

        # After the interval (plus a small delay, to account for the time that
        # the reactor takes to wake up and process the LoopingCall), we should
        # still have only made one call.
        clock.advance(INTERVAL + REALISTIC_DELAY)
        self.assertEqual(times, [(0, 1), (INTERVAL + REALISTIC_DELAY, 1)])

        # After advancing the clock by three intervals (plus a small delay to
        # account for the reactor), we should have skipped two calls; one less
        # than the number of intervals which have completely elapsed. Along
        # with the call we did actually make, the final number of calls is 3.
        clock.advance((3 * INTERVAL) + REALISTIC_DELAY)
        self.assertEqual(times,
                         [(0, 1), (INTERVAL + REALISTIC_DELAY, 1),
                          ((4 * INTERVAL) + (2 * REALISTIC_DELAY), 3)])

        # Advancing the clock by 0 seconds should not cause any changes!
        clock.advance(0)
        self.assertEqual(times,
                         [(0, 1), (INTERVAL + REALISTIC_DELAY, 1),
                          ((4 * INTERVAL) + (2 * REALISTIC_DELAY), 3)])


    def test_countLengthyIntervalCounts(self):
        """
        L{LoopingCall.withCount} counts only calls that were expected to be
        made.  So, if more than one, but less than two intervals pass between
        invocations, it won't increase the count above 1.  For example, a
        L{LoopingCall} with interval T expects to be invoked at T, 2T, 3T, etc.
        However, the reactor takes some time to get around to calling it, so in
        practice it will be called at T+something, 2T+something, 3T+something;
        and due to other things going on in the reactor, "something" is
        variable.  It won't increase the count unless "something" is greater
        than T.  So if the L{LoopingCall} is invoked at T, 2.75T, and 3T,
        the count has not increased, even though the distance between
        invocation 1 and invocation 2 is 1.75T.
        """
        times = []
        clock = task.Clock()
        def aCallback(count):
            times.append((clock.seconds(), count))

        # Start a LoopingCall that tracks the time passed, and the number of
        # calls, with a 0.5 second increment.
        call = task.LoopingCall.withCount(aCallback)
        call.clock = clock
        INTERVAL = 0.5
        REALISTIC_DELAY = 0.01
        call.start(INTERVAL)
        self.assertEqual(times.pop(), (0, 1))

        # About one interval... So far, so good
        clock.advance(INTERVAL + REALISTIC_DELAY)
        self.assertEqual(times.pop(), (INTERVAL + REALISTIC_DELAY, 1))

        # Oh no, something delayed us for a while.
        clock.advance(INTERVAL * 1.75)
        self.assertEqual(times.pop(), ((2.75 * INTERVAL) + REALISTIC_DELAY, 1))

        # Back on track!  We got invoked when we expected this time.
        clock.advance(INTERVAL * 0.25)
        self.assertEqual(times.pop(), ((3.0 * INTERVAL) + REALISTIC_DELAY, 1))


    def testBasicFunction(self):
        # Arrange to have time advanced enough so that our function is
        # called a few times.
        # Only need to go to 2.5 to get 3 calls, since the first call
        # happens before any time has elapsed.
        timings = [0.05, 0.1, 0.1]

        clock = task.Clock()

        L = []
        def foo(a, b, c=None, d=None):
            L.append((a, b, c, d))

        lc = TestableLoopingCall(clock, foo, "a", "b", d="d")
        D = lc.start(0.1)

        theResult = []
        def saveResult(result):
            theResult.append(result)
        D.addCallback(saveResult)

        clock.pump(timings)

        self.assertEqual(len(L), 3,
                          "got %d iterations, not 3" % (len(L),))

        for (a, b, c, d) in L:
            self.assertEqual(a, "a")
            self.assertEqual(b, "b")
            self.assertEqual(c, None)
            self.assertEqual(d, "d")

        lc.stop()
        self.assertIdentical(theResult[0], lc)

        # Make sure it isn't planning to do anything further.
        self.failIf(clock.calls)


    def testDelayedStart(self):
        timings = [0.05, 0.1, 0.1]

        clock = task.Clock()

        L = []
        lc = TestableLoopingCall(clock, L.append, None)
        d = lc.start(0.1, now=False)

        theResult = []
        def saveResult(result):
            theResult.append(result)
        d.addCallback(saveResult)

        clock.pump(timings)

        self.assertEqual(len(L), 2,
                          "got %d iterations, not 2" % (len(L),))
        lc.stop()
        self.assertIdentical(theResult[0], lc)

        self.failIf(clock.calls)


    def testBadDelay(self):
        lc = task.LoopingCall(lambda: None)
        self.assertRaises(ValueError, lc.start, -1)


    # Make sure that LoopingCall.stop() prevents any subsequent calls.
    def _stoppingTest(self, delay):
        ran = []
        def foo():
            ran.append(None)

        clock = task.Clock()
        lc = TestableLoopingCall(clock, foo)
        lc.start(delay, now=False)
        lc.stop()
        self.failIf(ran)
        self.failIf(clock.calls)


    def testStopAtOnce(self):
        return self._stoppingTest(0)


    def testStoppingBeforeDelayedStart(self):
        return self._stoppingTest(10)


    def test_reset(self):
        """
        Test that L{LoopingCall} can be reset.
        """
        ran = []
        def foo():
            ran.append(None)

        c = task.Clock()
        lc = TestableLoopingCall(c, foo)
        lc.start(2, now=False)
        c.advance(1)
        lc.reset()
        c.advance(1)
        self.assertEqual(ran, [])
        c.advance(1)
        self.assertEqual(ran, [None])



class ReactorLoopTestCase(unittest.TestCase):
    # Slightly inferior tests which exercise interactions with an actual
    # reactor.
    def testFailure(self):
        def foo(x):
            raise TestException(x)

        lc = task.LoopingCall(foo, "bar")
        return self.assertFailure(lc.start(0.1), TestException)


    def testFailAndStop(self):
        def foo(x):
            lc.stop()
            raise TestException(x)

        lc = task.LoopingCall(foo, "bar")
        return self.assertFailure(lc.start(0.1), TestException)


    def testEveryIteration(self):
        ran = []

        def foo():
            ran.append(None)
            if len(ran) > 5:
                lc.stop()

        lc = task.LoopingCall(foo)
        d = lc.start(0)
        def stopped(ign):
            self.assertEqual(len(ran), 6)
        return d.addCallback(stopped)


    def testStopAtOnceLater(self):
        # Ensure that even when LoopingCall.stop() is called from a
        # reactor callback, it still prevents any subsequent calls.
        d = defer.Deferred()
        def foo():
            d.errback(failure.DefaultException(
                "This task also should never get called."))
        self._lc = task.LoopingCall(foo)
        self._lc.start(1, now=False)
        reactor.callLater(0, self._callback_for_testStopAtOnceLater, d)
        return d


    def _callback_for_testStopAtOnceLater(self, d):
        self._lc.stop()
        reactor.callLater(0, d.callback, "success")

    def testWaitDeferred(self):
        # Tests if the callable isn't scheduled again before the returned
        # deferred has fired.
        timings = [0.2, 0.8]
        clock = task.Clock()

        def foo():
            d = defer.Deferred()
            d.addCallback(lambda _: lc.stop())
            clock.callLater(1, d.callback, None)
            return d

        lc = TestableLoopingCall(clock, foo)
        lc.start(0.2)
        clock.pump(timings)
        self.failIf(clock.calls)

    def testFailurePropagation(self):
        # Tests if the failure of the errback of the deferred returned by the
        # callable is propagated to the lc errback.
        #
        # To make sure this test does not hang trial when LoopingCall does not
        # wait for the callable's deferred, it also checks there are no
        # calls in the clock's callLater queue.
        timings = [0.3]
        clock = task.Clock()

        def foo():
            d = defer.Deferred()
            clock.callLater(0.3, d.errback, TestException())
            return d

        lc = TestableLoopingCall(clock, foo)
        d = lc.start(1)
        self.assertFailure(d, TestException)

        clock.pump(timings)
        self.failIf(clock.calls)
        return d


    def test_deferredWithCount(self):
        """
        In the case that the function passed to L{LoopingCall.withCount}
        returns a deferred, which does not fire before the next interval
        elapses, the function should not be run again. And if a function call
        is skipped in this fashion, the appropriate count should be
        provided.
        """
        testClock = task.Clock()
        d = defer.Deferred()
        deferredCounts = []

        def countTracker(possibleCount):
            # Keep a list of call counts
            deferredCounts.append(possibleCount)
            # Return a deferred, but only on the first request
            if len(deferredCounts) == 1:
                return d
            else:
                return None

        # Start a looping call for our countTracker function
        # Set the increment to 0.2, and do not call the function on startup.
        lc = task.LoopingCall.withCount(countTracker)
        lc.clock = testClock
        d = lc.start(0.2, now=False)

        # Confirm that nothing has happened yet.
        self.assertEqual(deferredCounts, [])

        # Advance the clock by 0.2 and then 0.4;
        testClock.pump([0.2, 0.4])
        # We should now have exactly one count (of 1 call)
        self.assertEqual(len(deferredCounts), 1)

        # Fire the deferred, and advance the clock by another 0.2
        d.callback(None)
        testClock.pump([0.2])
        # We should now have exactly 2 counts...
        self.assertEqual(len(deferredCounts), 2)
        # The first count should be 1 (one call)
        # The second count should be 3 (calls were missed at about 0.6 and 0.8)
        self.assertEqual(deferredCounts, [1, 3])



class DeferLaterTests(unittest.TestCase):
    """
    Tests for L{task.deferLater}.
    """
    def test_callback(self):
        """
        The L{defer.Deferred} returned by L{task.deferLater} is called back
        after the specified delay with the result of the function passed in.
        """
        results = []
        flag = object()
        def callable(foo, bar):
            results.append((foo, bar))
            return flag

        clock = task.Clock()
        d = task.deferLater(clock, 3, callable, 'foo', bar='bar')
        d.addCallback(self.assertIdentical, flag)
        clock.advance(2)
        self.assertEqual(results, [])
        clock.advance(1)
        self.assertEqual(results, [('foo', 'bar')])
        return d


    def test_errback(self):
        """
        The L{defer.Deferred} returned by L{task.deferLater} is errbacked if
        the supplied function raises an exception.
        """
        def callable():
            raise TestException()

        clock = task.Clock()
        d = task.deferLater(clock, 1, callable)
        clock.advance(1)
        return self.assertFailure(d, TestException)


    def test_cancel(self):
        """
        The L{defer.Deferred} returned by L{task.deferLater} can be cancelled
        to prevent the call from actually being performed.
        """
        called = []
        clock = task.Clock()
        d = task.deferLater(clock, 1, called.append, None)
        d.cancel()
        def cbCancelled(ignored):
            # Make sure there are no calls outstanding.
            self.assertEqual([], clock.getDelayedCalls())
            # And make sure the call didn't somehow happen already.
            self.assertFalse(called)
        self.assertFailure(d, defer.CancelledError)
        d.addCallback(cbCancelled)
        return d


class AddDeferredTimeoutTests(unittest.TestCase):
    """
    Tests for L{task.addDeferredTimeout}.
    """

    def test_noTimeoutIfCallback(self):
        """
        L{task.addDeferredTimeout} will not not cause a timeout if the
        L{defer.Deferred}'s C{callback()} is called.
        """
        reactor = Clock()
        cancelled = []
        result = []
        d = defer.Deferred(cancelled.append)
        d.addCallback(result.append)

        task.addDeferredTimeout(reactor, d, 10)
        d.callback("success")
        self.assertEqual(result, ["success"])
        self.assertEqual(cancelled, [])
        # Timeout should have been cancelled:
        self.assertFalse(reactor.getDelayedCalls())


    def test_noTimeoutIfErrback(self):
        """
        L{task.addDeferredTimeout} will not not cause a timeout if the
        L{defer.Deferred}'s C{errback()} is called.
        """
        reactor = Clock()
        cancelled = []
        result = []
        d = defer.Deferred(cancelled.append)
        d.addErrback(result.append)

        task.addDeferredTimeout(reactor, d, 10)
        f = failure.Failure(RuntimeError())
        d.errback(f)
        self.assertEqual(result, [f])
        self.assertEqual(cancelled, [])
        # Timeout should have been cancelled:
        self.assertFalse(reactor.getDelayedCalls())


    def test_noTimeoutIfCancel(self):
        """
        L{task.addDeferredTimeout} will not not cause a timeout if the
        L{defer.Deferred}'s C{cancel()} method is called.
        """
        reactor = Clock()
        result = []
        d = defer.Deferred()
        d.addErrback(result.append)

        task.addDeferredTimeout(reactor, d, 10)
        d.cancel()
        self.assertIsInstance(result[0].value, defer.CancelledError)

        # Timeout should have been cancelled:
        self.assertFalse(reactor.getDelayedCalls())


    def test_timeout(self):
        """
        If the L{defer.Deferred} is not fired in time,
        L{task.addDeferredTimeout} will cancel it.
        """
        reactor = Clock()
        cancelled = []
        result = []
        d = defer.Deferred(cancelled.append)
        d.addErrback(result.append)

        task.addDeferredTimeout(reactor, d, 10)
        reactor.advance(10.1)
        self.assertIsInstance(result[0].value, defer.CancelledError)
        self.assertEqual(cancelled, [d])
        self.assertFalse(reactor.getDelayedCalls())


    def test_callbackStack(self):
        """
        L{task.addDeferredTimeout} will not timeout the L{defer.Deferred} if
        the callbacks that were added before it was called have fired, even if
        later callbacks mean it's back in a waiting state.
        """
        original = defer.Deferred()
        reactor = Clock()

        # Add the initial timeout:
        task.addDeferredTimeout(reactor, original, 1)

        # Add another callback, waiting for another Deferred:
        waiting = defer.Deferred()
        original.addCallback(lambda ign: waiting)

        # Add a second timeout:
        task.addDeferredTimeout(reactor, original, 2)

        # If we fire the original Deferred, this will cancel the first
        # timeout, even though the Deferred is now waiting again for a second
        # Deferred:
        result = []
        original.addBoth(result.append)
        original.callback(1)
        reactor.advance(1)
        self.assertEqual(result, [])

        # However, the 2nd timeout is still there:
        reactor.advance(1)
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0].value, defer.CancelledError)


    def test_cancelReturnedDelayedCall(self):
        """
        L{task.addDeferredTimeout} returns the C{IDelayedCall} for the
        scheduled timeout, allowing the caller to cancel the timeout manually.
        """
        reactor = Clock()
        result = []
        d = defer.Deferred()
        d.addCallback(result.append)

        delayedCall = task.addDeferredTimeout(reactor, d, 10)
        self.assertTrue(interfaces.IDelayedCall.providedBy(delayedCall))

        # If we cancel delayedCall, timeout is no longer active:
        delayedCall.cancel()
        reactor.advance(11)
        d.callback(u"success")
        self.assertEqual(result, [u"success"])

# -*- coding: utf-8 -*-
#
# Copyright (C) 2018 Andrew Resch <andrewresch@gmail.com>
#
# This file is part of Deluge and is licensed under GNU General Public License 3.0, or later, with
# the additional special exception to link portions of this program with the OpenSSL library.
# See LICENSE for more details.
#

import asyncio
from collections import defaultdict
from enum import Enum, auto
import logging
from typing import Dict, Iterable, List

from deluge.loopingcall import LoopingCall, NotRunning

log = logging.getLogger(__name__)


class AlreadyRegistered(Exception):
    pass


class NotRegistered(Exception):
    pass


class WrongState(Exception):
    pass


class State(Enum):
    STOPPING = auto()
    STOPPED = auto()
    STARTING = auto()
    STARTED = auto()
    PAUSING = auto()
    PAUSED = auto()
    RESUMING = auto()
    SHUTTING_DOWN = auto()
    SHUTDOWN = auto()


class Component:
    """Component objects are singletons managed by the :class:`ComponentRegistry`.

    When a new Component object is instantiated, it will be automatically
    registered with the :class:`ComponentRegistry`.

    The ComponentRegistry has the ability to start, stop, pause, resume and
    shutdown the components registered with it.

    **Events:**

        WARNING: DO NOT call any method from the ComponentRegistry in these
        callbacks as it may cause a deadlock.

        **start()** - This method is called when the client has connected to a
                  Deluge core.

        **stop()** - This method is called when the client has disconnected from a
                 Deluge core.

        **update()** - This method is called every 1 second by default while the
                   Componented is in a *Started* state.  The interval can be
                   specified during instantiation.  The update() timer can be
                   paused and resumed by instructing the
                   :class:`ComponentRegistry` to pause or resume this Component.

        **pause()** - This method is called when the Component is paused.

        **resume()** - This method is called when the Component is resumed.

        **shutdown()** - This method is called when the client is exiting.  If the
                     Component is in a "Started" state when this is called, a
                     call to stop() will be issued prior to shutdown().

    **States:**

        A Component can be in one of these 8 states.

        **Started** - The Component has been started by the :class:`ComponentRegistry`
                    and will have it's update timer started.

        **Starting** - The Component has had it's start method called, but it hasn't
                    fully started yet.

        **Stopped** - The Component has either been stopped or has yet to be started.

        **Stopping** - The Component has had it's stop method called, but it hasn't
                    fully stopped yet.

        **Pausing** - The Component is transitioning to a paused state.

        **Paused** - The Component has had it's update timer stopped, but will
                    still be considered in a Started state.

        **Resuming** - The Component is transitioning from a paused state to
                    a started state.

        **Shuting Down** - The Component is transitioning to a shutdown state.

        **Shutdown** - The Component has been shutdown. It cannot transition to
                    any other state anymore.

    """

    def __init__(self, name: str, interval: int = 1, depend: List[str] = None):
        """Initialize component.

        Args:
            name (str): Name of component.
            interval (int, optional): The interval in seconds to call the update function.
            depend (list, optional): The names of components this component depends on.

        """
        self._component_name = name
        self._component_interval = interval
        self._component_depend = depend
        self._component_state: State = State.STOPPED
        self._component_timer = LoopingCall(self.update)
        self._component_lock = asyncio.Lock()
        _ComponentRegistry.register(self)

    @property
    def state(self) -> State:
        return self._component_state

    async def _component_start(self):
        if self.state not in (State.STOPPED, State.STARTING, State.STARTED):
            raise WrongState(
                f'state: {self.state} wanted: not in (State.STOPPED, State.STARTING, State.STARTED)'
            )

        async with self._component_lock:
            if self.state == State.STARTED:
                return

            self._component_state = State.STARTING
            await self.start()
            self._component_state = State.STARTED
            self._component_timer.start(self._component_interval)

    async def _component_stop(self):
        if self.state not in (
            State.STARTED,
            State.PAUSED,
            State.STOPPING,
            State.STOPPED,
        ):
            raise WrongState(
                f'state: {self.state} wanted: not in (State.STARTED, State.PAUSED, State.STOPPING, State.STOPPED)'
            )

        async with self._component_lock:
            if self.state == State.STOPPED:
                return

            self._component_state = State.STOPPING
            await self.stop()
            try:
                await self._component_timer.stop()
            except NotRunning:
                pass
            self._component_state = State.STOPPED

    async def _component_pause(self):
        if self.state not in (State.STARTED, State.PAUSING, State.PAUSED):
            raise WrongState(
                f'state: {self.state} wanted: not in (State.STARTED, State.PAUSING, State.PAUSED)'
            )

        async with self._component_lock:
            if self.state == State.PAUSED:
                return

            self._component_state = State.PAUSING
            await self.pause()
            await self._component_timer.stop()
            self._component_state = State.PAUSED

    async def _component_resume(self):
        if self.state not in (State.PAUSED, State.RESUMING, State.STARTED):
            raise WrongState(
                f'state: {self.state} wanted: not in (State.PAUSED, State.RESUMING, State.STARTED)'
            )

        async with self._component_lock:
            if self.state == State.STARTED:
                return

            self._component_state = State.RESUMING
            await self.resume()
            self._component_timer.start(self._component_interval)
            self._component_state = State.STARTED

    async def _component_shutdown(self):
        if self.state != State.STOPPED:
            await self._component_stop()

        async with self._component_lock:
            if self.state == State.SHUTDOWN:
                return

            self._component_state = State.SHUTTING_DOWN
            await self.shutdown()
            self._component_state = State.SHUTDOWN

    async def start(self):
        pass

    async def stop(self):
        pass

    async def update(self):
        pass

    async def pause(self):
        pass

    async def resume(self):
        pass

    async def shutdown(self):
        pass


class ComponentRegistry:
    """The ComponentRegistry holds a list of currently registered :class:`Component` objects.

    It is used to manage the Components by starting, stopping, pausing and shutting them down.
    """

    def __init__(self):
        self.components: Dict[str, Component] = {}
        # Stores all of the components that are dependent on a particular component
        self.dependents: Dict[str, List[str]] = defaultdict(list)

    def register(self, obj: Component):
        """Register a component object with the registry.

        Note:
            This is done automatically when a Component object is instantiated.

        Args:
            obj (Component): A component object to register.

        Raises:
            AlreadyRegistered: If a component with the same name is already registered.

        """
        name = obj._component_name
        if name in self.components:
            raise AlreadyRegistered('Component already registered with name %s' % name)

        self.components[obj._component_name] = obj
        if obj._component_depend:
            for depend in obj._component_depend:
                self.dependents[depend].append(name)

    async def deregister(self, obj: Component):
        """Deregister a component from the registry.  A stop will be
        issued to the component prior to deregistering it.

        Args:
            obj (Component): a component object to deregister

        Raises:
            NotRegistered: If the object is not registered.
        """
        if obj not in self.components.values():
            raise NotRegistered(f'Object {obj} is not a registered Component.')
        log.debug('Deregistering Component: %s', obj._component_name)
        if obj.state != State.SHUTDOWN:
            await self.stop([obj._component_name])
        del self.components[obj._component_name]

    async def start(self, names: Iterable[str] = None):
        """Start Components, and their dependencies, that are currently in a Stopped state.

        Note:
            If no names are specified then all registered components will be started.

        Args:
            names (list): A list of Components to start and their dependencies.
        """
        if names is None:
            names = self.components.keys()

        for name in names:
            if self.components[name]._component_depend:
                # This component has depends, so we need to start them first.
                await self.start(self.components[name]._component_depend)
            await self.components[name]._component_start()

    async def stop(self, names: Iterable[str] = None):
        """Stop Components that are currently not in a Stopped state.

        Note:
            If no names are specified then all registered components will be stopped.

        Args:
            names (list): A list of Components to stop.
        """
        if names is None:
            names = self.components.keys()

        for name in names:
            if name in self.components:
                if name in self.dependents:
                    # If other components depend on this component, stop them first
                    await self.stop(self.dependents[name])
                await self.components[name]._component_stop()

    async def pause(self, names: Iterable[str] = None):
        """Pause Components that are currently in a Started state.

        Note:
            If no names are specified then all registered components will be paused.

        Args:
            names (list): A list of Components to pause.
        """
        if names is None:
            names = self.components.keys()

        for name in names:
            await self.components[name]._component_pause()

    async def resume(self, names: Iterable[str] = None):
        """Resume Components that are currently in a Paused state.

        Note:
            If no names are specified then all registered components will be resumed.

        Args:
            names (list): A list of Components to to resume.
        """
        if names is None:
            names = self.components.keys()

        for name in names:
            await self.components[name]._component_resume()

    async def shutdown(self):
        """Shutdown all Components regardless of state.

        This will call stop() on all the components prior to shutting down. This should be called
        when the program is exiting to ensure all Components have a chance to properly shutdown.
        """
        await self.stop()
        await asyncio.gather(
            *[c._component_shutdown() for c in self.components.values()]
        )


_ComponentRegistry = ComponentRegistry()

deregister = _ComponentRegistry.deregister
start = _ComponentRegistry.start
stop = _ComponentRegistry.stop
pause = _ComponentRegistry.pause
resume = _ComponentRegistry.resume
shutdown = _ComponentRegistry.shutdown


def get(name: str) -> Component:
    """Return a reference to a component.

    Args:
        name (str): The Component name to get.

    Returns:
        Component: The Component object.

    Raises:
        KeyError: If the Component does not exist.

    """
    return _ComponentRegistry.components[name]

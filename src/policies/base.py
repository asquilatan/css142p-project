"""
Abstract Base Class for Provisioning Policies.
"""

from abc import ABC, abstractmethod


class ProvisioningPolicy(ABC):
    def __init__(self, name: str):
        self.name = name
        self.sim = None

    def attach(self, simulation_engine):
        """Binds this policy to the running simulation engine."""
        self.sim = simulation_engine
        self.on_init()

    def on_init(self):
        """Called immediately after attaching to initialize server states."""
        pass

    def on_tick(self, current_time: float):
        """Called periodically by the simulation engine event loop."""
        pass

    def on_arrival(self, arrival_time: float):
        """Called when a new request enters the queue (receives its arrival timestamp)."""
        pass

    def on_completion(self, server, arrival_time: float):
        """Called when a request finishes processing on a server."""
        pass

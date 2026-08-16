"""Tests for opt-in plugin discovery."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from dq_questionbank.exceptions import PluginDiscoveryError
from dq_questionbank.plugins import available_plugins, discover_plugins
from dq_questionbank.registry import FormatRegistry, default_registry


class FakeEntryPoint:
    def __init__(self, name, registrar, *, value=None, group="dq_questionbank.plugins"):
        self.name = name
        self.group = group
        self.value = value or f"example:{name}"
        self._registrar = registrar

    def load(self):
        if isinstance(self._registrar, Exception):
            raise self._registrar
        return self._registrar


class FakeEntryPoints(list):
    def select(self, *, group):
        return [entry for entry in self if entry.group == group]


class PluginDiscoveryTests(unittest.TestCase):
    def test_available_plugins_is_sorted_without_loading(self):
        entries = FakeEntryPoints(
            [
                FakeEntryPoint("zeta", lambda registry: None),
                FakeEntryPoint("alpha", lambda registry: None),
            ]
        )
        with patch("dq_questionbank.plugins.entry_points", return_value=entries):
            self.assertEqual(available_plugins(), ("alpha", "zeta"))

    def test_discovery_calls_registrars_in_stable_order(self):
        calls = []

        def registrar(name):
            def register(registry):
                self.assertIsInstance(registry, FormatRegistry)
                calls.append(name)

            return register

        entries = FakeEntryPoints(
            [FakeEntryPoint("zeta", registrar("zeta")), FakeEntryPoint("alpha", registrar("alpha"))]
        )
        with patch("dq_questionbank.plugins.entry_points", return_value=entries):
            loaded = discover_plugins(FormatRegistry())
        self.assertEqual(loaded, ("alpha", "zeta"))
        self.assertEqual(calls, ["alpha", "zeta"])

    def test_discovery_wraps_load_and_registration_failures(self):
        registrars = (
            RuntimeError("load failed"),
            lambda registry: (_ for _ in ()).throw(ValueError("bad")),
        )
        for registrar in registrars:
            with self.subTest(registrar=registrar):
                entries = FakeEntryPoints([FakeEntryPoint("broken", registrar)])
                with patch("dq_questionbank.plugins.entry_points", return_value=entries):
                    with self.assertRaises(PluginDiscoveryError):
                        discover_plugins(FormatRegistry())

    def test_duplicate_names_and_invalid_registries_fail_closed(self):
        entries = FakeEntryPoints(
            [
                FakeEntryPoint("same", lambda registry: None),
                FakeEntryPoint("same", lambda registry: None),
            ]
        )
        with patch("dq_questionbank.plugins.entry_points", return_value=entries):
            with self.assertRaises(PluginDiscoveryError):
                available_plugins()
        with self.assertRaises(TypeError):
            discover_plugins(Path("not-a-registry"))

    def test_default_registry_never_discovers_plugins(self):
        with patch("dq_questionbank.plugins.entry_points") as discover:
            registry = default_registry()
        self.assertIn("json", registry.import_formats)
        discover.assert_not_called()

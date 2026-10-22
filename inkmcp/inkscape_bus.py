"""
Transport to the running Inkscape instance over the GLib session bus.

Inkscape exports its actions, including installed extensions, through the
GApplication ``org.gtk.Actions`` interface on ``org.inkscape.Inkscape``.

* Linux: the regular D-Bus session bus, driven with the ``gdbus`` tool.
* Windows: GLib auto-launches a private session bus for the user session
  (``gdbus.exe _win32_run_session_bus``). Its ``nonce-tcp:`` address is
  published in the named shared memory ``DBusDaemonAddressInfo`` and it
  authenticates with ``DBUS_COOKIE_SHA1`` against
  ``%USERPROFILE%\\.dbus-keyrings``. Inkscape's own ``gdbus.exe`` cannot be
  executed from a Microsoft Store (MSIX) install, so this module speaks the
  wire protocol directly with a minimal pure-Python client.

Public API: ``list_actions()`` and ``activate_mcp_action()``; both raise
``BusError`` with a user-facing reason when Inkscape cannot be reached.
"""

import ast
import hashlib
import os
import shutil
import socket
import struct
import subprocess
import sys
from functools import lru_cache
from typing import List, Optional, Tuple
from urllib.parse import unquote

SERVICE = "org.inkscape.Inkscape"
OBJECT_PATH = "/org/inkscape/Inkscape"
INTERFACE = "org.gtk.Actions"
ACTION_NAME = "org.khema.inkscape.mcp"

# Linux: full path of the gdbus binary to use; overrides PATH lookup.
GDBUS_ENV = "INKMCP_GDBUS"

NOT_RUNNING = "Inkscape is not running (no session bus service)."


class BusError(RuntimeError):
    """Inkscape could not be reached; the message explains why."""


def list_actions(timeout: float = 5) -> List[str]:
    """Names of the actions Inkscape currently exposes."""
    if sys.platform == "win32":
        return _win_list_actions(timeout)
    return _gdbus_list_actions(timeout)


def activate_mcp_action(timeout: float = 30) -> None:
    """Trigger the MCP extension; it reads mcp_params.json from the temp dir."""
    if sys.platform == "win32":
        _win_activate(timeout)
    else:
        _gdbus_activate(timeout)


# ---------------------------------------------------------------------------
# Linux: gdbus subprocess
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _find_gdbus() -> str:
    override = os.environ.get(GDBUS_ENV)
    if override:
        if os.path.isfile(override):
            return override
        raise BusError(f"{GDBUS_ENV} points to a missing file: {override}")
    found = shutil.which("gdbus")
    if found:
        return found
    raise BusError(
        "gdbus not found in PATH. Install the GLib tools (e.g. 'libglib2.0-bin' on "
        f"Debian/Ubuntu) or set {GDBUS_ENV} to the full path of gdbus."
    )


def _gdbus_call(method: str, *args: str, timeout: float) -> str:
    cmd = [
        _find_gdbus(), "call", "--session",
        "--dest", SERVICE, "--object-path", OBJECT_PATH,
        "--method", f"{INTERFACE}.{method}", *args,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise BusError(f"gdbus {method} timed out after {timeout:g}s")
    if result.returncode != 0:
        stderr = result.stderr.strip()
        if "ServiceUnknown" in stderr:
            raise BusError(NOT_RUNNING)
        raise BusError(f"gdbus call failed: {stderr}")
    return result.stdout


def _gdbus_list_actions(timeout: float) -> List[str]:
    output = _gdbus_call("List", timeout=timeout)
    try:
        (names,) = ast.literal_eval(output.strip())
        return list(names)
    except (ValueError, SyntaxError, TypeError):
        raise BusError(f"Unexpected gdbus List output: {output.strip()}")


def _gdbus_activate(timeout: float) -> None:
    _gdbus_call("Activate", ACTION_NAME, "[]", "{}", timeout=timeout)


# ---------------------------------------------------------------------------
# Windows: native client for the GLib auto-launched session bus
# ---------------------------------------------------------------------------

_SHM_NAME = "DBusDaemonAddressInfo"
_FILE_MAP_READ = 0x0004


def _win_bus_address() -> str:
    """Read the bus address GLib published in named shared memory."""
    import ctypes
    from ctypes import wintypes

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenFileMappingW.restype = wintypes.HANDLE
    k32.MapViewOfFile.restype = ctypes.c_void_p
    k32.MapViewOfFile.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ctypes.c_size_t]
    k32.UnmapViewOfFile.argtypes = [ctypes.c_void_p]
    k32.CloseHandle.argtypes = [wintypes.HANDLE]

    handle = k32.OpenFileMappingW(_FILE_MAP_READ, False, _SHM_NAME)
    if not handle:
        raise BusError(NOT_RUNNING)
    try:
        view = k32.MapViewOfFile(handle, _FILE_MAP_READ, 0, 0, 0)
        if not view:
            raise BusError("Cannot map the GLib session bus address")
        try:
            address = ctypes.string_at(view).decode()
        finally:
            k32.UnmapViewOfFile(view)
    finally:
        k32.CloseHandle(handle)
    if not address.startswith("nonce-tcp:"):
        raise BusError(f"Unsupported GLib session bus address: {address!r}")
    return address


@lru_cache(maxsize=1)
def _win_user_sid() -> str:
    """String SID of the current process token (what GLib expects as cookie identity)."""
    import ctypes
    from ctypes import wintypes
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.GetCurrentProcess.restype = wintypes.HANDLE
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    k32.LocalFree.argtypes = [wintypes.HLOCAL]
    advapi.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    advapi.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    advapi.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_wchar_p)]
    TOKEN_QUERY, TOKEN_USER = 0x0008, 1

    token = wintypes.HANDLE()
    if not advapi.OpenProcessToken(k32.GetCurrentProcess(), TOKEN_QUERY, ctypes.byref(token)):
        raise BusError("OpenProcessToken failed")
    try:
        size = wintypes.DWORD()
        advapi.GetTokenInformation(token, TOKEN_USER, None, 0, ctypes.byref(size))
        buf = ctypes.create_string_buffer(size.value)
        if not advapi.GetTokenInformation(token, TOKEN_USER, buf, size, ctypes.byref(size)):
            raise BusError("GetTokenInformation failed")
        sid_ptr = ctypes.cast(buf, ctypes.POINTER(ctypes.c_void_p))[0]
        sid_str = ctypes.c_wchar_p()
        if not advapi.ConvertSidToStringSidW(ctypes.c_void_p(sid_ptr), ctypes.byref(sid_str)):
            raise BusError("ConvertSidToStringSid failed")
        try:
            return sid_str.value
        finally:
            k32.LocalFree(sid_str)
    finally:
        k32.CloseHandle(token)


def _win_cookie(context: str, cookie_id: str) -> str:
    home = os.environ.get("USERPROFILE") or os.path.expanduser("~")
    path = os.path.join(home, ".dbus-keyrings", context)
    try:
        with open(path, "r") as f:
            for row in f:
                parts = row.split()
                if len(parts) == 3 and parts[0] == cookie_id:
                    return parts[2]
    except OSError as e:
        raise BusError(f"Cannot read D-Bus keyring {path}: {e}")
    raise BusError(f"Cookie {cookie_id} not found in D-Bus keyring {path}")


class _WinBusConnection:
    """Minimal D-Bus client: nonce-tcp transport, DBUS_COOKIE_SHA1 auth, two methods."""

    def __init__(self, timeout: float):
        params = dict(kv.split("=", 1) for kv in _win_bus_address()[len("nonce-tcp:"):].split(","))
        try:
            with open(unquote(params["noncefile"]), "rb") as f:
                nonce = f.read()
        except (KeyError, OSError) as e:
            raise BusError(f"Cannot read session bus nonce file: {e}")
        try:
            self.sock = socket.create_connection((params.get("host", "localhost"), int(params["port"])), timeout=timeout)
        except OSError as e:
            raise BusError(f"Cannot connect to the GLib session bus: {e}")
        self.serial = 0
        self.buffer = b""
        try:
            self._authenticate(nonce)
            self.call("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "Hello", "", b"")
        except Exception:
            self.sock.close()
            raise

    def close(self) -> None:
        self.sock.close()

    # -- authentication --------------------------------------------------

    def _read_line(self) -> bytes:
        line = b""
        while not line.endswith(b"\r\n"):
            chunk = self.sock.recv(1)
            if not chunk:
                raise BusError("Session bus closed the connection during authentication")
            line += chunk
        return line[:-2]

    def _authenticate(self, nonce: bytes) -> None:
        sid_hex = _win_user_sid().encode().hex().encode()
        self.sock.sendall(nonce + b"\0AUTH DBUS_COOKIE_SHA1 " + sid_hex + b"\r\n")
        reply = self._read_line()
        if not reply.startswith(b"DATA "):
            raise BusError(f"Session bus rejected DBUS_COOKIE_SHA1 auth: {reply.decode(errors='replace')}")
        context, cookie_id, server_challenge = bytes.fromhex(reply[5:].decode()).decode().split(" ")
        cookie = _win_cookie(context, cookie_id)
        client_challenge = os.urandom(16).hex()
        digest = hashlib.sha1(f"{server_challenge}:{client_challenge}:{cookie}".encode()).hexdigest()
        self.sock.sendall(b"DATA " + f"{client_challenge} {digest}".encode().hex().encode() + b"\r\n")
        reply = self._read_line()
        if not reply.startswith(b"OK"):
            raise BusError(f"Session bus authentication failed: {reply.decode(errors='replace')}")
        self.sock.sendall(b"BEGIN\r\n")

    # -- marshalling (little endian) ---------------------------------------

    @staticmethod
    def _pad(data: bytes, align: int) -> bytes:
        return data + b"\0" * (-len(data) % align)

    @staticmethod
    def _string(value: str) -> bytes:
        encoded = value.encode()
        return struct.pack("<I", len(encoded)) + encoded + b"\0"

    def _header_field(self, code: int, type_code: str, value: str) -> bytes:
        if type_code == "g":
            payload = struct.pack("<B", len(value)) + value.encode() + b"\0"
        else:
            payload = self._string(value)
        return struct.pack("<BB", code, 1) + type_code.encode() + b"\0" + payload

    def _method_call(self, dest: str, path: str, iface: str, member: str, signature: str, body: bytes) -> bytes:
        self.serial += 1
        fields = [
            self._header_field(1, "o", path),
            self._header_field(6, "s", dest),
            self._header_field(2, "s", iface),
            self._header_field(3, "s", member),
        ]
        if signature:
            fields.append(self._header_field(8, "g", signature))
        # Each a(yv) struct element is aligned to 8; the array length excludes the trailing pad.
        array = b""
        for field in fields:
            array = self._pad(array, 8) + field
        header = struct.pack("<cBBBII", b"l", 1, 0, 1, len(body), self.serial) + struct.pack("<I", len(array)) + array
        return self._pad(header, 8) + body

    # -- receiving ---------------------------------------------------------

    def _recv_exact(self, n: int) -> bytes:
        while len(self.buffer) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise BusError("Session bus closed the connection")
            self.buffer += chunk
        data, self.buffer = self.buffer[:n], self.buffer[n:]
        return data

    def _read_message(self) -> Tuple[int, dict, bytes]:
        """Return (message_type, header_fields, body)."""
        fixed = self._recv_exact(16)
        endian, msg_type, _flags, _ver, body_len, _serial, fields_len = struct.unpack("<cBBBIII", fixed)
        if endian != b"l":
            raise BusError("Big-endian D-Bus messages are not supported")
        fields_raw = self._recv_exact(fields_len + (-(16 + fields_len) % 8))
        body = self._recv_exact(body_len)

        fields = {}
        pos = 0
        while pos < fields_len:
            code, sig_len = fields_raw[pos], fields_raw[pos + 1]
            sig = fields_raw[pos + 2:pos + 2 + sig_len].decode()
            pos += 2 + sig_len + 1
            if sig == "g":
                length = fields_raw[pos]
                fields[code] = fields_raw[pos + 1:pos + 1 + length].decode()
                pos += 1 + length + 1
            elif sig in ("s", "o"):
                pos += -pos % 4
                (length,) = struct.unpack_from("<I", fields_raw, pos)
                fields[code] = fields_raw[pos + 4:pos + 4 + length].decode()
                pos += 4 + length + 1
            elif sig == "u":
                pos += -pos % 4
                (fields[code],) = struct.unpack_from("<I", fields_raw, pos)
                pos += 4
            else:
                raise BusError(f"Unexpected header field signature {sig!r}")
            pos += -pos % 8
        return msg_type, fields, body

    def call(self, dest: str, path: str, iface: str, member: str, signature: str, body: bytes) -> Tuple[str, bytes]:
        """Send a method call and return (reply_signature, reply_body)."""
        self.sock.sendall(self._method_call(dest, path, iface, member, signature, body))
        serial = self.serial
        while True:
            try:
                msg_type, fields, reply = self._read_message()
            except socket.timeout:
                raise BusError(f"{member} timed out waiting for Inkscape")
            if fields.get(5) != serial:
                continue  # signal or unrelated message (e.g. NameAcquired)
            if msg_type == 2:
                return fields.get(8, ""), reply
            if msg_type == 3:
                name = fields.get(4, "unknown error")
                detail = ""
                if fields.get(8, "").startswith("s") and len(reply) >= 4:
                    (length,) = struct.unpack_from("<I", reply, 0)
                    detail = reply[4:4 + length].decode(errors="replace")
                if name.endswith(".ServiceUnknown"):
                    raise BusError(NOT_RUNNING)
                raise BusError(f"{name}: {detail}" if detail else name)
            raise BusError(f"Unexpected D-Bus message type {msg_type}")


def _win_parse_string_array(body: bytes) -> List[str]:
    (length,) = struct.unpack_from("<I", body, 0)
    pos, end, names = 4, 4 + length, []
    while pos < end:
        pos += -pos % 4
        (str_len,) = struct.unpack_from("<I", body, pos)
        names.append(body[pos + 4:pos + 4 + str_len].decode())
        pos += 4 + str_len + 1
    return names


def _win_list_actions(timeout: float) -> List[str]:
    conn = _WinBusConnection(timeout)
    try:
        signature, body = conn.call(SERVICE, OBJECT_PATH, INTERFACE, "List", "", b"")
    finally:
        conn.close()
    if signature != "as":
        raise BusError(f"Unexpected List reply signature {signature!r}")
    return _win_parse_string_array(body)


def _win_activate(timeout: float) -> None:
    conn = _WinBusConnection(timeout)
    try:
        # Activate(s action_name, av parameter, a{sv} platform_data): empty arrays
        # are a uint32 length of 0; the a{sv} array content is 8-aligned.
        body = conn._string(ACTION_NAME)
        body = conn._pad(body, 4) + struct.pack("<I", 0)
        body = conn._pad(body, 4) + struct.pack("<I", 0)
        body = conn._pad(body, 8)
        conn.call(SERVICE, OBJECT_PATH, INTERFACE, "Activate", "sava{sv}", body)
    finally:
        conn.close()

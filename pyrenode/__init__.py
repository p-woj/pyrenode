import re, telnetlib
import pexpect
from typing import Tuple

logfile = '/tmp/renode_log.txt'
global renode_connection
renode_connection = None
global renode_log
renode_log = None

import logging
LOGGER = logging.getLogger(__name__)

def escape_ansi(line):
    ansi_escape = re.compile(r'(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]')
    return ansi_escape.sub('', line)

def connect_renode(port=12348):

    port = port
    global renode_log
    renode_log = pexpect.spawn('renode --plain --port '+str(port)+' --disable-xwt')
    renode_log.stripcr = True
    assert expect_log("Monitor available in telnet mode on port").match is not None
    global renode_connection
    renode_connection = telnetlib.Telnet("localhost", port)
    assert expect_cli("(monitor)").match is not None
    # first char gets eaten for some reason, hence the space
    tell_renode(" ")
    tell_renode(f"logFile @{logfile}")
    tell_renode(f"Clear")

def shutdown_renode():

    import psutil

    for proc in psutil.process_iter():
        if "Renode" in proc.name():
            proc.kill()

    if renode_connection:
        renode_connection.close()

def tell_renode(string, newline = True):
    if newline:
        string += '\n'
    renode_connection.write(string.encode())

from typing import List, Dict
from dataclasses import dataclass, field

@dataclass
class Result:
    text: str = ''
    match: object = None

def read_until(string, timeout = 1):
    return escape_ansi(renode_connection.read_until(string.encode(), timeout).decode())

def expect_cli(string, timeout = 15):
    # take into consideration that the outpit will include some CR chars
    expected = re.escape(string).replace('\n','\r*\n\r*')
    idx, matches, data = renode_connection.expect([expected.encode()], timeout)
    return Result(escape_ansi(data.decode()), matches)

def expect_log(regex, timeout = 15):
    result = renode_log.expect(regex, timeout=timeout)
    return Result(escape_ansi(renode_log.before.decode()), renode_log.match)

# same as in tuttest, but wanted to avoid the import for now
@dataclass
class Snippet:
    text: List[str] = field(default_factory=list)
    lang: str = ''
    meta: Dict = field(default_factory=dict)
    commands: List[Command] = field(default_factory=list)

@dataclass
class Command:
    prompt: str
    command: str
    result: str = ''

def autoexec(snippet: Snippet):
    if 'name' in snippet.meta:
        name = snippet.meta['name']
        LOGGER.info(f"Executing snippet '{name}'")
    else:
        LOGGER.info(f"Executing unnamed snippet")
    # inject empty command to make sure we have the right prompt
    tell_renode('');
    for c in snippet.commands:
        if c.prompt:
            LOGGER.info(f"  {c.prompt}")
            assert expect_cli(c.prompt).match is not None
        if c.command:
            LOGGER.info(f"  >>> {c.command}")
            tell_renode(c.command)
            assert expect_cli(c.command).match is not None
        if c.result:
            for line in c.result.strip().split('\n'):
                LOGGER.info(f"  {line}")
            assert expect_cli(c.result).match is not None
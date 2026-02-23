# power-detect

Monitors GPIO pin and serves the status via a threaded HTTP server.

## Usage

```
usage: power-detect.py [-h] [-p PORT] [-d DELAY] [-g GPIO] [-v VERBOSITY] [-V]

Monitors GPIO pin and serves the status via a threaded HTTP server.

options:
  -h, --help            show this help message and exit
  -p PORT, --port PORT  HTTP port to listen on (default: 1999)
  -d DELAY, --delay DELAY
                        Seconds to wait after power loss before status becomes "shutdown" (default: 300)
  -g GPIO, --gpio GPIO  GPIO pin to monitor (default: 5)
  -v VERBOSITY, --verbosity VERBOSITY
                        The logging verbosity (DEBUG=10, INFO=20, WARNING=30)
  -V, --version         show program's version number and exit
```

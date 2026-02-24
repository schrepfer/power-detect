#!/usr/bin/env python3

"""Monitors GPIO pin and serves the status via a threaded HTTP server."""

import argparse
import logging
import os
import sys
import time

from enum import Enum
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from gpiozero import Button


def define_flags() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument(
      '-p', '--port',
      type=int,
      default=1999,
      help='HTTP port to listen on (default: 1999)',
  )
  parser.add_argument(
      '-d', '--delay',
      type=int,
      default=300,
      help='Seconds to wait after power loss before status becomes "shutdown" (default: 300)',
  )
  parser.add_argument(
      '-i', '--input-pin',
      type=int,
      default=5,
      help='The input GPIO pin (BCM numbering)',
  )
  parser.add_argument(
      '-v', '--verbosity',
      default=logging.INFO,
      type=int,
      help='The logging verbosity (DEBUG=10, INFO=20, WARNING=30)',
  )
  parser.add_argument(
      '-V', '--version',
      action='version',
      version='power-detect version 0.2',
  )

  args = parser.parse_args()
  check_flags(parser, args)
  return args

def check_flags(parser: argparse.ArgumentParser,
                args: argparse.Namespace) -> None:
  # See: http://docs.python.org/3/library/argparse.html#exiting-methods
  return None

class PowerStatus(Enum):
  OK = 'ok'
  SHUTDOWN = 'shutdown'

# Initial state
current_status = PowerStatus.OK

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
  """Handle requests in a separate thread."""
  daemon_threads = True

class StatusHandler(BaseHTTPRequestHandler):
  def do_GET(self):
    self.send_response(200)
    self.send_header('Content-type', 'text/plain')
    self.end_headers()
    self.wfile.write(f'{current_status.value}\n'.encode())

  def handle_error(self, request, client_address):
    # Get the current exception
    exctype, value = sys.exc_info()[:2]

    # If it's just a connection reset, log it as a warning (or ignore it)
    if exctype is ConnectionResetError:
      logging.warning(f'Connection reset by client {client_address}')
    else:
      # For all other "real" errors, use the default behavior
      super().handle_error(request, client_address)

  def log_message(self, format, *args):
    # Redirect server logs to logging module
    logging.info('%s - - %s' % (self.address_string(), format % args))

def monitor_power(pin: int, delay_seconds: int):
  """Watches the GPIO pin and updates the global status."""
  global current_status

  # pull_up=False means we expect 3.3v to pull the pin HIGH
  power_sense = Button(pin, pull_up=False)

  logging.info(f'Monitoring GPIO {pin}. Shutdown delay: {delay_seconds}s')

  current_status = (
      PowerStatus.OK
      if power_sense.is_pressed
      else PowerStatus.SHUTDOWN
  )

  while True:
    if power_sense.is_pressed:
      # Power is present
      if current_status != PowerStatus.OK:
        logging.warning('Power restored. Status: {current_status}')
        current_status = PowerStatus.OK
    elif current_status == PowerStatus.OK:
      # Power is lost, start the countdown
      logging.warning(f'Power loss detected! Waiting {delay_seconds}s before signaling shutdown...')

      # Re-check during the delay
      lost_time = time.time()
      still_lost = True

      while time.time() - lost_time < delay_seconds:
        time.sleep(1)
        if power_sense.is_pressed:
          logging.info('Power restored during grace period.')
          still_lost = False
          break

      if still_lost:
        logging.critical('Grace period exceeded. Status: shutdown')
        current_status = PowerStatus.SHUTDOWN

    time.sleep(1)


def main(args: argparse.Namespace) -> int:
  # Start the power monitoring in a background thread
  monitor_thread = Thread(
      target=monitor_power, 
      args=(args.input_pin, args.delay), 
      daemon=True
  )
  monitor_thread.start()

  # Start the HTTP server
  server_address = ('', args.port)
  httpd = ThreadedHTTPServer(server_address, StatusHandler)
  logging.info(f'Server started on port {args.port}')

  try:
    httpd.serve_forever()
  except KeyboardInterrupt:
    logging.info('Shutting down...')
    return os.EX_OK

  return os.EX_OK


if __name__ == '__main__':
  a = define_flags()
  logging.basicConfig(
      level=a.verbosity,
      datefmt='%Y/%m/%d %H:%M:%S',
      format='%(levelname)s: %(message)s')
  sys.exit(main(a))

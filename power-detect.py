#!/usr/bin/env python3

"""Monitors GPIO pin and serves the status via a threaded HTTP server."""

import argparse
import datetime
import logging
import os
import sys
import time
import smtplib
import socket
from email.message import EmailMessage

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
    '-a', '--admin-email',
    type=str,
    default='',
    help='Email address to notify on power status changes',
  )
  parser.add_argument(
    '--smtp-server',
    type=str,
    default='',
    help='Email address to notify on power status changes',
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
    version='power-detect version 0.3',
  )

  args = parser.parse_args()
  return args


class PowerStatus(Enum):
  UNKNOWN = 'unknown'
  POWERED = 'powered'
  BATTERY = 'battery'
  SHUTDOWN = 'shutdown'


# Initial state
current_status = PowerStatus.POWERED


def send_notification(args: argparse.Namespace, message: str, status: PowerStatus, old_status: PowerStatus = PowerStatus.UNKNOWN):
  """Sends an email notification via localhost SMTP."""
  if not args.admin_email or not args.smtp_server:
    return

  now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  fqdn = socket.getfqdn()

  msg = EmailMessage()
  subject = f"[Power Detect] {message}"

  body = [
    f"Event Time:  {now}",
    f"Device FQDN: {fqdn}",
    f"Status:      {old_status.value.upper()} -> {status.value.upper()}",
  ]

  msg.set_content('\n'.join(body))

  msg['Subject'] = subject
  msg['From'] = f"power-detect@{socket.getfqdn()}"
  msg['To'] = args.admin_email

  try:
    # Defaults to localhost.
    with smtplib.SMTP(args.smtp_server) as s:
      #s.set_debuglevel(1)
      s.send_message(msg)
    logging.info(f"Notification email sent to {args.admin_email}")
  except Exception as e:
    logging.error(f"Failed to send email: {e}")


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
  """Handle requests in a separate thread."""
  daemon_threads = True


class StatusHandler(BaseHTTPRequestHandler):
  def do_GET(self):
    self.send_response(200)
    self.send_header('Content-type', 'text/plain')
    self.end_headers()
    self.wfile.write(f'{current_status.value}\n'.encode())

  def log_message(self, format, *args):
    logging.info('%s - - %s' % (self.address_string(), format % args))


def monitor_power(args: argparse.Namespace) -> None:
  """Watches the GPIO pin and updates the global status."""
  global current_status

  power_sense = Button(args.input_pin, pull_up=False)
  logging.info(f'Monitoring GPIO {args.input_pin}. Shutdown delay: {args.delay}s')

  current_status = (
    PowerStatus.POWERED
    if power_sense.is_pressed
    else PowerStatus.BATTERY
  )

  while True:
    if power_sense.is_pressed:
      # Power is present
      if current_status != PowerStatus.POWERED:
        old = current_status
        current_status = PowerStatus.POWERED
        logging.info(f'Power restored from {old.value} state.')
        send_notification(args, 'Power restored', current_status, old)

    elif current_status in {PowerStatus.POWERED, PowerStatus.BATTERY}:
      # Power just lost
      old = current_status
      current_status = PowerStatus.BATTERY
      logging.warning(f'Power loss detected! Waiting {args.delay}s before signaling shutdown...')
      send_notification(args, 'Power is out', current_status, old)

      # Enter grace period countdown
      lost_time = time.time()
      still_lost = True
      while time.time() - lost_time < args.delay:
        time.sleep(1)
        if power_sense.is_pressed:
          old = current_status
          current_status = PowerStatus.POWERED
          logging.info('Power restored during grace period.')
          still_lost = False
          send_notification(args, 'Power restored', current_status, old)
          break

      if still_lost and current_status != PowerStatus.SHUTDOWN:
        old = current_status
        current_status = PowerStatus.SHUTDOWN
        logging.critical('Grace period exceeded. Status: shutdown')

    time.sleep(1)


def main(args: argparse.Namespace) -> int:
  monitor_thread = Thread(
    target=monitor_power,
    args=[args],
    daemon=True
  )
  monitor_thread.start()

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

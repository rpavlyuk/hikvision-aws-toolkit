#!/usr/bin/env python3
#
# hk-aws-tool: manage files stored by Hikvision devices on the file share: upload them to AWS, rotate old files, etc.
# Author: Roman Pavlyuk <roman.pavlyuk@gmail.com>

_VERSION="1.0"

# import modules used here -- sys is a very standard one
import sys, argparse, logging
from argparse import ArgumentError
from hkawstoolkit import util, manage


# Gather our code in a main() function
def main(args, loglevel):
  logging.basicConfig(format="%(levelname)s: %(message)s", level=loglevel)
  
  logging.info("hk-aws-toolkit version " +  _VERSION)
  logging.info("More info here: https://github.com/rpavlyuk/hikvision-aws-toolkit")

  if args.force:
      logging.warning("Force mode is ON")

  # Loading the configuration
  cfg = util.parse_config(args, args.config)

  # Main program code
  logging.info("tool action to take: %s" % args.action)

  # Bring the action!
  manage.action(args, cfg)



# Standard boilerplate to call the main() function to begin
# the program.
if __name__ == '__main__':
  parser = argparse.ArgumentParser( 
          description = "hk-aws-tool: manage files stored by Hikvision devices on the file share",
          fromfile_prefix_chars = '@' )
  # Parameters
  parser.add_argument(
                      "-a",
                      "--action",
                      help = "Action the script has to perform",
                      choices=['upload', 'cleanup', 'list', 'list-cameras', 'list-camera-dirs', 'list-camera-files', 'list-camera-files-on-date' ],
                      required=True)
  parser.add_argument(
                      "-v",
                      "--verbose",
                      help="Increase output verbosity. NOTE: This option produces lots of information like API calls so beware when using it.",
                      action="store_true",
                      default=False)
  parser.add_argument(
                      "-f",
                      "--force",
                      help="Ignore minor errors, assume 'yes' when deleting and override in case of existing entities",
                      action="store_true")
  parser.add_argument(
                      "-c",
                      "--config",
                      help = "Path to main configuration file (e.g., config.yaml)",
                      required=False,
                      default='/etc/hkawstoolkit/config.yaml')
  parser.add_argument(
                      "-q",
                      "--quiet",
                      help="Stay quiet and make all responses ready for machine processing, e.g. stripping out the surplus info text",
                      action="store_true",
                      default=False)
  parser.add_argument(
                      "-m",
                      "--camera",
                      help="Camera to proceed with (required for certain actions)",
                      required=False,
                      default=None)
  parser.add_argument(
                      "-d",
                      "--date",
                      help="Date of the event (required for certain actions). Format: YYYY-MM-DD",
                      required=False,
                      default=None)   
  parser.add_argument(
                      "-p",
                      "--pattern",
                      help="Filter files. Format example: *.jpg",
                      required=False,
                      default="*")                   

  args = parser.parse_args()
  
  # Setup logging
  if args.verbose:
    loglevel = logging.DEBUG
  else:
    loglevel = logging.INFO

  # "quiet" has higher priority over "verbose"
  if args.quiet:
    loglevel = logging.ERROR

main(args, loglevel)
import logging
import os
import sys
from datetime import datetime, timedelta
from time import sleep

import tensorflow as tf


def set_logger():
    verbosity = int(os.environ.get('VERBOSITY', 1))
    if verbosity == 0:
        logging.getLogger().setLevel(logging.WARNING)
    elif verbosity == 1:
        logging.getLogger().setLevel(logging.INFO)
    elif verbosity > 1:
        logging.getLogger().setLevel(logging.DEBUG)
    logging.basicConfig(format="%(asctime)s %(filename)s "
                                "%(lineno)s %(levelname)s - %(message)s")


def check_file_exist_infinity(input_file):
    while True:
        if tf.io.gfile.exists(input_file):
            break
        logging.info('%s does not exist, sleep 10s...', input_file)
        sleep(10)
    logging.info('%s is ready', input_file)


def main():
    set_logger()
    input_dir = os.getenv('INPUT_PATH')
    has_date = os.getenv('HAS_DATE', 0)
    offset = os.getenv('OFFSET')
    check_success = int(os.getenv('CHECK_SUCCESS', '1'))
    if not input_dir:
        print("Input dir is not set")
        sys.exit(1)

    if has_date:
        cur_day = datetime.today()
        if offset and int(offset) > 0:
            offset = int(offset)
        else:
            offset = 1  # default last day
        cur_day = cur_day - timedelta(days=offset)
        cur_day_str = cur_day.strftime('%Y%m%d')
        input_dir = os.path.join(input_dir, cur_day_str)

    if check_success:
        input_dir = os.path.join(input_dir, '_SUCCESS')

    check_file_exist_infinity(input_dir)


if __name__ == "__main__":
    main()

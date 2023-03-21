import sys
import traceback

import os
from photolog.db import DB
from photolog.settings import Settings
from photolog.squeue import SqliteQueue
from photolog.queue.jobs import prepare_job
from photolog import queue_logger as log, settings_file


def daemon(db, settings, queue):
    log.info('Starting daemon')
    daemon_started = True
    while daemon_started:
        job = queue.popleft(100)
        try:
            next_job = prepare_job(job, db, settings).process()
        except KeyboardInterrupt as inter:
            log.info('Daemon interrupted')
            queue.append(job)
            daemon_started = False
        except SystemExit as inter:
            # If job was interrupted, don't toss job.
            queue.append(job)
            log.info('Daemon interrupted')
            daemon_started = False
        except Exception as exc:
            ex_type, ex, tb = sys.exc_info()
            traceback.print_tb(tb)
            if job['attempt'] <= settings.MAX_QUEUE_ATTEMPTS:
                job['attempt'] += 1
                queue.append(job)
            else:
                # What should it do? Send a notification, record an error?
                # Don't loose the task
                log.info('Adding job %s to bad jobs' % job['key'])
                queue.append_bad(job)
        else:
            if next_job:
                queue.append(next_job)

    log.info("Finishing daemon")


def start():
    if not settings_file:
        print("Provide a SETTINGS env variable pointing to the settings.yaml file")
        sys.exit(1)

    settings = Settings.load(settings_file)
    db = DB(settings.DB_FILE)
    queue = SqliteQueue(settings.DB_FILE)
    ensure_thumbs_folder(settings)
    daemon(db, settings, queue)


def ensure_thumbs_folder(settings):
    if not os.path.exists(settings.THUMBS_FOLDER):
        os.makedirs(settings.THUMBS_FOLDER)

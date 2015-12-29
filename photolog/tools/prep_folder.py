import os
import argparse
from photolog import ALLOWED_FILES, IMAGE_FILES, RAW_FILES

BASE_COMMAND = 'upload2photolog'


def run():
    parser = argparse.ArgumentParser(
        description="Prepare directory for upload"
    )
    parser.add_argument('directories', type=str, nargs='+',
        help="Directory to upload")
    parser.add_argument('--tags', metavar='T', nargs='?', type=str,
        help="Tags for this batch")
    parser.add_argument('--host', metavar='H', nargs='?', type=str,
        help="Host to upload")
    parser.add_argument('--skip', nargs='?', type=str,
        help="steps to skip")
    parser.add_argument('--output', type=str,
        help="File to write commands")
    parsed = parser.parse_args()

    directories = parsed.directories
    tags = parsed.tags or ''
    skip = parsed.skip or ''
    host = parsed.host or ''
    output = parsed.output or ''
    lines, first_batch, second_batch = [], [], []

    for directory in directories:
        for file in os.listdir(directory):
            name, ext = os.path.splitext(file)
            ext = ext.lstrip('.').lower()
            if ext not in ALLOWED_FILES:
                continue
            full_file = os.path.join(directory, file)
            if ext in IMAGE_FILES:
                first_batch.append((file, full_file))
            elif ext in RAW_FILES:
                second_batch.append((file, full_file))

    # Keep file, full_file so it gets sorted same way as uploader will
    for file, full_file in sorted(first_batch) + sorted(second_batch):
        base_command = ['%(command)s %(file)s ' % {
            'command': BASE_COMMAND,
            'file': full_file
        }]
        if skip:
            base_command.append("--skip '%s'" % skip)
        if host:
            base_command.append("--host %s" % host)
        if tags:
            base_command.append("--tags '%s'" % tags)
        lines.append(' '.join(base_command))

    with open(output, 'a') as fh:
        fh.write('\n'.join(lines))


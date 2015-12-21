from setuptools import setup

setup(
    name='upload_api',
    version='0.1',
    install_requirements=[
        'Flask==0.10.1'
        'piexif==1.0.2',
        'gunicorn==19.4.1',
        'flickrapi==2.1.2',
        'boto==2.38.0',
        'PyYAML==3.11',
        'Pillow==3.0.0',
        'ExifRead==2.1.2',
    ],
    entry_points={
        'console_scripts': [
            'start_api=upload_api.main:start',
            'start_queue=upload_api.queue_runner:start_daemon',
            'start_web=upload_api.webend.app:start'
        ]
    }
)

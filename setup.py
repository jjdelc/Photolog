from setuptools import setup

setup(
    name='Photolog',
    version='0.1',
    install_requirements=[
        'Flask==0.10.1'
        'piexif==1.0.2',
        'flickrapi==2.1.2',
        'boto==2.38.0',
        'PyYAML==3.11',
        'Pillow==3.0.0',
        'ExifRead==2.1.2',
        'Flask-Login==0.4.0'
    ],
    entry_points={
        'console_scripts': [
            'start_api=photolog.api.main:start',
            'start_queue=photolog.queue.main:start',
            'start_web=photolog.web.main:start',
            'upload2photolog=photolog.tools.uploader:run',
            'prep_folder=photolog.tools.prep_folder:run'
        ]
    }
)

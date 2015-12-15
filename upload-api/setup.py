from setuptools import setup

setup(
    name='upload_api',
    version='0.1',
    install_requirements=[
        'Flask==0.10.1'
    ],
    entry_points={
        'console_scripts': [
            'start_api=upload_api.main:start',
            'start_queue=upload_api.queue_runner:daemon'
        ]
    }
)

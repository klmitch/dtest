from distutils.core import setup

setup(
    name='DTest',
    version='0.1',
    description="Dependency-based Threaded Test Framework",
    author="Kevin L. Mitchell",
    author_email="kevin.mitchell@rackspace.com",
    url="",
    scripts=['bin/run-dtests'],
    packages=['dtest',],
    license="",
    long_description=open('README.txt').read(),
    requires=['eventlet'],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: End Users/Desktop',
        'Intended Audience :: Information Technology',
        'License :: Other/Proprietary License',  # temporary, until we decide
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Topic :: Software Development :: Testing',
        ],
    )

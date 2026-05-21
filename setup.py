from setuptools import setup, find_packages

setup(
    name='ebayAlert',
    version='2.0',
    description='eBay/Kleinanzeigen alert scraper',
    python_requires='>=3.8',
    packages=find_packages(),
    install_requires=[
        'click>=8.1.3',
        'SQLAlchemy>=1.4.46',
        'beautifulsoup4>=4.11.1',
        'geopy>=2.3.0',
        'requests>=2.28.1',
        'scrapeops-scrapy>=0.5.2',
        'python-dotenv>=1.0.0',
    ],
    entry_points={'console_scripts': ['ebayAlert=ebayAlert.main:cli']}
)
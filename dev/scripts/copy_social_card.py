"""Override the default social card image as we are using a custom image for the social card."""

import logging
import os
import shutil
import sys

_logger = logging.getLogger(__name__)


logging.basicConfig(level=logging.INFO, format='%(levelname)s    -  %(message)s', stream=sys.stdout)


def on_post_build(config, **kwargs):
    _logger.info('Running post build actions...')
    if os.path.exists('site/assets/images/social'):  # only on gh-pages branch
        _logger.info('Copying custom social card...')
        shutil.copyfile('docs/assets/images/social-card.png', 'site/assets/images/social/index.png')
